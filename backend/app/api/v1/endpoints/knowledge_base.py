"""
Knowledge Base API Endpoints

Endpoints for managing knowledge bases, documents, and semantic search.
"""
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List, Optional, Dict, Any
import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.core.dependencies import get_db, get_current_active_user
from app.models.user import User, OrganizationMember


async def get_current_org_id(
    user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> uuid.UUID:
    """Resolve the user's organization id. User has no organization_id column;
    membership lives in organization_members. Falls back to the user id."""
    m = (await db.execute(
        select(OrganizationMember).where(OrganizationMember.user_id == user.id).limit(1)
    )).scalar_one_or_none()
    return m.organization_id if m else user.id
from app.models.knowledge_base import KnowledgeBase as KnowledgeBaseModel, Document as DocumentModel
from app.services.knowledge_base import RAGService
from app.core.config import settings

router = APIRouter()


# Pydantic Schemas
class KnowledgeBaseCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    chunk_size: int = Field(default=1000, ge=100, le=4000)
    chunk_overlap: int = Field(default=200, ge=0, le=1000)
    vector_store_type: str = Field(default="local")  # local, pinecone, qdrant
    vector_store_config: Optional[Dict[str, Any]] = None


class KnowledgeBaseResponse(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    name: str
    description: Optional[str]
    embedding_model: str
    chunk_size: int
    chunk_overlap: int
    vector_store_type: str
    is_active: bool
    created_at: datetime
    updated_at: datetime
    document_count: int = 0

    class Config:
        from_attributes = True


class DocumentCreate(BaseModel):
    knowledge_base_id: uuid.UUID
    title: str = Field(..., min_length=1, max_length=500)
    content: str = Field(..., min_length=1)
    source_type: str = Field(default="text")  # text, file, url, api
    source_url: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class DocumentResponse(BaseModel):
    id: uuid.UUID
    knowledge_base_id: uuid.UUID
    title: str
    source_type: str
    source_url: Optional[str]
    file_type: Optional[str]
    file_size: Optional[int]
    processing_status: str
    processing_error: Optional[str]
    total_chunks: int
    total_tokens: Optional[int]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class SearchRequest(BaseModel):
    query: str = Field(..., min_length=1)
    knowledge_base_id: uuid.UUID
    top_k: int = Field(default=5, ge=1, le=20)
    min_similarity: float = Field(default=0.7, ge=0.0, le=1.0)
    filters: Optional[Dict[str, Any]] = None


class SearchResult(BaseModel):
    chunk_id: str
    content: str
    document_id: str
    document_title: str
    chunk_index: int
    similarity: float
    metadata: Dict[str, Any]


class SearchResponse(BaseModel):
    query: str
    results: List[SearchResult]
    total_results: int


# Helper function to get RAG service
def get_rag_service(db: AsyncSession = Depends(get_db)) -> RAGService:
    """Get RAG service instance."""
    return RAGService(
        db=db,
        openai_api_key=settings.OPENAI_API_KEY,
        vector_store_config={
            'type': 'local',  # Can be configured via environment
            'config': {}
        }
    )


# Knowledge Base Endpoints

@router.post("/knowledge-bases", response_model=KnowledgeBaseResponse, status_code=201)
async def create_knowledge_base(
    kb_create: KnowledgeBaseCreate,
    current_user: User = Depends(get_current_active_user),
    org_id: uuid.UUID = Depends(get_current_org_id),
    rag_service: RAGService = Depends(get_rag_service)
):
    """
    Create a new knowledge base.

    Creates a knowledge base container for organizing documents.
    Automatically creates a vector store index.
    """
    try:
        kb = await rag_service.create_knowledge_base(
            organization_id=org_id,
            name=kb_create.name,
            description=kb_create.description,
            chunk_size=kb_create.chunk_size,
            chunk_overlap=kb_create.chunk_overlap,
            vector_store_type=kb_create.vector_store_type,
            vector_store_config=kb_create.vector_store_config or {}
        )

        return KnowledgeBaseResponse(
            **kb.__dict__,
            document_count=0
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/knowledge-bases", response_model=List[KnowledgeBaseResponse])
async def list_knowledge_bases(
    current_user: User = Depends(get_current_active_user),
    org_id: uuid.UUID = Depends(get_current_org_id),
    db: AsyncSession = Depends(get_db)
):
    """
    List all knowledge bases for the organization.
    """
    from sqlalchemy import select, func
    from app.models.knowledge_base import Document

    result = await db.execute(
        select(KnowledgeBaseModel).where(
            KnowledgeBaseModel.organization_id == org_id
        ).order_by(KnowledgeBaseModel.created_at.desc())
    )
    knowledge_bases = result.scalars().all()

    # Get document counts
    response_list = []
    for kb in knowledge_bases:
        count_result = await db.execute(
            select(func.count(Document.id)).where(Document.knowledge_base_id == kb.id)
        )
        doc_count = count_result.scalar() or 0

        response_list.append(
            KnowledgeBaseResponse(
                **kb.__dict__,
                document_count=doc_count
            )
        )

    return response_list


@router.get("/knowledge-bases/{kb_id}", response_model=KnowledgeBaseResponse)
async def get_knowledge_base(
    kb_id: uuid.UUID,
    current_user: User = Depends(get_current_active_user),
    org_id: uuid.UUID = Depends(get_current_org_id),
    db: AsyncSession = Depends(get_db)
):
    """
    Get a specific knowledge base by ID.
    """
    from sqlalchemy import select, func
    from app.models.knowledge_base import Document

    result = await db.execute(
        select(KnowledgeBaseModel).where(
            KnowledgeBaseModel.id == kb_id,
            KnowledgeBaseModel.organization_id == org_id
        )
    )
    kb = result.scalar_one_or_none()

    if not kb:
        raise HTTPException(status_code=404, detail="Knowledge base not found")

    # Get document count
    count_result = await db.execute(
        select(func.count(Document.id)).where(Document.knowledge_base_id == kb.id)
    )
    doc_count = count_result.scalar() or 0

    return KnowledgeBaseResponse(
        **kb.__dict__,
        document_count=doc_count
    )


@router.delete("/knowledge-bases/{kb_id}", status_code=204)
async def delete_knowledge_base(
    kb_id: uuid.UUID,
    current_user: User = Depends(get_current_active_user),
    org_id: uuid.UUID = Depends(get_current_org_id),
    db: AsyncSession = Depends(get_db)
):
    """
    Delete a knowledge base and all its documents.
    """
    from sqlalchemy import select

    result = await db.execute(
        select(KnowledgeBaseModel).where(
            KnowledgeBaseModel.id == kb_id,
            KnowledgeBaseModel.organization_id == org_id
        )
    )
    kb = result.scalar_one_or_none()

    if not kb:
        raise HTTPException(status_code=404, detail="Knowledge base not found")

    # Delete index from vector store
    # TODO: Implement vector store cleanup

    await db.delete(kb)
    await db.commit()

    return None


# Document Endpoints

@router.post("/documents", response_model=DocumentResponse, status_code=201)
async def create_document(
    doc_create: DocumentCreate,
    current_user: User = Depends(get_current_active_user),
    org_id: uuid.UUID = Depends(get_current_org_id),
    rag_service: RAGService = Depends(get_rag_service),
    db: AsyncSession = Depends(get_db)
):
    """
    Add a text document to a knowledge base.

    The document will be automatically chunked, embedded, and indexed.
    """
    # Verify knowledge base belongs to user's organization
    from sqlalchemy import select

    kb_result = await db.execute(
        select(KnowledgeBaseModel).where(
            KnowledgeBaseModel.id == doc_create.knowledge_base_id,
            KnowledgeBaseModel.organization_id == org_id
        )
    )
    kb = kb_result.scalar_one_or_none()

    if not kb:
        raise HTTPException(status_code=404, detail="Knowledge base not found")

    try:
        doc = await rag_service.add_document(
            knowledge_base_id=doc_create.knowledge_base_id,
            title=doc_create.title,
            content=doc_create.content,
            source_type=doc_create.source_type,
            source_url=doc_create.source_url,
            metadata=doc_create.metadata or {}
        )

        return DocumentResponse(**doc.__dict__)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/documents/upload", response_model=DocumentResponse, status_code=201)
async def upload_document(
    knowledge_base_id: uuid.UUID = Form(...),
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_active_user),
    org_id: uuid.UUID = Depends(get_current_org_id),
    rag_service: RAGService = Depends(get_rag_service),
    db: AsyncSession = Depends(get_db)
):
    """
    Upload a file document to a knowledge base.

    Supported formats: txt, pdf, docx, md, json
    """
    # Verify knowledge base
    from sqlalchemy import select

    kb_result = await db.execute(
        select(KnowledgeBaseModel).where(
            KnowledgeBaseModel.id == knowledge_base_id,
            KnowledgeBaseModel.organization_id == org_id
        )
    )
    kb = kb_result.scalar_one_or_none()

    if not kb:
        raise HTTPException(status_code=404, detail="Knowledge base not found")

    # Read file content
    content = await file.read()

    # Extract text based on file type
    try:
        if file.filename.endswith('.txt') or file.filename.endswith('.md'):
            text_content = content.decode('utf-8')
        elif file.filename.endswith('.pdf'):
            # TODO: Implement PDF parsing with PyPDF2 or pdfplumber
            raise HTTPException(status_code=400, detail="PDF parsing not yet implemented")
        elif file.filename.endswith('.docx'):
            # TODO: Implement DOCX parsing with python-docx
            raise HTTPException(status_code=400, detail="DOCX parsing not yet implemented")
        else:
            raise HTTPException(status_code=400, detail="Unsupported file format")

        doc = await rag_service.add_document(
            knowledge_base_id=knowledge_base_id,
            title=file.filename,
            content=text_content,
            source_type="file",
            file_type=file.content_type,
            file_size=len(content)
        )

        return DocumentResponse(**doc.__dict__)

    except UnicodeDecodeError:
        raise HTTPException(status_code=400, detail="File encoding error. Please upload UTF-8 encoded files.")
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/knowledge-bases/{kb_id}/documents", response_model=List[DocumentResponse])
async def list_documents(
    kb_id: uuid.UUID,
    current_user: User = Depends(get_current_active_user),
    org_id: uuid.UUID = Depends(get_current_org_id),
    db: AsyncSession = Depends(get_db)
):
    """
    List all documents in a knowledge base.
    """
    from sqlalchemy import select

    # Verify knowledge base
    kb_result = await db.execute(
        select(KnowledgeBaseModel).where(
            KnowledgeBaseModel.id == kb_id,
            KnowledgeBaseModel.organization_id == org_id
        )
    )
    kb = kb_result.scalar_one_or_none()

    if not kb:
        raise HTTPException(status_code=404, detail="Knowledge base not found")

    # Get documents
    result = await db.execute(
        select(DocumentModel).where(
            DocumentModel.knowledge_base_id == kb_id
        ).order_by(DocumentModel.created_at.desc())
    )
    documents = result.scalars().all()

    return [DocumentResponse(**doc.__dict__) for doc in documents]


@router.delete("/documents/{doc_id}", status_code=204)
async def delete_document(
    doc_id: uuid.UUID,
    current_user: User = Depends(get_current_active_user),
    org_id: uuid.UUID = Depends(get_current_org_id),
    rag_service: RAGService = Depends(get_rag_service),
    db: AsyncSession = Depends(get_db)
):
    """
    Delete a document and all its chunks.
    """
    from sqlalchemy import select

    # Verify document belongs to user's organization
    doc_result = await db.execute(
        select(DocumentModel).where(DocumentModel.id == doc_id)
    )
    doc = doc_result.scalar_one_or_none()

    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    # Verify knowledge base ownership
    kb_result = await db.execute(
        select(KnowledgeBaseModel).where(
            KnowledgeBaseModel.id == doc.knowledge_base_id,
            KnowledgeBaseModel.organization_id == org_id
        )
    )
    kb = kb_result.scalar_one_or_none()

    if not kb:
        raise HTTPException(status_code=403, detail="Access denied")

    # Delete document
    success = await rag_service.delete_document(doc_id)

    if not success:
        raise HTTPException(status_code=500, detail="Failed to delete document")

    return None


# Search Endpoints

@router.post("/search", response_model=SearchResponse)
async def search_knowledge_base(
    search_req: SearchRequest,
    current_user: User = Depends(get_current_active_user),
    org_id: uuid.UUID = Depends(get_current_org_id),
    rag_service: RAGService = Depends(get_rag_service),
    db: AsyncSession = Depends(get_db)
):
    """
    Semantic search across a knowledge base.

    Uses embeddings to find relevant content based on semantic similarity.
    """
    from sqlalchemy import select

    # Verify knowledge base
    kb_result = await db.execute(
        select(KnowledgeBaseModel).where(
            KnowledgeBaseModel.id == search_req.knowledge_base_id,
            KnowledgeBaseModel.organization_id == org_id
        )
    )
    kb = kb_result.scalar_one_or_none()

    if not kb:
        raise HTTPException(status_code=404, detail="Knowledge base not found")

    # Perform search
    results = await rag_service.search(
        knowledge_base_id=search_req.knowledge_base_id,
        query=search_req.query,
        top_k=search_req.top_k,
        min_similarity=search_req.min_similarity,
        filters=search_req.filters
    )

    return SearchResponse(
        query=search_req.query,
        results=[SearchResult(**r) for r in results],
        total_results=len(results)
    )


@router.post("/search/context", response_model=Dict[str, str])
async def get_search_context(
    search_req: SearchRequest,
    max_tokens: int = 2000,
    current_user: User = Depends(get_current_active_user),
    org_id: uuid.UUID = Depends(get_current_org_id),
    rag_service: RAGService = Depends(get_rag_service),
    db: AsyncSession = Depends(get_db)
):
    """
    Get formatted context for LLM prompt injection.

    Returns a context string ready to be injected into prompts.
    """
    from sqlalchemy import select

    # Verify knowledge base
    kb_result = await db.execute(
        select(KnowledgeBaseModel).where(
            KnowledgeBaseModel.id == search_req.knowledge_base_id,
            KnowledgeBaseModel.organization_id == org_id
        )
    )
    kb = kb_result.scalar_one_or_none()

    if not kb:
        raise HTTPException(status_code=404, detail="Knowledge base not found")

    # Get context
    context = await rag_service.get_context_for_prompt(
        knowledge_base_id=search_req.knowledge_base_id,
        query=search_req.query,
        max_chunks=search_req.top_k,
        max_tokens=max_tokens
    )

    return {
        "context": context,
        "query": search_req.query
    }
