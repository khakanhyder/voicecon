"""
SendGrid Connector.

Integration with SendGrid Email API.
"""
import logging
from typing import Dict, Any, Optional, List

from app.services.integrations.connector_base import BaseConnector, ConnectorError

logger = logging.getLogger(__name__)


class SendGridConnector(BaseConnector):
    """
    SendGrid email connector.

    Provides methods to interact with SendGrid API:
    - Send emails
    - Send templated emails
    - Manage contacts
    - Manage lists
    - Get email statistics
    """

    async def test_connection(self) -> Dict[str, Any]:
        """
        Test SendGrid connection by fetching API key details.

        Returns:
            Test result dictionary
        """
        try:
            # Get API key details (scopes)
            response = await self.get("/v3/scopes")

            return {
                "success": True,
                "message": "SendGrid connection successful",
                "details": {
                    "scopes": response.get("scopes", []),
                },
            }

        except Exception as e:
            logger.error(f"SendGrid connection test failed: {e}", exc_info=True)
            return {
                "success": False,
                "message": f"SendGrid connection test failed: {str(e)}",
                "details": {},
            }

    # ========================================================================
    # Email Sending Methods
    # ========================================================================

    async def send_email(
        self,
        to_email: str,
        from_email: str,
        subject: str,
        html_content: Optional[str] = None,
        text_content: Optional[str] = None,
        to_name: Optional[str] = None,
        from_name: Optional[str] = None,
        reply_to: Optional[str] = None,
        cc: Optional[List[Dict[str, str]]] = None,
        bcc: Optional[List[Dict[str, str]]] = None,
        attachments: Optional[List[Dict[str, Any]]] = None,
        custom_args: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """
        Send an email via SendGrid.

        Args:
            to_email: Recipient email address
            from_email: Sender email address
            subject: Email subject
            html_content: HTML email body
            text_content: Plain text email body
            to_name: Recipient name
            from_name: Sender name
            reply_to: Reply-to email address
            cc: CC recipients [{"email": "...", "name": "..."}]
            bcc: BCC recipients [{"email": "...", "name": "..."}]
            attachments: Email attachments
            custom_args: Custom arguments for tracking

        Returns:
            Send result with message ID

        Raises:
            ConnectorError: If sending fails
        """
        try:
            # Build email data
            email_data = {
                "personalizations": [
                    {
                        "to": [{"email": to_email}],
                    }
                ],
                "from": {"email": from_email},
                "subject": subject,
            }

            # Add recipient name
            if to_name:
                email_data["personalizations"][0]["to"][0]["name"] = to_name

            # Add sender name
            if from_name:
                email_data["from"]["name"] = from_name

            # Add content
            content = []
            if text_content:
                content.append({"type": "text/plain", "value": text_content})
            if html_content:
                content.append({"type": "text/html", "value": html_content})

            if content:
                email_data["content"] = content

            # Add reply-to
            if reply_to:
                email_data["reply_to"] = {"email": reply_to}

            # Add CC
            if cc:
                email_data["personalizations"][0]["cc"] = cc

            # Add BCC
            if bcc:
                email_data["personalizations"][0]["bcc"] = bcc

            # Add attachments
            if attachments:
                email_data["attachments"] = attachments

            # Add custom args
            if custom_args:
                email_data["custom_args"] = custom_args

            # Send email
            response = await self.post("/v3/mail/send", json=email_data)

            logger.info(f"SendGrid email sent to: {to_email}")

            return {
                "success": True,
                "message": "Email sent successfully",
            }

        except Exception as e:
            logger.error(f"Failed to send SendGrid email: {e}", exc_info=True)
            raise ConnectorError(f"Failed to send email: {str(e)}")

    async def send_template_email(
        self,
        to_email: str,
        from_email: str,
        template_id: str,
        dynamic_template_data: Optional[Dict[str, Any]] = None,
        to_name: Optional[str] = None,
        from_name: Optional[str] = None,
        reply_to: Optional[str] = None,
        cc: Optional[List[Dict[str, str]]] = None,
        bcc: Optional[List[Dict[str, str]]] = None,
    ) -> Dict[str, Any]:
        """
        Send a templated email via SendGrid.

        Args:
            to_email: Recipient email address
            from_email: Sender email address
            template_id: SendGrid template ID
            dynamic_template_data: Template variables
            to_name: Recipient name
            from_name: Sender name
            reply_to: Reply-to email address
            cc: CC recipients
            bcc: BCC recipients

        Returns:
            Send result

        Raises:
            ConnectorError: If sending fails
        """
        try:
            # Build email data
            email_data = {
                "personalizations": [
                    {
                        "to": [{"email": to_email}],
                    }
                ],
                "from": {"email": from_email},
                "template_id": template_id,
            }

            # Add recipient name
            if to_name:
                email_data["personalizations"][0]["to"][0]["name"] = to_name

            # Add sender name
            if from_name:
                email_data["from"]["name"] = from_name

            # Add template data
            if dynamic_template_data:
                email_data["personalizations"][0]["dynamic_template_data"] = dynamic_template_data

            # Add reply-to
            if reply_to:
                email_data["reply_to"] = {"email": reply_to}

            # Add CC
            if cc:
                email_data["personalizations"][0]["cc"] = cc

            # Add BCC
            if bcc:
                email_data["personalizations"][0]["bcc"] = bcc

            # Send email
            await self.post("/v3/mail/send", json=email_data)

            logger.info(f"SendGrid template email sent to: {to_email}")

            return {
                "success": True,
                "message": "Template email sent successfully",
            }

        except Exception as e:
            logger.error(f"Failed to send SendGrid template email: {e}", exc_info=True)
            raise ConnectorError(f"Failed to send template email: {str(e)}")

    # ========================================================================
    # Contact Management Methods
    # ========================================================================

    async def add_contact(
        self,
        email: str,
        first_name: Optional[str] = None,
        last_name: Optional[str] = None,
        custom_fields: Optional[Dict[str, Any]] = None,
        list_ids: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Add or update a contact in SendGrid.

        Args:
            email: Contact email address
            first_name: Contact first name
            last_name: Contact last name
            custom_fields: Custom field values
            list_ids: List IDs to add contact to

        Returns:
            Contact creation result

        Raises:
            ConnectorError: If contact creation fails
        """
        try:
            # Build contact data
            contact_data = {
                "email": email,
            }

            if first_name:
                contact_data["first_name"] = first_name
            if last_name:
                contact_data["last_name"] = last_name
            if custom_fields:
                contact_data["custom_fields"] = custom_fields

            # Build request payload
            payload = {
                "contacts": [contact_data]
            }

            if list_ids:
                payload["list_ids"] = list_ids

            # Add contact
            response = await self.put("/v3/marketing/contacts", json=payload)

            logger.info(f"SendGrid contact added: {email}")

            return {
                "success": True,
                "job_id": response.get("job_id"),
            }

        except Exception as e:
            logger.error(f"Failed to add SendGrid contact: {e}", exc_info=True)
            raise ConnectorError(f"Failed to add contact: {str(e)}")

    async def delete_contact(self, contact_id: str) -> Dict[str, Any]:
        """
        Delete a contact from SendGrid.

        Args:
            contact_id: SendGrid contact ID

        Returns:
            Deletion result

        Raises:
            ConnectorError: If deletion fails
        """
        try:
            await self.delete(
                "/v3/marketing/contacts",
                params={"ids": contact_id}
            )

            logger.info(f"SendGrid contact deleted: {contact_id}")

            return {
                "success": True,
            }

        except Exception as e:
            logger.error(f"Failed to delete SendGrid contact: {e}", exc_info=True)
            raise ConnectorError(f"Failed to delete contact: {str(e)}")

    async def search_contacts(
        self,
        query: str,
    ) -> Dict[str, Any]:
        """
        Search for contacts.

        Args:
            query: Search query (e.g., "email LIKE '%@example.com%'")

        Returns:
            Search results

        Raises:
            ConnectorError: If search fails
        """
        try:
            response = await self.post(
                "/v3/marketing/contacts/search",
                json={"query": query}
            )

            return {
                "total": response.get("contact_count", 0),
                "contacts": response.get("result", []),
            }

        except Exception as e:
            logger.error(f"Failed to search SendGrid contacts: {e}", exc_info=True)
            raise ConnectorError(f"Failed to search contacts: {str(e)}")

    # ========================================================================
    # List Management Methods
    # ========================================================================

    async def create_list(
        self,
        name: str,
    ) -> Dict[str, Any]:
        """
        Create a new contact list.

        Args:
            name: List name

        Returns:
            Created list data

        Raises:
            ConnectorError: If list creation fails
        """
        try:
            response = await self.post(
                "/v3/marketing/lists",
                json={"name": name}
            )

            logger.info(f"SendGrid list created: {name}")

            return {
                "id": response.get("id"),
                "name": response.get("name"),
            }

        except Exception as e:
            logger.error(f"Failed to create SendGrid list: {e}", exc_info=True)
            raise ConnectorError(f"Failed to create list: {str(e)}")

    async def get_lists(self) -> List[Dict[str, Any]]:
        """
        Get all contact lists.

        Returns:
            List of lists

        Raises:
            ConnectorError: If retrieval fails
        """
        try:
            response = await self.get("/v3/marketing/lists")

            return response.get("result", [])

        except Exception as e:
            logger.error(f"Failed to get SendGrid lists: {e}", exc_info=True)
            raise ConnectorError(f"Failed to get lists: {str(e)}")

    async def add_contacts_to_list(
        self,
        list_id: str,
        contact_ids: List[str],
    ) -> Dict[str, Any]:
        """
        Add contacts to a list.

        Args:
            list_id: List ID
            contact_ids: Contact IDs to add

        Returns:
            Operation result

        Raises:
            ConnectorError: If operation fails
        """
        try:
            await self.post(
                f"/v3/marketing/lists/{list_id}/contacts",
                json={"contact_ids": contact_ids}
            )

            logger.info(f"Added {len(contact_ids)} contacts to list {list_id}")

            return {
                "success": True,
            }

        except Exception as e:
            logger.error(f"Failed to add contacts to SendGrid list: {e}", exc_info=True)
            raise ConnectorError(f"Failed to add contacts to list: {str(e)}")

    # ========================================================================
    # Statistics Methods
    # ========================================================================

    async def get_stats(
        self,
        start_date: str,
        end_date: Optional[str] = None,
        aggregated_by: str = "day",
    ) -> Dict[str, Any]:
        """
        Get email statistics.

        Args:
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)
            aggregated_by: Aggregation period (day, week, month)

        Returns:
            Email statistics

        Raises:
            ConnectorError: If retrieval fails
        """
        try:
            params = {
                "start_date": start_date,
                "aggregated_by": aggregated_by,
            }

            if end_date:
                params["end_date"] = end_date

            response = await self.get("/v3/stats", params=params)

            return {
                "stats": response,
            }

        except Exception as e:
            logger.error(f"Failed to get SendGrid stats: {e}", exc_info=True)
            raise ConnectorError(f"Failed to get stats: {str(e)}")

    async def get_bounces(
        self,
        start_time: Optional[int] = None,
        end_time: Optional[int] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """
        Get bounce events.

        Args:
            start_time: Unix timestamp start
            end_time: Unix timestamp end
            limit: Number of results to return

        Returns:
            List of bounce events

        Raises:
            ConnectorError: If retrieval fails
        """
        try:
            params = {"limit": limit}

            if start_time:
                params["start_time"] = start_time
            if end_time:
                params["end_time"] = end_time

            response = await self.get("/v3/suppression/bounces", params=params)

            return response

        except Exception as e:
            logger.error(f"Failed to get SendGrid bounces: {e}", exc_info=True)
            raise ConnectorError(f"Failed to get bounces: {str(e)}")
