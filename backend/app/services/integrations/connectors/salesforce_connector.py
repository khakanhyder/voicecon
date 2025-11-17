"""
Salesforce Connector.

Integration with Salesforce CRM API.
"""
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime

from app.services.integrations.connector_base import BaseConnector, ConnectorError

logger = logging.getLogger(__name__)


class SalesforceConnector(BaseConnector):
    """
    Salesforce CRM connector.

    Provides methods to interact with Salesforce API:
    - Create/update/delete contacts
    - Create/update/delete leads
    - Create/update/delete opportunities
    - Search records
    - Query with SOQL
    """

    async def test_connection(self) -> Dict[str, Any]:
        """
        Test Salesforce connection by fetching user info.

        Returns:
            Test result dictionary
        """
        try:
            # Get current user info
            user_info = await self.get("/services/oauth2/userinfo")

            return {
                "success": True,
                "message": "Salesforce connection successful",
                "details": {
                    "user_id": user_info.get("user_id"),
                    "organization_id": user_info.get("organization_id"),
                    "email": user_info.get("email"),
                    "name": user_info.get("name"),
                },
            }

        except Exception as e:
            logger.error(f"Salesforce connection test failed: {e}", exc_info=True)
            return {
                "success": False,
                "message": f"Salesforce connection test failed: {str(e)}",
                "details": {},
            }

    # ========================================================================
    # Contact Methods
    # ========================================================================

    async def create_contact(
        self,
        first_name: str,
        last_name: str,
        email: Optional[str] = None,
        phone: Optional[str] = None,
        additional_fields: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Create a new contact in Salesforce.

        Args:
            first_name: Contact's first name
            last_name: Contact's last name
            email: Contact's email
            phone: Contact's phone number
            additional_fields: Additional Salesforce fields

        Returns:
            Created contact data including ID

        Raises:
            ConnectorError: If contact creation fails
        """
        try:
            # Build contact data
            contact_data = {
                "FirstName": first_name,
                "LastName": last_name,
            }

            if email:
                contact_data["Email"] = email
            if phone:
                contact_data["Phone"] = phone

            # Add additional fields
            if additional_fields:
                contact_data.update(additional_fields)

            # Create contact
            response = await self.post(
                "/services/data/v57.0/sobjects/Contact",
                json=contact_data,
            )

            logger.info(f"Salesforce contact created: {response.get('id')}")

            return {
                "id": response.get("id"),
                "success": response.get("success", False),
                "errors": response.get("errors", []),
            }

        except Exception as e:
            logger.error(f"Failed to create Salesforce contact: {e}", exc_info=True)
            raise ConnectorError(f"Failed to create contact: {str(e)}")

    async def update_contact(
        self,
        contact_id: str,
        fields: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Update an existing contact in Salesforce.

        Args:
            contact_id: Salesforce contact ID
            fields: Fields to update

        Returns:
            Update result

        Raises:
            ConnectorError: If update fails
        """
        try:
            # Update contact
            await self.patch(
                f"/services/data/v57.0/sobjects/Contact/{contact_id}",
                json=fields,
            )

            logger.info(f"Salesforce contact updated: {contact_id}")

            return {
                "id": contact_id,
                "success": True,
            }

        except Exception as e:
            logger.error(f"Failed to update Salesforce contact: {e}", exc_info=True)
            raise ConnectorError(f"Failed to update contact: {str(e)}")

    async def get_contact(self, contact_id: str) -> Dict[str, Any]:
        """
        Get a contact by ID.

        Args:
            contact_id: Salesforce contact ID

        Returns:
            Contact data

        Raises:
            ConnectorError: If retrieval fails
        """
        try:
            contact = await self.get(
                f"/services/data/v57.0/sobjects/Contact/{contact_id}"
            )

            return contact

        except Exception as e:
            logger.error(f"Failed to get Salesforce contact: {e}", exc_info=True)
            raise ConnectorError(f"Failed to get contact: {str(e)}")

    async def delete_contact(self, contact_id: str) -> Dict[str, Any]:
        """
        Delete a contact.

        Args:
            contact_id: Salesforce contact ID

        Returns:
            Deletion result

        Raises:
            ConnectorError: If deletion fails
        """
        try:
            await self.delete(
                f"/services/data/v57.0/sobjects/Contact/{contact_id}"
            )

            logger.info(f"Salesforce contact deleted: {contact_id}")

            return {
                "id": contact_id,
                "success": True,
            }

        except Exception as e:
            logger.error(f"Failed to delete Salesforce contact: {e}", exc_info=True)
            raise ConnectorError(f"Failed to delete contact: {str(e)}")

    # ========================================================================
    # Lead Methods
    # ========================================================================

    async def create_lead(
        self,
        first_name: str,
        last_name: str,
        company: str,
        email: Optional[str] = None,
        phone: Optional[str] = None,
        status: str = "Open - Not Contacted",
        additional_fields: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Create a new lead in Salesforce.

        Args:
            first_name: Lead's first name
            last_name: Lead's last name
            company: Company name
            email: Lead's email
            phone: Lead's phone number
            status: Lead status
            additional_fields: Additional Salesforce fields

        Returns:
            Created lead data including ID

        Raises:
            ConnectorError: If lead creation fails
        """
        try:
            # Build lead data
            lead_data = {
                "FirstName": first_name,
                "LastName": last_name,
                "Company": company,
                "Status": status,
            }

            if email:
                lead_data["Email"] = email
            if phone:
                lead_data["Phone"] = phone

            # Add additional fields
            if additional_fields:
                lead_data.update(additional_fields)

            # Create lead
            response = await self.post(
                "/services/data/v57.0/sobjects/Lead",
                json=lead_data,
            )

            logger.info(f"Salesforce lead created: {response.get('id')}")

            return {
                "id": response.get("id"),
                "success": response.get("success", False),
                "errors": response.get("errors", []),
            }

        except Exception as e:
            logger.error(f"Failed to create Salesforce lead: {e}", exc_info=True)
            raise ConnectorError(f"Failed to create lead: {str(e)}")

    async def update_lead(
        self,
        lead_id: str,
        fields: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Update an existing lead in Salesforce.

        Args:
            lead_id: Salesforce lead ID
            fields: Fields to update

        Returns:
            Update result

        Raises:
            ConnectorError: If update fails
        """
        try:
            await self.patch(
                f"/services/data/v57.0/sobjects/Lead/{lead_id}",
                json=fields,
            )

            logger.info(f"Salesforce lead updated: {lead_id}")

            return {
                "id": lead_id,
                "success": True,
            }

        except Exception as e:
            logger.error(f"Failed to update Salesforce lead: {e}", exc_info=True)
            raise ConnectorError(f"Failed to update lead: {str(e)}")

    # ========================================================================
    # Opportunity Methods
    # ========================================================================

    async def create_opportunity(
        self,
        name: str,
        stage_name: str,
        close_date: str,
        amount: Optional[float] = None,
        account_id: Optional[str] = None,
        additional_fields: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Create a new opportunity in Salesforce.

        Args:
            name: Opportunity name
            stage_name: Sales stage
            close_date: Expected close date (YYYY-MM-DD)
            amount: Opportunity amount
            account_id: Associated account ID
            additional_fields: Additional Salesforce fields

        Returns:
            Created opportunity data including ID

        Raises:
            ConnectorError: If opportunity creation fails
        """
        try:
            # Build opportunity data
            opportunity_data = {
                "Name": name,
                "StageName": stage_name,
                "CloseDate": close_date,
            }

            if amount is not None:
                opportunity_data["Amount"] = amount
            if account_id:
                opportunity_data["AccountId"] = account_id

            # Add additional fields
            if additional_fields:
                opportunity_data.update(additional_fields)

            # Create opportunity
            response = await self.post(
                "/services/data/v57.0/sobjects/Opportunity",
                json=opportunity_data,
            )

            logger.info(f"Salesforce opportunity created: {response.get('id')}")

            return {
                "id": response.get("id"),
                "success": response.get("success", False),
                "errors": response.get("errors", []),
            }

        except Exception as e:
            logger.error(f"Failed to create Salesforce opportunity: {e}", exc_info=True)
            raise ConnectorError(f"Failed to create opportunity: {str(e)}")

    # ========================================================================
    # Query Methods
    # ========================================================================

    async def query(self, soql: str) -> Dict[str, Any]:
        """
        Execute a SOQL query.

        Args:
            soql: SOQL query string

        Returns:
            Query results

        Raises:
            ConnectorError: If query fails
        """
        try:
            response = await self.get(
                "/services/data/v57.0/query",
                params={"q": soql},
            )

            return {
                "total_size": response.get("totalSize", 0),
                "done": response.get("done", False),
                "records": response.get("records", []),
            }

        except Exception as e:
            logger.error(f"Failed to execute Salesforce query: {e}", exc_info=True)
            raise ConnectorError(f"Failed to execute query: {str(e)}")

    async def search_contacts(
        self,
        email: Optional[str] = None,
        phone: Optional[str] = None,
        name: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Search for contacts.

        Args:
            email: Email to search for
            phone: Phone to search for
            name: Name to search for

        Returns:
            List of matching contacts

        Raises:
            ConnectorError: If search fails
        """
        try:
            # Build SOQL query
            conditions = []
            if email:
                conditions.append(f"Email = '{email}'")
            if phone:
                conditions.append(f"Phone = '{phone}'")
            if name:
                conditions.append(f"Name LIKE '%{name}%'")

            if not conditions:
                return []

            where_clause = " OR ".join(conditions)
            soql = f"SELECT Id, FirstName, LastName, Email, Phone FROM Contact WHERE {where_clause}"

            result = await self.query(soql)
            return result.get("records", [])

        except Exception as e:
            logger.error(f"Failed to search Salesforce contacts: {e}", exc_info=True)
            raise ConnectorError(f"Failed to search contacts: {str(e)}")

    async def search_leads(
        self,
        email: Optional[str] = None,
        phone: Optional[str] = None,
        company: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Search for leads.

        Args:
            email: Email to search for
            phone: Phone to search for
            company: Company to search for

        Returns:
            List of matching leads

        Raises:
            ConnectorError: If search fails
        """
        try:
            # Build SOQL query
            conditions = []
            if email:
                conditions.append(f"Email = '{email}'")
            if phone:
                conditions.append(f"Phone = '{phone}'")
            if company:
                conditions.append(f"Company LIKE '%{company}%'")

            if not conditions:
                return []

            where_clause = " OR ".join(conditions)
            soql = f"SELECT Id, FirstName, LastName, Email, Phone, Company, Status FROM Lead WHERE {where_clause}"

            result = await self.query(soql)
            return result.get("records", [])

        except Exception as e:
            logger.error(f"Failed to search Salesforce leads: {e}", exc_info=True)
            raise ConnectorError(f"Failed to search leads: {str(e)}")
