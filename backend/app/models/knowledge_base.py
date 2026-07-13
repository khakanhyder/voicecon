"""
Knowledge Base Models

Database models for RAG (Retrieval Augmented Generation) system.
Supports document management, chunking, and vector embeddings.
"""
from datetime import datetime
from typing import Optional, List
import uuid

from sqlalchemy import String, Integer, Text, DateTime, ForeignKey, Boolean, JSON, Float, Index, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class KnowledgeBase(Base):
    """
    Knowledge base container for organizing documents.
    Multiple agents can share a knowledge base or have their own.
    """
    __tablename__ = "knowledge_bases"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("organizations.id"), nullable=False)

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)

    # Configuration
    embedding_model: Mapped[str] = mapped_column(String(100), default="text-embedding-ada-002")  # OpenAI model
    chunk_size: Mapped[int] = mapped_column(Integer, default=1000)  # Characters per chunk
    chunk_overlap: Mapped[int] = mapped_column(Integer, default=200)  # Overlap between chunks
    vector_dimension: Mapped[int] = mapped_column(Integer, default=1536)  # OpenAI embedding dimension

    # Vector store configuration
    vector_store_type: Mapped[str] = mapped_column(String(50), default="pinecone")  # pinecone, qdrant, local
    vector_store_config: Mapped[Optional[dict]] = mapped_column(JSON)  # Store-specific config

    # Metadata
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    documents: Mapped[List["Document"]] = relationship("Document", back_populates="knowledge_base", cascade="all, delete-orphan")
    agent_knowledge_bases: Mapped[List["AgentKnowledgeBase"]] = relationship("AgentKnowledgeBase", back_populates="knowledge_base")

    # Indexes
    __table_args__ = (
        Index('idx_kb_org', 'organization_id'),
        Index('idx_kb_active', 'is_active'),
    )


class Document(Base):
    """
    Documents uploaded to a knowledge base.
    Can be PDFs, text files, web pages, etc.
    """
    __tablename__ = "documents"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    knowledge_base_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("knowledge_bases.id"), nullable=False)

    # Document info
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    source_type: Mapped[str] = mapped_column(String(50), nullable=False)  # file, url, text, api
    source_url: Mapped[Optional[str]] = mapped_column(String(1000))  # Original URL or file path
    file_type: Mapped[Optional[str]] = mapped_column(String(50))  # pdf, txt, docx, html, etc.
    file_size: Mapped[Optional[int]] = mapped_column(Integer)  # Size in bytes

    # Content
    content: Mapped[str] = mapped_column(Text, nullable=False)  # Full text content
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)  # SHA-256 hash for deduplication

    # Metadata
    document_metadata: Mapped[Optional[dict]] = mapped_column(JSON)  # Custom metadata (author, date, tags, etc.)
    language: Mapped[str] = mapped_column(String(10), default="en")

    # Processing status
    processing_status: Mapped[str] = mapped_column(String(50), default="pending")  # pending, processing, completed, failed
    processing_error: Mapped[Optional[str]] = mapped_column(Text)
    processed_at: Mapped[Optional[datetime]] = mapped_column(DateTime)

    # Statistics
    total_chunks: Mapped[int] = mapped_column(Integer, default=0)
    total_tokens: Mapped[Optional[int]] = mapped_column(Integer)  # Estimated token count

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    knowledge_base: Mapped["KnowledgeBase"] = relationship("KnowledgeBase", back_populates="documents")
    chunks: Mapped[List["DocumentChunk"]] = relationship("DocumentChunk", back_populates="document", cascade="all, delete-orphan")

    # Indexes
    __table_args__ = (
        Index('idx_doc_kb', 'knowledge_base_id'),
        Index('idx_doc_hash', 'content_hash'),
        Index('idx_doc_status', 'processing_status'),
    )


class DocumentChunk(Base):
    """
    Text chunks from documents.
    Each chunk is embedded and stored in the vector database.
    """
    __tablename__ = "document_chunks"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("documents.id"), nullable=False)

    # Chunk content
    content: Mapped[str] = mapped_column(Text, nullable=False)
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)  # Position in document

    # Position in document
    start_char: Mapped[int] = mapped_column(Integer, nullable=False)
    end_char: Mapped[int] = mapped_column(Integer, nullable=False)

    # Embedding
    vector_id: Mapped[Optional[str]] = mapped_column(String(255))  # ID in vector store (Pinecone/Qdrant)
    embedding_model: Mapped[str] = mapped_column(String(100), nullable=False)
    embedding_dimension: Mapped[int] = mapped_column(Integer, default=1536)

    # Vector stored in-row as a JSON array so semantic search is DB-backed and
    # survives restarts (no external vector store required for the default path).
    embedding: Mapped[Optional[list]] = mapped_column(JSON)

    # Metadata
    chunk_metadata: Mapped[Optional[dict]] = mapped_column(JSON)  # Chunk-specific metadata
    token_count: Mapped[Optional[int]] = mapped_column(Integer)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    document: Mapped["Document"] = relationship("Document", back_populates="chunks")

    # Indexes
    __table_args__ = (
        Index('idx_chunk_doc', 'document_id'),
        Index('idx_chunk_vector', 'vector_id'),
        Index('idx_chunk_index', 'document_id', 'chunk_index'),
    )


class AgentKnowledgeBase(Base):
    """
    Many-to-many relationship between agents and knowledge bases.
    Allows agents to access multiple knowledge bases with different priorities.
    """
    __tablename__ = "agent_knowledge_bases"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    agent_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("agents.id"), nullable=False)
    knowledge_base_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("knowledge_bases.id"), nullable=False)

    # Configuration
    priority: Mapped[int] = mapped_column(Integer, default=0)  # Higher priority searched first
    max_results: Mapped[int] = mapped_column(Integer, default=5)  # Max chunks to retrieve
    min_similarity: Mapped[float] = mapped_column(Float, default=0.7)  # Minimum similarity threshold

    # Feature flags
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    auto_inject: Mapped[bool] = mapped_column(Boolean, default=True)  # Auto-inject into prompts

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    agent: Mapped["Agent"] = relationship("Agent", back_populates="agent_knowledge_bases")
    knowledge_base: Mapped["KnowledgeBase"] = relationship("KnowledgeBase", back_populates="agent_knowledge_bases")

    # Indexes
    __table_args__ = (
        Index('idx_akb_agent', 'agent_id'),
        Index('idx_akb_kb', 'knowledge_base_id'),
        Index('idx_akb_priority', 'agent_id', 'priority'),
    )


class SearchQuery(Base):
    """
    Log of search queries for analytics and improvement.
    Helps identify common questions and improve retrieval.
    """
    __tablename__ = "search_queries"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    knowledge_base_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("knowledge_bases.id"), nullable=False)
    agent_id: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid(as_uuid=True), ForeignKey("agents.id"))
    call_id: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid(as_uuid=True), ForeignKey("calls.id"))

    # Query details
    query_text: Mapped[str] = mapped_column(Text, nullable=False)
    query_type: Mapped[str] = mapped_column(String(50), default="semantic")  # semantic, keyword, hybrid

    # Results
    results_count: Mapped[int] = mapped_column(Integer, default=0)
    top_similarity: Mapped[Optional[float]] = mapped_column(Float)  # Best match score
    avg_similarity: Mapped[Optional[float]] = mapped_column(Float)  # Average match score

    # Result IDs (for analysis)
    result_chunk_ids: Mapped[Optional[List[str]]] = mapped_column(JSON)

    # Performance
    query_duration_ms: Mapped[Optional[int]] = mapped_column(Integer)  # Query execution time

    # Feedback (if collected)
    was_helpful: Mapped[Optional[bool]] = mapped_column(Boolean)
    user_feedback: Mapped[Optional[str]] = mapped_column(Text)

    # Timestamp
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Indexes
    __table_args__ = (
        Index('idx_query_kb', 'knowledge_base_id'),
        Index('idx_query_agent', 'agent_id'),
        Index('idx_query_call', 'call_id'),
        Index('idx_query_created', 'created_at'),
    )
