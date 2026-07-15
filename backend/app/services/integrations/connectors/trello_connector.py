"""
Trello Connector.

Trello authenticates every request with two query params: an app-level `key`
(TRELLO_API_KEY, shared) and a per-user `token` (obtained via Trello's authorize
flow and stored on the connection). It is NOT OAuth2 and NOT a header API key.
"""
import os
import logging
from typing import Dict, Any, Optional, List

from app.services.integrations.connector_base import BaseConnector, ConnectorError

logger = logging.getLogger(__name__)


class TrelloConnector(BaseConnector):
    """
    Trello connector.

    Actions:
    - test_connection: verify the token (members/me)
    - get_boards: list the user's boards
    - get_lists: list lists on a board
    - create_card: create a card in a list
    - get_cards: list cards in a list
    - add_comment: comment on a card
    - update_card: update card fields
    """

    def get_auth_headers(self, access_token: str) -> Dict[str, str]:
        # Trello uses query params, not an auth header.
        return {}

    async def _auth_params(self, extra: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        app_key = os.getenv("TRELLO_API_KEY")
        if not app_key:
            raise ConnectorError("TRELLO_API_KEY is not configured on the server")
        token = await self.get_access_token()  # the stored per-user token
        params = {"key": app_key, "token": token}
        if extra:
            params.update(extra)
        return params

    async def test_connection(self) -> Dict[str, Any]:
        try:
            me = await self.get("/members/me", params=await self._auth_params())
            return {
                "success": True,
                "message": "Trello connection successful",
                "details": {"id": me.get("id"), "username": me.get("username")},
            }
        except Exception as e:
            logger.error(f"Trello connection test failed: {e}", exc_info=True)
            return {"success": False, "message": f"Trello connection test failed: {e}", "details": {}}

    async def get_boards(self) -> Dict[str, Any]:
        try:
            boards = await self.get("/members/me/boards",
                                    params=await self._auth_params({"fields": "name,url"}))
            items = [{"id": b.get("id"), "name": b.get("name"), "url": b.get("url")} for b in boards]
            return {"boards": items, "count": len(items)}
        except Exception as e:
            raise ConnectorError(f"Trello get_boards failed: {e}")

    async def get_lists(self, board_id: str) -> Dict[str, Any]:
        try:
            lists = await self.get(f"/boards/{board_id}/lists",
                                   params=await self._auth_params({"fields": "name"}))
            items = [{"id": l.get("id"), "name": l.get("name")} for l in lists]
            return {"lists": items, "count": len(items)}
        except Exception as e:
            raise ConnectorError(f"Trello get_lists failed: {e}")

    async def create_card(self, list_id: str, name: str,
                          description: Optional[str] = None,
                          due: Optional[str] = None) -> Dict[str, Any]:
        """Create a card in a list. `due` is an ISO 8601 datetime string."""
        try:
            extra = {"idList": list_id, "name": name}
            if description:
                extra["desc"] = description
            if due:
                extra["due"] = due
            card = await self.post("/cards", params=await self._auth_params(extra))
            logger.info(f"Trello card created: {card.get('id')}")
            return {"id": card.get("id"), "name": card.get("name"), "url": card.get("url")}
        except Exception as e:
            logger.error(f"Trello create_card failed: {e}", exc_info=True)
            raise ConnectorError(f"Trello create_card failed: {e}")

    async def get_cards(self, list_id: str) -> Dict[str, Any]:
        try:
            cards = await self.get(f"/lists/{list_id}/cards",
                                   params=await self._auth_params({"fields": "name,due,url"}))
            items = [{"id": c.get("id"), "name": c.get("name"), "url": c.get("url")} for c in cards]
            return {"cards": items, "count": len(items)}
        except Exception as e:
            raise ConnectorError(f"Trello get_cards failed: {e}")

    async def add_comment(self, card_id: str, text: str) -> Dict[str, Any]:
        try:
            res = await self.post(f"/cards/{card_id}/actions/comments",
                                  params=await self._auth_params({"text": text}))
            return {"id": res.get("id"), "success": True}
        except Exception as e:
            raise ConnectorError(f"Trello add_comment failed: {e}")

    async def update_card(self, card_id: str, **fields) -> Dict[str, Any]:
        """Update a card. Accepts name, desc, due, idList, closed, etc."""
        try:
            extra = {k: v for k, v in fields.items() if v is not None}
            res = await self.put(f"/cards/{card_id}", params=await self._auth_params(extra))
            return {"id": res.get("id"), "name": res.get("name")}
        except Exception as e:
            raise ConnectorError(f"Trello update_card failed: {e}")
