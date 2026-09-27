"""
Knowledge base passages for one turn of an agent conversation.

Shared by the website chat widget and the browser voice test
(``POST /agents/{id}/respond``) so both answer from the same documents with
the same retrieval settings. The phone pipeline (``voice_session``) has its
own equivalent that reads the same ``AgentKnowledgeBase`` links.
"""
import logging
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.agent import Agent

logger = logging.getLogger(__name__)

# Passages handed to the model per turn, across all attached knowledge bases.
MAX_PASSAGES = 5


async def get_agent_kb_context(db: AsyncSession, agent: Agent, query: str) -> Optional[str]:
    """
    Retrieve relevant knowledge base chunks, best-effort.

    Any failure (no KB, no embeddings, provider down) degrades to no context
    rather than breaking the reply.
    """
    if not query or not query.strip():
        return None
    try:
        from app.core.config import settings
        from app.models.knowledge_base import AgentKnowledgeBase
        from app.services.knowledge_base.rag_service import search_knowledge_base_db

        # Primary source: knowledge bases attached via the agent's Knowledge
        # tab (the AgentKnowledgeBase table). This is the same set the voice
        # agent uses, so chat and calls stay in sync.
        links = (
            await db.execute(
                select(AgentKnowledgeBase)
                .where(
                    AgentKnowledgeBase.agent_id == agent.id,
                    AgentKnowledgeBase.is_active == True,  # noqa: E712
                    AgentKnowledgeBase.auto_inject == True,  # noqa: E712
                )
                .order_by(AgentKnowledgeBase.priority.desc())
            )
        ).scalars().all()

        kb_targets = [
            (str(l.knowledge_base_id), l.max_results or 4, l.min_similarity or 0.2)
            for l in links
        ]

        # Fall back to the legacy single-KB config field if nothing is
        # attached the new way, so older agents keep working.
        if not kb_targets:
            config = agent.knowledge_base_config or {}
            legacy_id = config.get("knowledge_base_id") or config.get("id")
            if legacy_id:
                kb_targets = [(str(legacy_id), 4, 0.2)]

        if not kb_targets:
            return None

        passages = []
        for kb_id, top_k, min_sim in kb_targets:
            chunks = await search_knowledge_base_db(
                db=db,
                knowledge_base_id=kb_id,
                query=query,
                api_key=settings.OPENAI_API_KEY,
                top_k=top_k,
                min_similarity=min_sim,
            )
            passages.extend(c.get("content", "") for c in chunks if c.get("content"))

        if not passages:
            return None
        return "\n\n".join(passages[:MAX_PASSAGES])
    except Exception as e:
        logger.debug(f"Knowledge base lookup skipped: {e}")
        return None
