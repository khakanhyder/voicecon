"""
RAG (Retrieval Augmented Generation) Service

Handles document processing, chunking, embedding generation,
and semantic search for knowledge base queries.
"""
import hashlib
import logging
import re
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime
import uuid
import asyncio

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_

from app.models.knowledge_base import (
    KnowledgeBase, Document, DocumentChunk,
    AgentKnowledgeBase, SearchQuery
)
from app.services.knowledge_base.vector_store import get_vector_store, VectorStore

logger = logging.getLogger(__name__)


class TextChunker:
    """
    Intelligent text chunking with overlap.
    Preserves sentence and paragraph boundaries when possible.
    """

    def __init__(self, chunk_size: int = 1000, chunk_overlap: int = 200):
        """
        Initialize chunker.

        Args:
            chunk_size: Target size of each chunk in characters
            chunk_overlap: Overlap between consecutive chunks
        """
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

    def chunk_text(self, text: str) -> List[Tuple[str, int, int]]:
        """
        Split text into overlapping chunks.

        Returns:
            List of (chunk_text, start_char, end_char) tuples
        """
        chunks = []

        # First, try to split by paragraphs
        paragraphs = text.split('\n\n')
        current_chunk = ""
        current_start = 0

        for para in paragraphs:
            # If adding this paragraph exceeds chunk size
            if len(current_chunk) + len(para) + 2 > self.chunk_size and current_chunk:
                # Save current chunk
                chunks.append((
                    current_chunk.strip(),
                    current_start,
                    current_start + len(current_chunk)
                ))

                # Start new chunk with overlap
                overlap_start = max(0, len(current_chunk) - self.chunk_overlap)
                current_chunk = current_chunk[overlap_start:] + "\n\n" + para
                current_start = current_start + overlap_start
            else:
                if current_chunk:
                    current_chunk += "\n\n" + para
                else:
                    current_chunk = para

        # Add final chunk
        if current_chunk:
            chunks.append((
                current_chunk.strip(),
                current_start,
                current_start + len(current_chunk)
            ))

        # If no paragraphs, fall back to sentence-based chunking
        if len(chunks) == 0 or all(len(c[0]) > self.chunk_size * 1.5 for c in chunks):
            chunks = self._chunk_by_sentences(text)

        return chunks

    def _chunk_by_sentences(self, text: str) -> List[Tuple[str, int, int]]:
        """Chunk text by sentences when paragraph chunking fails."""
        # Simple sentence splitter (can be improved with NLTK)
        sentences = re.split(r'(?<=[.!?])\s+', text)

        chunks = []
        current_chunk = ""
        current_start = 0
        current_pos = 0

        for sentence in sentences:
            if len(current_chunk) + len(sentence) + 1 > self.chunk_size and current_chunk:
                # Save current chunk
                chunks.append((
                    current_chunk.strip(),
                    current_start,
                    current_pos
                ))

                # Start new chunk with overlap
                overlap_start = max(0, len(current_chunk) - self.chunk_overlap)
                current_chunk = current_chunk[overlap_start:] + " " + sentence
                current_start = current_pos - (len(current_chunk) - len(sentence) - 1)
            else:
                if current_chunk:
                    current_chunk += " " + sentence
                else:
                    current_chunk = sentence
                    current_start = current_pos

            current_pos += len(sentence) + 1

        # Add final chunk
        if current_chunk:
            chunks.append((
                current_chunk.strip(),
                current_start,
                current_pos
            ))

        return chunks


class EmbeddingService:
    """
    Generate embeddings using OpenAI API.
    Can be extended to support other providers.
    """

    def __init__(self, api_key: str, model: str = "text-embedding-ada-002"):
        """
        Initialize embedding service.

        Args:
            api_key: OpenAI API key
            model: Embedding model to use
        """
        self.api_key = api_key
        self.model = model

    async def generate_embeddings(self, texts: List[str]) -> List[List[float]]:
        """
        Generate embeddings for a list of texts.

        Args:
            texts: List of text strings

        Returns:
            List of embedding vectors
        """
        try:
            import openai
            openai.api_key = self.api_key

            # OpenAI embeddings API
            response = await asyncio.to_thread(
                openai.Embedding.create,
                input=texts,
                model=self.model
            )

            embeddings = [item['embedding'] for item in response['data']]
            logger.info(f"Generated {len(embeddings)} embeddings")
            return embeddings

        except ImportError:
            raise ImportError("OpenAI SDK not installed. Run: pip install openai")
        except Exception as e:
            logger.error(f"Failed to generate embeddings: {e}")
            raise

    async def generate_embedding(self, text: str) -> List[float]:
        """Generate embedding for a single text."""
        embeddings = await self.generate_embeddings([text])
        return embeddings[0] if embeddings else []


class RAGService:
    """
    Main RAG service for knowledge base operations.
    """

    def __init__(
        self,
        db: AsyncSession,
        openai_api_key: str,
        vector_store_config: Optional[Dict[str, Any]] = None
    ):
        """
        Initialize RAG service.

        Args:
            db: Database session
            openai_api_key: OpenAI API key for embeddings
            vector_store_config: Configuration for vector store
        """
        self.db = db
        self.embedding_service = EmbeddingService(api_key=openai_api_key)
        self.chunker = TextChunker()

        # Initialize vector store (default to local for dev)
        if vector_store_config is None:
            vector_store_config = {'type': 'local', 'config': {}}

        self.vector_store = get_vector_store(
            store_type=vector_store_config['type'],
            config=vector_store_config.get('config', {})
        )

    async def create_knowledge_base(
        self,
        organization_id: uuid.UUID,
        name: str,
        description: Optional[str] = None,
        **kwargs
    ) -> KnowledgeBase:
        """
        Create a new knowledge base.

        Args:
            organization_id: Organization ID
            name: Knowledge base name
            description: Optional description
            **kwargs: Additional configuration

        Returns:
            Created KnowledgeBase instance
        """
        kb = KnowledgeBase(
            organization_id=organization_id,
            name=name,
            description=description,
            embedding_model=kwargs.get('embedding_model', 'text-embedding-ada-002'),
            chunk_size=kwargs.get('chunk_size', 1000),
            chunk_overlap=kwargs.get('chunk_overlap', 200),
            vector_store_type=kwargs.get('vector_store_type', 'local'),
            vector_store_config=kwargs.get('vector_store_config', {})
        )

        self.db.add(kb)
        await self.db.commit()
        await self.db.refresh(kb)

        # Create vector store index
        index_name = f"kb_{str(kb.id).replace('-', '_')}"
        await self.vector_store.create_index(
            index_name=index_name,
            dimension=kb.vector_dimension
        )

        logger.info(f"Created knowledge base: {kb.name} ({kb.id})")
        return kb

    async def add_document(
        self,
        knowledge_base_id: uuid.UUID,
        title: str,
        content: str,
        source_type: str = "text",
        metadata: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> Document:
        """
        Add a document to a knowledge base.

        Args:
            knowledge_base_id: Knowledge base ID
            title: Document title
            content: Document content
            source_type: Type of source (file, url, text, api)
            metadata: Optional metadata
            **kwargs: Additional document fields

        Returns:
            Created Document instance
        """
        # Get knowledge base
        kb_result = await self.db.execute(
            select(KnowledgeBase).where(KnowledgeBase.id == knowledge_base_id)
        )
        kb = kb_result.scalar_one_or_none()

        if not kb:
            raise ValueError(f"Knowledge base not found: {knowledge_base_id}")

        # Calculate content hash for deduplication
        content_hash = hashlib.sha256(content.encode()).hexdigest()

        # Check if document already exists
        existing_result = await self.db.execute(
            select(Document).where(
                and_(
                    Document.knowledge_base_id == knowledge_base_id,
                    Document.content_hash == content_hash
                )
            )
        )
        existing_doc = existing_result.scalar_one_or_none()

        if existing_doc:
            logger.warning(f"Document already exists: {title}")
            return existing_doc

        # Create document
        doc = Document(
            knowledge_base_id=knowledge_base_id,
            title=title,
            content=content,
            content_hash=content_hash,
            source_type=source_type,
            source_url=kwargs.get('source_url'),
            file_type=kwargs.get('file_type'),
            file_size=kwargs.get('file_size'),
            metadata=metadata or {},
            language=kwargs.get('language', 'en'),
            processing_status="pending"
        )

        self.db.add(doc)
        await self.db.commit()
        await self.db.refresh(doc)

        # Process document in background
        asyncio.create_task(self._process_document(doc.id, kb))

        logger.info(f"Added document: {title} ({doc.id})")
        return doc

    async def _process_document(self, document_id: uuid.UUID, kb: KnowledgeBase):
        """
        Process document: chunk, embed, and store in vector database.

        Args:
            document_id: Document ID
            kb: Knowledge base instance
        """
        try:
            # Get document
            doc_result = await self.db.execute(
                select(Document).where(Document.id == document_id)
            )
            doc = doc_result.scalar_one_or_none()

            if not doc:
                return

            # Update status
            doc.processing_status = "processing"
            await self.db.commit()

            # Initialize chunker with KB settings
            chunker = TextChunker(
                chunk_size=kb.chunk_size,
                chunk_overlap=kb.chunk_overlap
            )

            # Chunk the document
            chunks_data = chunker.chunk_text(doc.content)
            logger.info(f"Created {len(chunks_data)} chunks for document {doc.id}")

            # Generate embeddings for all chunks
            chunk_texts = [chunk[0] for chunk in chunks_data]
            embeddings = await self.embedding_service.generate_embeddings(chunk_texts)

            # Prepare vector store data
            index_name = f"kb_{str(kb.id).replace('-', '_')}"
            vectors = []

            # Create DocumentChunk records
            for idx, ((chunk_text, start_char, end_char), embedding) in enumerate(zip(chunks_data, embeddings)):
                chunk_id = str(uuid.uuid4())

                # Create database record
                chunk = DocumentChunk(
                    id=uuid.UUID(chunk_id),
                    document_id=document_id,
                    content=chunk_text,
                    chunk_index=idx,
                    start_char=start_char,
                    end_char=end_char,
                    vector_id=chunk_id,
                    embedding_model=kb.embedding_model,
                    embedding_dimension=kb.vector_dimension,
                    metadata={
                        'document_id': str(document_id),
                        'document_title': doc.title,
                        'chunk_index': idx,
                        'source_type': doc.source_type
                    },
                    token_count=len(chunk_text.split())  # Rough estimate
                )

                self.db.add(chunk)

                # Prepare for vector store
                vectors.append((
                    chunk_id,
                    embedding,
                    {
                        'document_id': str(document_id),
                        'document_title': doc.title,
                        'chunk_index': idx,
                        'content': chunk_text[:500]  # Store preview
                    }
                ))

            # Upsert to vector store
            await self.vector_store.upsert_vectors(
                index_name=index_name,
                vectors=vectors
            )

            # Update document
            doc.total_chunks = len(chunks_data)
            doc.total_tokens = sum(c.token_count or 0 for c in doc.chunks)
            doc.processing_status = "completed"
            doc.processed_at = datetime.utcnow()

            await self.db.commit()

            logger.info(f"Successfully processed document {doc.id}")

        except Exception as e:
            logger.error(f"Failed to process document {document_id}: {e}")

            # Update error status
            doc_result = await self.db.execute(
                select(Document).where(Document.id == document_id)
            )
            doc = doc_result.scalar_one_or_none()

            if doc:
                doc.processing_status = "failed"
                doc.processing_error = str(e)
                await self.db.commit()

    async def search(
        self,
        knowledge_base_id: uuid.UUID,
        query: str,
        top_k: int = 5,
        min_similarity: float = 0.7,
        filters: Optional[Dict[str, Any]] = None,
        agent_id: Optional[uuid.UUID] = None,
        call_id: Optional[uuid.UUID] = None
    ) -> List[Dict[str, Any]]:
        """
        Semantic search across knowledge base.

        Args:
            knowledge_base_id: Knowledge base ID
            query: Search query
            top_k: Number of results to return
            min_similarity: Minimum similarity threshold
            filters: Optional metadata filters
            agent_id: Optional agent ID for logging
            call_id: Optional call ID for logging

        Returns:
            List of search results with content and metadata
        """
        start_time = datetime.utcnow()

        try:
            # Get knowledge base
            kb_result = await self.db.execute(
                select(KnowledgeBase).where(KnowledgeBase.id == knowledge_base_id)
            )
            kb = kb_result.scalar_one_or_none()

            if not kb:
                raise ValueError(f"Knowledge base not found: {knowledge_base_id}")

            # Generate query embedding
            query_embedding = await self.embedding_service.generate_embedding(query)

            # Search vector store
            index_name = f"kb_{str(kb.id).replace('-', '_')}"
            vector_results = await self.vector_store.search(
                index_name=index_name,
                query_vector=query_embedding,
                top_k=top_k * 2,  # Get more for filtering
                filter_dict=filters
            )

            # Filter by similarity threshold
            filtered_results = [
                r for r in vector_results
                if r['score'] >= min_similarity
            ][:top_k]

            # Enrich with full chunk data
            results = []
            for result in filtered_results:
                chunk_result = await self.db.execute(
                    select(DocumentChunk).where(
                        DocumentChunk.vector_id == result['id']
                    )
                )
                chunk = chunk_result.scalar_one_or_none()

                if chunk:
                    results.append({
                        'chunk_id': str(chunk.id),
                        'content': chunk.content,
                        'document_id': str(chunk.document_id),
                        'document_title': result['metadata'].get('document_title'),
                        'chunk_index': chunk.chunk_index,
                        'similarity': result['score'],
                        'metadata': chunk.metadata
                    })

            # Log search query
            query_duration = int((datetime.utcnow() - start_time).total_seconds() * 1000)
            await self._log_search_query(
                knowledge_base_id=knowledge_base_id,
                query_text=query,
                results_count=len(results),
                top_similarity=filtered_results[0]['score'] if filtered_results else None,
                avg_similarity=sum(r['score'] for r in filtered_results) / len(filtered_results) if filtered_results else None,
                query_duration_ms=query_duration,
                agent_id=agent_id,
                call_id=call_id
            )

            logger.info(f"Search returned {len(results)} results in {query_duration}ms")
            return results

        except Exception as e:
            logger.error(f"Search failed: {e}")
            return []

    async def _log_search_query(
        self,
        knowledge_base_id: uuid.UUID,
        query_text: str,
        results_count: int,
        top_similarity: Optional[float],
        avg_similarity: Optional[float],
        query_duration_ms: int,
        agent_id: Optional[uuid.UUID] = None,
        call_id: Optional[uuid.UUID] = None
    ):
        """Log search query for analytics."""
        try:
            search_log = SearchQuery(
                knowledge_base_id=knowledge_base_id,
                agent_id=agent_id,
                call_id=call_id,
                query_text=query_text,
                query_type="semantic",
                results_count=results_count,
                top_similarity=top_similarity,
                avg_similarity=avg_similarity,
                query_duration_ms=query_duration_ms
            )

            self.db.add(search_log)
            await self.db.commit()
        except Exception as e:
            logger.error(f"Failed to log search query: {e}")

    async def delete_document(self, document_id: uuid.UUID) -> bool:
        """
        Delete a document and all its chunks.

        Args:
            document_id: Document ID

        Returns:
            True if successful
        """
        try:
            # Get document with knowledge base
            doc_result = await self.db.execute(
                select(Document).where(Document.id == document_id)
            )
            doc = doc_result.scalar_one_or_none()

            if not doc:
                return False

            # Get all chunk vector IDs
            chunks_result = await self.db.execute(
                select(DocumentChunk).where(DocumentChunk.document_id == document_id)
            )
            chunks = chunks_result.scalars().all()

            vector_ids = [c.vector_id for c in chunks if c.vector_id]

            # Delete from vector store
            if vector_ids:
                index_name = f"kb_{str(doc.knowledge_base_id).replace('-', '_')}"
                await self.vector_store.delete_vectors(
                    index_name=index_name,
                    ids=vector_ids
                )

            # Delete from database (chunks deleted via cascade)
            await self.db.delete(doc)
            await self.db.commit()

            logger.info(f"Deleted document {document_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to delete document: {e}")
            return False

    async def get_context_for_prompt(
        self,
        knowledge_base_id: uuid.UUID,
        query: str,
        max_chunks: int = 3,
        max_tokens: int = 2000
    ) -> str:
        """
        Get relevant context to inject into LLM prompt.

        Args:
            knowledge_base_id: Knowledge base ID
            query: User query
            max_chunks: Maximum number of chunks to include
            max_tokens: Maximum total tokens (rough estimate)

        Returns:
            Formatted context string
        """
        results = await self.search(
            knowledge_base_id=knowledge_base_id,
            query=query,
            top_k=max_chunks
        )

        if not results:
            return ""

        # Build context string
        context_parts = []
        total_tokens = 0

        for result in results:
            chunk_tokens = result.get('metadata', {}).get('token_count', len(result['content'].split()))

            if total_tokens + chunk_tokens > max_tokens:
                break

            context_parts.append(
                f"[Source: {result['document_title']}]\n{result['content']}"
            )
            total_tokens += chunk_tokens

        context = "\n\n---\n\n".join(context_parts)

        return f"Relevant information from knowledge base:\n\n{context}"
