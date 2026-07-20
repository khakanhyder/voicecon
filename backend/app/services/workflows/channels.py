"""
Workflow execution channels.

A workflow's voice steps (speak / ask / transfer / end) need somewhere to *happen*.
During a live phone call that's the caller's audio stream; when a user hits "Run"
in the dashboard there is no call at all.

The channel abstracts that difference so one engine drives both:

  * ``SimulatedChannel`` — the default. Records what the agent *would* say and
    returns scripted/blank answers, so a flow can be tested from the dashboard
    without burning a phone call.
  * ``VoiceChannel``     — wraps a live voice session; speaks real TTS and waits
    on real STT for answers.

Handlers never branch on "is there a call?" — they just talk to the channel.
"""
import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class ChannelError(Exception):
    """Raised when a channel operation cannot be performed."""
    pass


class BaseChannel:
    """Interface every execution channel implements."""

    #: True when this channel is attached to a real, live conversation.
    is_live: bool = False

    async def speak(self, text: str, voice: Optional[str] = None) -> None:
        raise NotImplementedError

    async def ask(
        self,
        question: str,
        timeout: int = 10,
        input_type: str = "speech",
    ) -> Optional[str]:
        raise NotImplementedError

    async def transfer(self, destination: str, transfer_type: str = "blind") -> None:
        raise NotImplementedError

    async def end(self, farewell: Optional[str] = None) -> None:
        raise NotImplementedError


class SimulatedChannel(BaseChannel):
    """
    Dry-run channel used for dashboard test runs and post-call workflows.

    Nothing is spoken aloud. Every utterance is appended to ``transcript`` so the
    execution record shows exactly what the flow would have done, which is what
    makes "Run" in the builder useful.

    ``answers`` lets a test run script the caller's side: keys are the ask step's
    variable name (falling back to the question text), values are the reply.
    Unscripted questions return ``default_answer`` rather than blocking.
    """

    is_live = False

    def __init__(
        self,
        answers: Optional[Dict[str, str]] = None,
        default_answer: str = "",
    ):
        self.answers = answers or {}
        self.default_answer = default_answer
        self.transcript: List[Dict[str, Any]] = []

    async def speak(self, text: str, voice: Optional[str] = None) -> None:
        self.transcript.append({"role": "agent", "type": "speak", "text": text})
        logger.info(f"[simulated] agent says: {text}")

    async def ask(
        self,
        question: str,
        timeout: int = 10,
        input_type: str = "speech",
        variable: Optional[str] = None,
    ) -> Optional[str]:
        self.transcript.append({"role": "agent", "type": "ask", "text": question})
        answer = self.answers.get(variable or "", self.answers.get(question, self.default_answer))
        self.transcript.append({"role": "caller", "type": "answer", "text": answer})
        logger.info(f"[simulated] asked '{question}' -> '{answer}'")
        return answer

    async def transfer(self, destination: str, transfer_type: str = "blind") -> None:
        self.transcript.append(
            {"role": "system", "type": "transfer", "destination": destination,
             "transfer_type": transfer_type}
        )
        logger.info(f"[simulated] transfer to {destination} ({transfer_type})")

    async def end(self, farewell: Optional[str] = None) -> None:
        if farewell:
            self.transcript.append({"role": "agent", "type": "speak", "text": farewell})
        self.transcript.append({"role": "system", "type": "end"})
        logger.info("[simulated] call ended")


class VoiceChannel(BaseChannel):
    """
    Live channel backed by a voice session.

    ``session`` is a VoiceSession (app.services.websocket.voice_session). We call
    into it by duck-typing rather than importing it, to avoid a circular import
    between the workflow engine and the websocket layer.
    """

    is_live = True

    def __init__(self, session: Any):
        self.session = session

    async def speak(self, text: str, voice: Optional[str] = None) -> None:
        await self.session.speak(text)

    async def ask(
        self,
        question: str,
        timeout: int = 10,
        input_type: str = "speech",
        variable: Optional[str] = None,
    ) -> Optional[str]:
        await self.session.speak(question)
        return await self.session.wait_for_user_reply(timeout=timeout)

    async def transfer(self, destination: str, transfer_type: str = "blind") -> None:
        await self.session.transfer_call(destination, transfer_type=transfer_type)

    async def end(self, farewell: Optional[str] = None) -> None:
        if farewell:
            await self.session.speak(farewell)
        await self.session.end_call()
