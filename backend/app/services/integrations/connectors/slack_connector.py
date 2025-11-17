"""
Slack Connector.

Integration with Slack API.
"""
import logging
from typing import Dict, Any, Optional, List

from app.services.integrations.connector_base import BaseConnector, ConnectorError

logger = logging.getLogger(__name__)


class SlackConnector(BaseConnector):
    """
    Slack connector.

    Provides methods to interact with Slack API:
    - Send messages to channels and users
    - Upload files
    - Manage channels
    - Get user information
    - Post to webhooks
    - Manage reactions
    """

    async def test_connection(self) -> Dict[str, Any]:
        """
        Test Slack connection by authenticating.

        Returns:
            Test result dictionary
        """
        try:
            # Test auth
            response = await self.get("/auth.test")

            if not response.get("ok"):
                raise ConnectorError(response.get("error", "Authentication failed"))

            return {
                "success": True,
                "message": "Slack connection successful",
                "details": {
                    "team": response.get("team"),
                    "user": response.get("user"),
                    "team_id": response.get("team_id"),
                    "user_id": response.get("user_id"),
                },
            }

        except Exception as e:
            logger.error(f"Slack connection test failed: {e}", exc_info=True)
            return {
                "success": False,
                "message": f"Slack connection test failed: {str(e)}",
                "details": {},
            }

    # ========================================================================
    # Message Methods
    # ========================================================================

    async def send_message(
        self,
        channel: str,
        text: str,
        thread_ts: Optional[str] = None,
        blocks: Optional[List[Dict[str, Any]]] = None,
        attachments: Optional[List[Dict[str, Any]]] = None,
        username: Optional[str] = None,
        icon_emoji: Optional[str] = None,
        icon_url: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Send a message to a channel or user.

        Args:
            channel: Channel ID or name (e.g., "#general" or "C1234567890")
            text: Message text
            thread_ts: Thread timestamp to reply to
            blocks: Block Kit blocks for rich formatting
            attachments: Message attachments (legacy)
            username: Bot username override
            icon_emoji: Bot emoji icon (e.g., ":robot_face:")
            icon_url: Bot icon URL

        Returns:
            Sent message data including timestamp

        Raises:
            ConnectorError: If sending fails
        """
        try:
            # Build message data
            message_data = {
                "channel": channel,
                "text": text,
            }

            if thread_ts:
                message_data["thread_ts"] = thread_ts
            if blocks:
                message_data["blocks"] = blocks
            if attachments:
                message_data["attachments"] = attachments
            if username:
                message_data["username"] = username
            if icon_emoji:
                message_data["icon_emoji"] = icon_emoji
            if icon_url:
                message_data["icon_url"] = icon_url

            # Send message
            response = await self.post("/chat.postMessage", json=message_data)

            if not response.get("ok"):
                raise ConnectorError(response.get("error", "Failed to send message"))

            logger.info(f"Slack message sent to {channel}")

            return {
                "success": True,
                "channel": response.get("channel"),
                "ts": response.get("ts"),
                "message": response.get("message"),
            }

        except Exception as e:
            logger.error(f"Failed to send Slack message: {e}", exc_info=True)
            raise ConnectorError(f"Failed to send message: {str(e)}")

    async def send_direct_message(
        self,
        user_id: str,
        text: str,
        blocks: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """
        Send a direct message to a user.

        Args:
            user_id: User ID (e.g., "U1234567890")
            text: Message text
            blocks: Block Kit blocks for rich formatting

        Returns:
            Sent message data

        Raises:
            ConnectorError: If sending fails
        """
        try:
            # Open DM channel
            dm_response = await self.post(
                "/conversations.open",
                json={"users": user_id},
            )

            if not dm_response.get("ok"):
                raise ConnectorError(dm_response.get("error", "Failed to open DM"))

            channel_id = dm_response.get("channel", {}).get("id")

            # Send message
            return await self.send_message(
                channel=channel_id,
                text=text,
                blocks=blocks,
            )

        except Exception as e:
            logger.error(f"Failed to send Slack DM: {e}", exc_info=True)
            raise ConnectorError(f"Failed to send DM: {str(e)}")

    async def update_message(
        self,
        channel: str,
        ts: str,
        text: str,
        blocks: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """
        Update an existing message.

        Args:
            channel: Channel ID
            ts: Message timestamp
            text: New message text
            blocks: New Block Kit blocks

        Returns:
            Updated message data

        Raises:
            ConnectorError: If update fails
        """
        try:
            update_data = {
                "channel": channel,
                "ts": ts,
                "text": text,
            }

            if blocks:
                update_data["blocks"] = blocks

            response = await self.post("/chat.update", json=update_data)

            if not response.get("ok"):
                raise ConnectorError(response.get("error", "Failed to update message"))

            logger.info(f"Slack message updated: {ts}")

            return {
                "success": True,
                "channel": response.get("channel"),
                "ts": response.get("ts"),
            }

        except Exception as e:
            logger.error(f"Failed to update Slack message: {e}", exc_info=True)
            raise ConnectorError(f"Failed to update message: {str(e)}")

    async def delete_message(
        self,
        channel: str,
        ts: str,
    ) -> Dict[str, Any]:
        """
        Delete a message.

        Args:
            channel: Channel ID
            ts: Message timestamp

        Returns:
            Deletion result

        Raises:
            ConnectorError: If deletion fails
        """
        try:
            response = await self.post(
                "/chat.delete",
                json={"channel": channel, "ts": ts},
            )

            if not response.get("ok"):
                raise ConnectorError(response.get("error", "Failed to delete message"))

            logger.info(f"Slack message deleted: {ts}")

            return {
                "success": True,
                "channel": response.get("channel"),
                "ts": response.get("ts"),
            }

        except Exception as e:
            logger.error(f"Failed to delete Slack message: {e}", exc_info=True)
            raise ConnectorError(f"Failed to delete message: {str(e)}")

    # ========================================================================
    # File Methods
    # ========================================================================

    async def upload_file(
        self,
        channels: List[str],
        file_content: bytes,
        filename: str,
        title: Optional[str] = None,
        initial_comment: Optional[str] = None,
        filetype: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Upload a file to Slack.

        Args:
            channels: List of channel IDs
            file_content: File content as bytes
            filename: Filename
            title: File title
            initial_comment: Initial comment
            filetype: File type (e.g., "pdf", "png")

        Returns:
            Upload result with file info

        Raises:
            ConnectorError: If upload fails
        """
        try:
            # Note: This uses files.upload which requires multipart/form-data
            # For simplicity, we'll use the v2 API which accepts JSON
            import base64

            file_data = {
                "channels": ",".join(channels),
                "content": base64.b64encode(file_content).decode("utf-8"),
                "filename": filename,
            }

            if title:
                file_data["title"] = title
            if initial_comment:
                file_data["initial_comment"] = initial_comment
            if filetype:
                file_data["filetype"] = filetype

            response = await self.post("/files.upload", json=file_data)

            if not response.get("ok"):
                raise ConnectorError(response.get("error", "Failed to upload file"))

            logger.info(f"Slack file uploaded: {filename}")

            return {
                "success": True,
                "file": response.get("file"),
            }

        except Exception as e:
            logger.error(f"Failed to upload Slack file: {e}", exc_info=True)
            raise ConnectorError(f"Failed to upload file: {str(e)}")

    # ========================================================================
    # Channel Methods
    # ========================================================================

    async def list_channels(
        self,
        exclude_archived: bool = True,
        types: str = "public_channel,private_channel",
    ) -> List[Dict[str, Any]]:
        """
        List channels.

        Args:
            exclude_archived: Exclude archived channels
            types: Channel types (comma-separated: public_channel, private_channel, mpim, im)

        Returns:
            List of channels

        Raises:
            ConnectorError: If retrieval fails
        """
        try:
            params = {
                "exclude_archived": exclude_archived,
                "types": types,
            }

            response = await self.get("/conversations.list", params=params)

            if not response.get("ok"):
                raise ConnectorError(response.get("error", "Failed to list channels"))

            channels = response.get("channels", [])

            return [
                {
                    "id": ch.get("id"),
                    "name": ch.get("name"),
                    "is_private": ch.get("is_private", False),
                    "is_archived": ch.get("is_archived", False),
                    "num_members": ch.get("num_members", 0),
                    "topic": ch.get("topic", {}).get("value"),
                    "purpose": ch.get("purpose", {}).get("value"),
                }
                for ch in channels
            ]

        except Exception as e:
            logger.error(f"Failed to list Slack channels: {e}", exc_info=True)
            raise ConnectorError(f"Failed to list channels: {str(e)}")

    async def create_channel(
        self,
        name: str,
        is_private: bool = False,
    ) -> Dict[str, Any]:
        """
        Create a new channel.

        Args:
            name: Channel name (lowercase, no spaces)
            is_private: Create as private channel

        Returns:
            Created channel data

        Raises:
            ConnectorError: If creation fails
        """
        try:
            response = await self.post(
                "/conversations.create",
                json={"name": name, "is_private": is_private},
            )

            if not response.get("ok"):
                raise ConnectorError(response.get("error", "Failed to create channel"))

            logger.info(f"Slack channel created: {name}")

            channel = response.get("channel", {})

            return {
                "id": channel.get("id"),
                "name": channel.get("name"),
                "is_private": channel.get("is_private", False),
            }

        except Exception as e:
            logger.error(f"Failed to create Slack channel: {e}", exc_info=True)
            raise ConnectorError(f"Failed to create channel: {str(e)}")

    async def invite_to_channel(
        self,
        channel: str,
        users: List[str],
    ) -> Dict[str, Any]:
        """
        Invite users to a channel.

        Args:
            channel: Channel ID
            users: List of user IDs

        Returns:
            Invitation result

        Raises:
            ConnectorError: If invitation fails
        """
        try:
            response = await self.post(
                "/conversations.invite",
                json={"channel": channel, "users": ",".join(users)},
            )

            if not response.get("ok"):
                raise ConnectorError(response.get("error", "Failed to invite users"))

            logger.info(f"Invited {len(users)} users to Slack channel {channel}")

            return {
                "success": True,
                "channel": response.get("channel"),
            }

        except Exception as e:
            logger.error(f"Failed to invite to Slack channel: {e}", exc_info=True)
            raise ConnectorError(f"Failed to invite to channel: {str(e)}")

    # ========================================================================
    # User Methods
    # ========================================================================

    async def get_user_info(
        self,
        user_id: str,
    ) -> Dict[str, Any]:
        """
        Get user information.

        Args:
            user_id: User ID

        Returns:
            User information

        Raises:
            ConnectorError: If retrieval fails
        """
        try:
            response = await self.get("/users.info", params={"user": user_id})

            if not response.get("ok"):
                raise ConnectorError(response.get("error", "Failed to get user info"))

            user = response.get("user", {})

            return {
                "id": user.get("id"),
                "name": user.get("name"),
                "real_name": user.get("real_name"),
                "email": user.get("profile", {}).get("email"),
                "phone": user.get("profile", {}).get("phone"),
                "title": user.get("profile", {}).get("title"),
                "is_admin": user.get("is_admin", False),
                "is_bot": user.get("is_bot", False),
                "deleted": user.get("deleted", False),
            }

        except Exception as e:
            logger.error(f"Failed to get Slack user info: {e}", exc_info=True)
            raise ConnectorError(f"Failed to get user info: {str(e)}")

    async def list_users(self) -> List[Dict[str, Any]]:
        """
        List all users in the workspace.

        Returns:
            List of users

        Raises:
            ConnectorError: If retrieval fails
        """
        try:
            response = await self.get("/users.list")

            if not response.get("ok"):
                raise ConnectorError(response.get("error", "Failed to list users"))

            users = response.get("members", [])

            return [
                {
                    "id": user.get("id"),
                    "name": user.get("name"),
                    "real_name": user.get("real_name"),
                    "email": user.get("profile", {}).get("email"),
                    "is_bot": user.get("is_bot", False),
                    "deleted": user.get("deleted", False),
                }
                for user in users
            ]

        except Exception as e:
            logger.error(f"Failed to list Slack users: {e}", exc_info=True)
            raise ConnectorError(f"Failed to list users: {str(e)}")

    # ========================================================================
    # Reaction Methods
    # ========================================================================

    async def add_reaction(
        self,
        channel: str,
        timestamp: str,
        emoji: str,
    ) -> Dict[str, Any]:
        """
        Add a reaction emoji to a message.

        Args:
            channel: Channel ID
            timestamp: Message timestamp
            emoji: Emoji name (without colons, e.g., "thumbsup")

        Returns:
            Reaction result

        Raises:
            ConnectorError: If adding reaction fails
        """
        try:
            response = await self.post(
                "/reactions.add",
                json={
                    "channel": channel,
                    "timestamp": timestamp,
                    "name": emoji,
                },
            )

            if not response.get("ok"):
                raise ConnectorError(response.get("error", "Failed to add reaction"))

            logger.info(f"Slack reaction added: {emoji}")

            return {
                "success": True,
            }

        except Exception as e:
            logger.error(f"Failed to add Slack reaction: {e}", exc_info=True)
            raise ConnectorError(f"Failed to add reaction: {str(e)}")

    # ========================================================================
    # Webhook Methods
    # ========================================================================

    async def post_webhook(
        self,
        webhook_url: str,
        text: str,
        blocks: Optional[List[Dict[str, Any]]] = None,
        username: Optional[str] = None,
        icon_emoji: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Post to an incoming webhook.

        Args:
            webhook_url: Webhook URL
            text: Message text
            blocks: Block Kit blocks
            username: Bot username
            icon_emoji: Bot emoji icon

        Returns:
            Post result

        Raises:
            ConnectorError: If posting fails
        """
        try:
            import httpx

            webhook_data = {"text": text}

            if blocks:
                webhook_data["blocks"] = blocks
            if username:
                webhook_data["username"] = username
            if icon_emoji:
                webhook_data["icon_emoji"] = icon_emoji

            # Post directly to webhook (not through base connector)
            async with httpx.AsyncClient() as client:
                response = await client.post(webhook_url, json=webhook_data)
                response.raise_for_status()

            logger.info("Slack webhook message posted")

            return {
                "success": True,
            }

        except Exception as e:
            logger.error(f"Failed to post Slack webhook: {e}", exc_info=True)
            raise ConnectorError(f"Failed to post webhook: {str(e)}")
