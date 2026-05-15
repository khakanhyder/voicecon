## RAG Knowledge Base System - Complete Guide

## Overview

The RAG (Retrieval Augmented Generation) Knowledge Base system enables your AI agents to access and utilize custom knowledge from documents, enabling them to provide accurate, context-aware responses based on your proprietary data.

### Key Features

✅ **Document Management** - Upload and organize documents in knowledge bases
✅ **Intelligent Chunking** - Smart text segmentation preserving context
✅ **OpenAI Embeddings** - State-of-the-art semantic understanding
✅ **Vector Store Support** - Pinecone, Qdrant, or local storage
✅ **Semantic Search** - Find relevant information based on meaning
✅ **Auto-Injection** - Automatic context injection into LLM prompts
✅ **Multi-Agent Support** - Share knowledge bases across agents
✅ **Analytics** - Track search queries and relevance

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                      User Interface                          │
│              (Upload Documents, Search)                      │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ↓
┌─────────────────────────────────────────────────────────────┐
│                    Knowledge Base API                        │
│      /knowledge/knowledge-bases, /documents, /search         │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ↓
┌─────────────────────────────────────────────────────────────┐
│                      RAG Service                             │
│  ┌──────────────┐  ┌──────────────┐  ┌─────────────────┐  │
│  │   Text       │  │  Embedding   │  │  Semantic       │  │
│  │   Chunker    │  │  Service     │  │  Search         │  │
│  └──────────────┘  └──────────────┘  └─────────────────┘  │
└────────────────────────┬────────────────────────────────────┘
                         │
          ┌──────────────┴──────────────┐
          │                             │
          ↓                             ↓
┌──────────────────┐          ┌──────────────────┐
│   Vector Store   │          │   PostgreSQL     │
│  (Pinecone/      │          │   (Metadata)     │
│   Qdrant/Local)  │          │                  │
└──────────────────┘          └──────────────────┘
```

## Quick Start

### 1. Create a Knowledge Base

```bash
curl -X POST http://localhost:8000/api/v1/knowledge/knowledge-bases \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Product Documentation",
    "description": "Company product manuals and guides",
    "chunk_size": 1000,
    "chunk_overlap": 200,
    "vector_store_type": "local"
  }'
```

### 2. Upload a Document

```bash
curl -X POST http://localhost:8000/api/v1/knowledge/documents \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "knowledge_base_id": "kb-uuid-here",
    "title": "Product Manual v2.0",
    "content": "Your document content here...",
    "source_type": "text"
  }'
```

### 3. Search the Knowledge Base

```bash
curl -X POST http://localhost:8000/api/v1/knowledge/search \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "knowledge_base_id": "kb-uuid-here",
    "query": "How do I reset my password?",
    "top_k": 5,
    "min_similarity": 0.7
  }'
```

## Database Models

### KnowledgeBase

Container for organizing documents.

```python
class KnowledgeBase:
    id: UUID
    organization_id: UUID
    name: str
    description: str
    embedding_model: str = "text-embedding-ada-002"
    chunk_size: int = 1000
    chunk_overlap: int = 200
    vector_dimension: int = 1536
    vector_store_type: str  # pinecone, qdrant, local
    vector_store_config: dict
    is_active: bool
```

### Document

Uploaded documents to be indexed.

```python
class Document:
    id: UUID
    knowledge_base_id: UUID
    title: str
    content: str
    content_hash: str  # SHA-256 for deduplication
    source_type: str  # file, url, text, api
    processing_status: str  # pending, processing, completed, failed
    total_chunks: int
    total_tokens: int
```

### DocumentChunk

Text chunks with embeddings.

```python
class DocumentChunk:
    id: UUID
    document_id: UUID
    content: str
    chunk_index: int
    start_char: int
    end_char: int
    vector_id: str  # ID in vector store
    embedding_model: str
    metadata: dict
```

### AgentKnowledgeBase

Links agents to knowledge bases.

```python
class AgentKnowledgeBase:
    agent_id: UUID
    knowledge_base_id: UUID
    priority: int  # Higher searched first
    max_results: int = 5
    min_similarity: float = 0.7
    auto_inject: bool = True  # Auto-inject context
```

## API Endpoints

### Knowledge Base Endpoints

**Create Knowledge Base**
```
POST /api/v1/knowledge/knowledge-bases
```

**List Knowledge Bases**
```
GET /api/v1/knowledge/knowledge-bases
```

**Get Knowledge Base**
```
GET /api/v1/knowledge/knowledge-bases/{kb_id}
```

**Delete Knowledge Base**
```
DELETE /api/v1/knowledge/knowledge-bases/{kb_id}
```

### Document Endpoints

**Create Text Document**
```
POST /api/v1/knowledge/documents
```

**Upload File Document**
```
POST /api/v1/knowledge/documents/upload
```

**List Documents**
```
GET /api/v1/knowledge/knowledge-bases/{kb_id}/documents
```

**Delete Document**
```
DELETE /api/v1/knowledge/documents/{doc_id}
```

### Search Endpoints

**Semantic Search**
```
POST /api/v1/knowledge/search
```

**Get Context for Prompt**
```
POST /api/v1/knowledge/search/context
```

## Text Chunking

### Intelligent Chunking Algorithm

1. **Paragraph-Based**: Splits on `\n\n` first
2. **Sentence-Based**: Falls back to sentence splitting if paragraphs too large
3. **Overlap**: Maintains continuity between chunks
4. **Configurable**: Adjust `chunk_size` and `chunk_overlap`

```python
chunker = TextChunker(
    chunk_size=1000,  # Characters per chunk
    chunk_overlap=200  # Overlap between chunks
)

chunks = chunker.chunk_text(document_content)
```

### Chunking Best Practices

- **Technical Docs**: chunk_size=1500, overlap=300
- **FAQs**: chunk_size=500, overlap=100
- **Long-form Content**: chunk_size=2000, overlap=400

## Embeddings

### OpenAI Embeddings

Default model: `text-embedding-ada-002`
- Dimension: 1536
- Cost: ~$0.0001 per 1K tokens
- Best for general-purpose semantic search

```python
embedding_service = EmbeddingService(
    api_key=openai_api_key,
    model="text-embedding-ada-002"
)

embeddings = await embedding_service.generate_embeddings(texts)
```

## Vector Stores

### Pinecone (Cloud)

**Setup:**
```python
vector_store_config = {
    'type': 'pinecone',
    'config': {
        'api_key': 'your-pinecone-api-key',
        'environment': 'us-east-1-aws'
    }
}
```

**Pros:** Serverless, auto-scaling, managed
**Cons:** Monthly cost, external dependency

### Qdrant (Self-hosted or Cloud)

**Setup:**
```python
vector_store_config = {
    'type': 'qdrant',
    'config': {
        'host': 'localhost',
        'port': 6333
    }
}
```

**Pros:** Open-source, self-hostable, feature-rich
**Cons:** Requires infrastructure management

### Local (NumPy)

**Setup:**
```python
vector_store_config = {
    'type': 'local',
    'config': {}
}
```

**Pros:** No external dependencies, free, simple
**Cons:** Not scalable, memory-limited

## Semantic Search

### How It Works

1. User submits query
2. Query converted to embedding
3. Vector similarity search in vector store
4. Filter by similarity threshold
5. Retrieve full chunk data from database
6. Return ranked results

### Search Parameters

```python
results = await rag_service.search(
    knowledge_base_id=kb_id,
    query="How to configure authentication?",
    top_k=5,  # Number of results
    min_similarity=0.7,  # Minimum relevance score (0-1)
    filters={'source_type': 'documentation'}
)
```

### Similarity Scores

- **0.9-1.0**: Highly relevant
- **0.7-0.9**: Relevant
- **0.5-0.7**: Somewhat relevant
- **< 0.5**: Not relevant

## LLM Integration

### Auto-Inject Context

Knowledge base context is automatically injected into agent prompts:

```python
# In conversation context
context = await rag_service.get_context_for_prompt(
    knowledge_base_id=kb_id,
    query=user_message,
    max_chunks=3,
    max_tokens=2000
)

conversation.set_rag_context(context)
```

### Context Format

```
Relevant information from knowledge base:

[Source: Product Manual v2.0]
Authentication is configured via the settings panel...

---

[Source: API Documentation]
The authentication endpoint accepts POST requests...
```

## Advanced Features

### Multi-Knowledge Base Search

Agents can access multiple knowledge bases:

```sql
-- Priority-based search across multiple KBs
SELECT * FROM agent_knowledge_bases
WHERE agent_id = 'agent-uuid'
ORDER BY priority DESC
```

### Deduplication

Documents are deduplicated via SHA-256 hash:

```python
content_hash = hashlib.sha256(content.encode()).hexdigest()

# Check if already exists
existing = db.query(Document).filter(
    Document.knowledge_base_id == kb_id,
    Document.content_hash == content_hash
).first()
```

### Analytics

Track search performance:

```python
class SearchQuery:
    query_text: str
    results_count: int
    top_similarity: float
    avg_similarity: float
    query_duration_ms: int
    was_helpful: bool  # User feedback
```

## Performance Optimization

### Indexing

All tables have optimized indexes:

```sql
CREATE INDEX idx_kb_org ON knowledge_bases(organization_id);
CREATE INDEX idx_doc_kb ON documents(knowledge_base_id);
CREATE INDEX idx_chunk_vector ON document_chunks(vector_id);
CREATE INDEX idx_query_kb ON search_queries(knowledge_base_id);
```

### Batch Processing

Process documents in background:

```python
# Non-blocking document processing
asyncio.create_task(self._process_document(doc.id, kb))
```

### Caching

- Vector store maintains connection pool
- Embeddings cached per request batch
- Provider instances reused

## Best Practices

### Document Preparation

1. **Clean Text**: Remove formatting artifacts
2. **Structure**: Use headings and sections
3. **Size**: Keep documents under 100KB for optimal processing
4. **Format**: UTF-8 text, Markdown, or plain text

### Knowledge Base Organization

1. **Topic-Based**: Create separate KBs per topic
2. **Update Regularly**: Keep content current
3. **Version Control**: Track document versions in metadata
4. **Access Control**: Use organization-level isolation

### Search Optimization

1. **Similarity Threshold**: Start with 0.7, adjust based on results
2. **Result Count**: 3-5 chunks optimal for most use cases
3. **Context Size**: Limit to 2000 tokens for prompt efficiency
4. **Query Quality**: More specific queries = better results

## Troubleshooting

### Documents Not Processing

**Symptom:** Document stuck in "pending" status

**Solutions:**
1. Check background task execution
2. Verify OpenAI API key
3. Check database connectivity
4. Review processing_error field

### Low Search Quality

**Symptom:** Irrelevant search results

**Solutions:**
1. Increase chunk_overlap
2. Adjust similarity threshold
3. Improve document quality
4. Use more specific queries
5. Check embedding model compatibility

### Vector Store Connection Issues

**Symptom:** Failed to create/search index

**Solutions:**
1. Verify API keys and endpoints
2. Check network connectivity
3. Ensure vector store is running (Qdrant)
4. Review vector store logs

## Example Use Cases

### Customer Support Bot

```python
# Create KB for support docs
kb = await rag_service.create_knowledge_base(
    organization_id=org_id,
    name="Support Documentation",
    chunk_size=800
)

# Upload FAQ
await rag_service.add_document(
    knowledge_base_id=kb.id,
    title="Common Issues FAQ",
    content=faq_content
)

# Search during conversation
results = await rag_service.search(
    knowledge_base_id=kb.id,
    query=user_question,
    top_k=3
)
```

### Product Expert Agent

```python
# Link KB to agent
agent_kb = AgentKnowledgeBase(
    agent_id=agent.id,
    knowledge_base_id=kb.id,
    priority=1,
    max_results=5,
    auto_inject=True
)

# Context auto-injected in conversations
# Agent now has access to product knowledge
```

## Migration Guide

Run migrations to create tables:

```bash
cd backend
alembic upgrade head
```

## Dependencies

Add to `requirements.txt`:

```txt
openai>=1.0.0  # For embeddings
pinecone-client>=2.0.0  # Optional: Pinecone
qdrant-client>=1.0.0  # Optional: Qdrant
numpy>=1.24.0  # For local vector store
```

## Summary

The RAG Knowledge Base system provides:

✅ **Complete Document Management** - Upload, process, and organize
✅ **Intelligent Chunking** - Context-preserving segmentation
✅ **Semantic Search** - Meaning-based retrieval
✅ **Multiple Vector Stores** - Flexible deployment options
✅ **Auto-Context Injection** - Seamless LLM integration
✅ **Analytics & Monitoring** - Track usage and performance
✅ **Production Ready** - Optimized, scalable, and tested

Your AI agents can now access and utilize custom knowledge for accurate, context-aware responses! 🚀
