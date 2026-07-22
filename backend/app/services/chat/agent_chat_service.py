"""
Agent chat service — the text channel for an agent.

Same brain as the voice path, different mouth: it reuses the agent's system
prompt, knowledge base, and tools (including workflow-backed tools), but the
conversation is written text instead of speech. This is what the chat widget
runs on, and it is deliberately channel-agnostic so anything else that needs a
text turn can call it too.
"""
import json
import logging
from typing import Any, Dict, List, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.agent import Agent
from app.services.function_executor import get_function_executor, sanitize_function_name
from app.services.voice.llm_service import get_llm_service
from app.services.voice.providers.base import ChatMessage

logger = logging.getLogger(__name__)

# One tool per turn, capped so a misbehaving model can't loop forever.
MAX_TOOL_CALLS = 5

TEXT_CHANNEL_GUIDANCE = (
    "\n\nYou are chatting by text in a website chat widget. Write naturally and "
    "conversationally, in short, friendly messages. Plain text only — no markdown "
    "headings or code fences. You may use short bullet points when it genuinely "
    "helps."
)


class ChatTurnResult:
    """The outcome of one assistant turn."""

    __slots__ = ("reply", "tool_name")

    def __init__(self, reply: str, tool_name: Optional[str] = None):
        self.reply = reply
        self.tool_name = tool_name


class AgentChatService:
    """Runs one text turn of an agent conversation, tools and all."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.llm = get_llm_service()
        self.functions = get_function_executor()

    async def respond(
        self,
        agent: Agent,
        history: List[Dict[str, str]],
        user_message: str,
    ) -> ChatTurnResult:
        """
        Produce the agent's reply to a user message.

        Args:
            agent: The agent (system prompt, model, tools, knowledge base)
            history: Prior turns as ``[{"role": "user"|"assistant", "content": ...}]``
            user_message: The new user message

        Returns:
            The reply text and the tool used, if any
        """
        messages = await self._build_messages(agent, history, user_message)

        # Load the agent's tools once. Workflow-backed tools derive their schema
        # from the workflow's inputs (async), which is why this is awaited.
        agent_functions = await self.functions.get_agent_functions(str(agent.id), self.db)
        agent_tools = await self.functions.get_agent_assigned_tools(str(agent.id), self.db)

        func_defs = [
            self.functions.get_function_definition(f) for f in agent_functions
        ] + await self.functions.build_tool_definitions(agent_tools, db=self.db)

        model = agent.llm_model or "gpt-4o-mini"
        used_tool: Optional[str] = None

        for _ in range(MAX_TOOL_CALLS):
            completion = await self.llm.chat(
                messages=messages,
                provider=agent.llm_provider,
                model=model,
                temperature=float(agent.llm_temperature or 0.7),
                max_tokens=int(agent.llm_max_tokens or 600),
                functions=func_defs or None,
            )

            fcall = getattr(completion, "function_call", None)
            if not fcall:
                return ChatTurnResult(completion.content or "", used_tool)

            try:
                args = json.loads(fcall.arguments or "{}")
            except (ValueError, TypeError):
                args = {}

            used_tool = fcall.name

            # Record the assistant's tool request, then its result — the order
            # OpenAI requires (an orphan tool message is rejected).
            messages.append(
                ChatMessage(
                    role="assistant",
                    content=completion.content or "",
                    function_call={"name": fcall.name, "arguments": fcall.arguments},
                )
            )
            result = await self._run_tool(agent_functions, agent_tools, fcall.name, args)
            messages.append(
                ChatMessage(role="function", name=fcall.name, content=result)
            )

        # Hit the tool ceiling without a final answer.
        return ChatTurnResult(
            "I'm sorry, I'm having trouble completing that right now.", used_tool
        )

    async def _build_messages(
        self,
        agent: Agent,
        history: List[Dict[str, str]],
        user_message: str,
    ) -> List[ChatMessage]:
        """Assemble system prompt (+ KB context) + history + the new message."""
        system_text = agent.system_prompt or "You are a helpful assistant."
        system_text += TEXT_CHANNEL_GUIDANCE

        kb_context = await self._knowledge_context(agent, user_message)
        if kb_context:
            system_text += (
                "\n\nUse the following knowledge base context to answer when "
                "relevant. If it doesn't cover the question, say so honestly.\n\n"
                + kb_context
            )

        messages = [ChatMessage(role="system", content=system_text)]

        for turn in history[-10:]:
            role = turn.get("role", "user")
            role = "assistant" if role in ("assistant", "agent") else "user"
            content = turn.get("content") or turn.get("text") or ""
            if content:
                messages.append(ChatMessage(role=role, content=content))

        messages.append(ChatMessage(role="user", content=user_message))
        return messages

    async def _knowledge_context(self, agent: Agent, query: str) -> Optional[str]:
        """
        Retrieve relevant knowledge base chunks, best-effort.

        The same knowledge base the voice agent uses. Any failure (no KB, no
        embeddings, provider down) degrades to no context rather than breaking
        the reply.
        """
        config = agent.knowledge_base_config or {}
        kb_id = config.get("knowledge_base_id") or config.get("id")
        if not kb_id:
            return None

        try:
            from app.core.config import settings
            from app.services.knowledge_base.rag_service import search_knowledge_base_db

            chunks = await search_knowledge_base_db(
                db=self.db,
                knowledge_base_id=str(kb_id),
                query=query,
                api_key=settings.OPENAI_API_KEY,
                top_k=4,
            )
            if not chunks:
                return None
            return "\n\n".join(c.get("content", "") for c in chunks if c.get("content"))
        except Exception as e:
            logger.debug(f"Knowledge base lookup skipped: {e}")
            return None

    async def _run_tool(
        self,
        agent_functions: List[Any],
        agent_tools: List[Any],
        name: str,
        args: Dict[str, Any],
    ) -> str:
        """
        Execute the tool the model asked for and return a string for the LLM.

        Uses the SAME executor as the voice path, so a workflow-backed tool
        fires its workflow identically from chat. No live channel is passed —
        text has no mid-turn speak/ask — so a workflow's conversation steps run
        simulated and the result comes back for the model to phrase.
        """
        agent_function = next((f for f in agent_functions if f.name == name), None)
        if agent_function:
            result = await self.functions.execute_function(
                function=agent_function, parameters=args, call_id=None, db=self.db
            )
            return self.functions.format_for_llm(agent_function, result)

        tool = next(
            (t for t in agent_tools if sanitize_function_name(t.name) == name), None
        )
        if not tool:
            return f"The capability '{name}' is not configured."

        result = await self.functions.execute_global_tool(
            tool=tool, parameters=args, call_id=None, db=self.db
        )
        inner = result.get("result", {}) if result.get("success") else {}

        if isinstance(inner, dict) and inner.get("requires_telephony"):
            return (
                "That action needs a phone call and can't run in a chat. Offer the "
                "visitor an alternative."
            )
        if result.get("success"):
            return f"Tool {tool.name} returned: {json.dumps(inner)}"
        return f"Tool {tool.name} failed: {result.get('error', 'unknown error')}"


def get_agent_chat_service(db: AsyncSession) -> AgentChatService:
    return AgentChatService(db)
