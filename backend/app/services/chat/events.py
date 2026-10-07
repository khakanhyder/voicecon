"""
Live chat-inbox events for the mobile app (and any dashboard) over WebSocket.

Every change to a workspace's chat inbox — a visitor writes, the agent
answers, a team member replies, a conversation is taken over or read — is
published here, and each open ``/chat/ws`` socket for that workspace gets it.

In-process on purpose: the API runs as one uvicorn process (see start.sh).
Running several workers or replicas would need this swapped for Redis
pub/sub, otherwise a socket only hears events raised in its own process. The
socket is a convenience either way — clients re-fetch over REST on reconnect,
so a missed event costs freshness, never data.
"""
import asyncio
import logging
import uuid
from collections import defaultdict
from typing import Any, Dict, Set

logger = logging.getLogger(__name__)

#: Events a slow client may fall behind by before it is dropped; it reconnects
#: and re-syncs over REST.
QUEUE_SIZE = 200


class ChatEventBus:
    def __init__(self) -> None:
        self._subscribers: Dict[uuid.UUID, Set[asyncio.Queue]] = defaultdict(set)

    def subscribe(self, organization_id: uuid.UUID) -> asyncio.Queue:
        queue: asyncio.Queue = asyncio.Queue(maxsize=QUEUE_SIZE)
        self._subscribers[organization_id].add(queue)
        return queue

    def unsubscribe(self, organization_id: uuid.UUID, queue: asyncio.Queue) -> None:
        subs = self._subscribers.get(organization_id)
        if subs is None:
            return
        subs.discard(queue)
        if not subs:
            self._subscribers.pop(organization_id, None)

    def publish(self, organization_id: uuid.UUID, event: str, data: Dict[str, Any]) -> None:
        """Hand ``event`` to every socket open on this workspace. Never raises."""
        message = {"event": event, "organization_id": str(organization_id), "data": data}
        for queue in list(self._subscribers.get(organization_id, ())):
            try:
                queue.put_nowait(message)
            except asyncio.QueueFull:
                # Signal the socket loop to close this client; it will resync.
                logger.warning("Chat event queue full; dropping a slow subscriber")
                self.unsubscribe(organization_id, queue)
                try:
                    queue.get_nowait()
                    queue.put_nowait(None)
                except Exception:
                    pass

    def subscriber_count(self, organization_id: uuid.UUID) -> int:
        return len(self._subscribers.get(organization_id, ()))


chat_events = ChatEventBus()
