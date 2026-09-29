"""
The knowledge base must work whichever LLM provider an agent uses.

Embeddings (semantic search) come from OpenAI for every agent — Anthropic has
no embeddings API — so without a working OpenAI key or credits, uploads used
to fail outright and every lookup came back empty: the agent answered without
its documents. Search now falls back to keyword ranking, and uploads keep
their chunks for it, so neither depends on any provider.
"""
import types
import uuid

import pytest

import app.services.knowledge_base.rag_service as rag

KB_ID = str(uuid.uuid4())
FEE = "Consultation fee: 3000 rupees. Payment by cash or card."
HOURS = "Opening hours: Monday to Saturday, 9am to 5pm. Closed on Sundays."
PARKING = "Free parking is available behind the clinic building."


def _chunk(content, embedding=None):
    return types.SimpleNamespace(
        id=uuid.uuid4(), content=content, embedding=embedding,
        document_id=uuid.uuid4(), chunk_index=0,
    )


class _DB:
    def __init__(self, chunks):
        self.rows = [(c, "Clinic Guide") for c in chunks]

    async def execute(self, *_a, **_k):
        return types.SimpleNamespace(all=lambda: self.rows)


def _embeddings(monkeypatch, vector=None, error=None):
    calls = []

    async def generate_embedding(self, text):
        calls.append(text)
        if error:
            raise error
        return vector

    monkeypatch.setattr(rag.EmbeddingService, "generate_embedding", generate_embedding)
    return calls


@pytest.mark.asyncio
async def test_search_falls_back_to_keywords_when_openai_is_unavailable(monkeypatch):
    _embeddings(monkeypatch, error=RuntimeError("429 You have no credits remaining"))
    db = _DB([_chunk(HOURS, [0.1, 0.2]), _chunk(FEE, [0.3, 0.4]), _chunk(PARKING, [0.5, 0.6])])

    hits = await rag.search_knowledge_base_db(db, KB_ID, "How much is a consultation?", api_key="sk-no-credits")

    assert hits[0]["content"] == FEE
    assert hits[0]["match"] == "keyword"


@pytest.mark.asyncio
async def test_search_without_any_openai_key_uses_keywords_and_never_calls_openai(monkeypatch):
    calls = _embeddings(monkeypatch, vector=[1.0, 0.0])
    db = _DB([_chunk(FEE, [0.3, 0.4]), _chunk(HOURS, [0.1, 0.2])])

    hits = await rag.search_knowledge_base_db(db, KB_ID, "When are you open on Saturday?", api_key=None)

    assert calls == []
    assert [h["content"] for h in hits] == [HOURS]


@pytest.mark.asyncio
async def test_semantic_search_is_still_used_when_openai_works(monkeypatch):
    _embeddings(monkeypatch, vector=[1.0, 0.0])
    db = _DB([_chunk(PARKING, [0.0, 1.0]), _chunk(FEE, [1.0, 0.0])])

    hits = await rag.search_knowledge_base_db(db, KB_ID, "what does it cost to see the doctor", api_key="sk-live")

    assert hits[0]["content"] == FEE and hits[0]["match"] == "semantic"


@pytest.mark.asyncio
async def test_chunks_indexed_during_an_outage_are_found_once_openai_is_back(monkeypatch):
    """Semantic scores for embedded chunks, keywords for the ones without."""
    _embeddings(monkeypatch, vector=[1.0, 0.0])
    db = _DB([_chunk(HOURS, [0.0, 1.0]), _chunk(FEE, None)])

    hits = await rag.search_knowledge_base_db(db, KB_ID, "consultation fee", api_key="sk-live")

    assert {h["content"]: h["match"] for h in hits}[FEE] == "keyword"


@pytest.mark.asyncio
async def test_an_unrelated_question_finds_nothing(monkeypatch):
    _embeddings(monkeypatch, error=RuntimeError("no credits"))
    db = _DB([_chunk(FEE, [0.3, 0.4]), _chunk(HOURS, [0.1, 0.2])])

    assert await rag.search_knowledge_base_db(db, KB_ID, "What is the weather in Paris?", api_key="sk") == []


def test_keyword_scores_weigh_rare_words_and_fold_plurals():
    scores = rag._keyword_scores("what are the fees for a consultation", [FEE, HOURS, PARKING])
    assert scores[0] == 1.0 and scores[1] == 0.0 and scores[2] == 0.0


@pytest.mark.asyncio
async def test_a_document_uploaded_during_an_outage_is_kept_for_keyword_search(monkeypatch):
    """Uploads used to be marked "failed" with nothing saved."""
    doc = types.SimpleNamespace(
        id=uuid.uuid4(), content=f"{FEE}\n\n{HOURS}", title="Clinic Guide", source_type="text",
        processing_status="pending", processing_error=None, total_chunks=0, total_tokens=0, processed_at=None,
    )
    kb = types.SimpleNamespace(id=uuid.uuid4(), chunk_size=1000, chunk_overlap=100)
    added, upserts = [], []

    class _DocDB:
        async def execute(self, *_a, **_k):
            return types.SimpleNamespace(scalar_one_or_none=lambda: doc)

        def add(self, obj):
            added.append(obj)

        async def commit(self):
            pass

    async def no_embeddings(self, texts):
        raise RuntimeError("429 You have no credits remaining")

    class _Store:
        async def upsert_vectors(self, **kwargs):
            upserts.append(kwargs)

    monkeypatch.setattr(rag.EmbeddingService, "generate_embeddings", no_embeddings)
    service = rag.RAGService.__new__(rag.RAGService)
    service.db, service.vector_store = _DocDB(), _Store()
    service.embedding_service = rag.EmbeddingService(api_key="sk-no-credits")

    await service._process_document(doc.id, kb)

    assert doc.processing_status == "completed"
    assert "keyword search only" in doc.processing_error
    assert added and all(c.embedding is None and c.content for c in added)
    assert upserts == []  # nothing to put in the vector index
