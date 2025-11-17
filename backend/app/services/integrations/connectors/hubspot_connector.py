"""
HubSpot Connector.

Integration with HubSpot CRM API.
"""
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime

from app.services.integrations.connector_base import BaseConnector, ConnectorError

logger = logging.getLogger(__name__)


class HubSpotConnector(BaseConnector):
    """
    HubSpot CRM connector.

    Provides methods to interact with HubSpot API:
    - Create/update/delete contacts
    - Create/update/delete companies
    - Create/update/delete deals
    - Search records
    - Manage associations
    - Get analytics
    """

    async def test_connection(self) -> Dict[str, Any]:
        """
        Test HubSpot connection by fetching account info.

        Returns:
            Test result dictionary
        """
        try:
            # Get account info
            account_info = await self.get("/account-info/v3/api-usage/daily")

            return {
                "success": True,
                "message": "HubSpot connection successful",
                "details": {
                    "account_type": "HubSpot CRM",
                },
            }

        except Exception as e:
            logger.error(f"HubSpot connection test failed: {e}", exc_info=True)
            return {
                "success": False,
                "message": f"HubSpot connection test failed: {str(e)}",
                "details": {},
            }

    # ========================================================================
    # Contact Methods
    # ========================================================================

    async def create_contact(
        self,
        email: str,
        first_name: Optional[str] = None,
        last_name: Optional[str] = None,
        phone: Optional[str] = None,
        company: Optional[str] = None,
        website: Optional[str] = None,
        additional_properties: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Create a new contact in HubSpot.

        Args:
            email: Contact's email (required)
            first_name: Contact's first name
            last_name: Contact's last name
            phone: Contact's phone number
            company: Company name
            website: Website URL
            additional_properties: Additional HubSpot properties

        Returns:
            Created contact data including ID

        Raises:
            ConnectorError: If contact creation fails
        """
        try:
            # Build contact properties
            properties = {"email": email}

            if first_name:
                properties["firstname"] = first_name
            if last_name:
                properties["lastname"] = last_name
            if phone:
                properties["phone"] = phone
            if company:
                properties["company"] = company
            if website:
                properties["website"] = website

            # Add additional properties
            if additional_properties:
                properties.update(additional_properties)

            # Create contact
            response = await self.post(
                "/crm/v3/objects/contacts",
                json={"properties": properties},
            )

            logger.info(f"HubSpot contact created: {response.get('id')}")

            return {
                "id": response.get("id"),
                "properties": response.get("properties", {}),
                "created_at": response.get("createdAt"),
                "updated_at": response.get("updatedAt"),
            }

        except Exception as e:
            logger.error(f"Failed to create HubSpot contact: {e}", exc_info=True)
            raise ConnectorError(f"Failed to create contact: {str(e)}")

    async def update_contact(
        self,
        contact_id: str,
        properties: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Update an existing contact in HubSpot.

        Args:
            contact_id: HubSpot contact ID
            properties: Properties to update

        Returns:
            Updated contact data

        Raises:
            ConnectorError: If update fails
        """
        try:
            response = await self.patch(
                f"/crm/v3/objects/contacts/{contact_id}",
                json={"properties": properties},
            )

            logger.info(f"HubSpot contact updated: {contact_id}")

            return {
                "id": response.get("id"),
                "properties": response.get("properties", {}),
                "updated_at": response.get("updatedAt"),
            }

        except Exception as e:
            logger.error(f"Failed to update HubSpot contact: {e}", exc_info=True)
            raise ConnectorError(f"Failed to update contact: {str(e)}")

    async def get_contact(
        self,
        contact_id: str,
        properties: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Get a contact by ID.

        Args:
            contact_id: HubSpot contact ID
            properties: List of properties to retrieve

        Returns:
            Contact data

        Raises:
            ConnectorError: If retrieval fails
        """
        try:
            params = {}
            if properties:
                params["properties"] = ",".join(properties)

            contact = await self.get(
                f"/crm/v3/objects/contacts/{contact_id}",
                params=params,
            )

            return {
                "id": contact.get("id"),
                "properties": contact.get("properties", {}),
                "created_at": contact.get("createdAt"),
                "updated_at": contact.get("updatedAt"),
            }

        except Exception as e:
            logger.error(f"Failed to get HubSpot contact: {e}", exc_info=True)
            raise ConnectorError(f"Failed to get contact: {str(e)}")

    async def delete_contact(self, contact_id: str) -> Dict[str, Any]:
        """
        Delete a contact.

        Args:
            contact_id: HubSpot contact ID

        Returns:
            Deletion result

        Raises:
            ConnectorError: If deletion fails
        """
        try:
            await self.delete(f"/crm/v3/objects/contacts/{contact_id}")

            logger.info(f"HubSpot contact deleted: {contact_id}")

            return {
                "id": contact_id,
                "success": True,
            }

        except Exception as e:
            logger.error(f"Failed to delete HubSpot contact: {e}", exc_info=True)
            raise ConnectorError(f"Failed to delete contact: {str(e)}")

    async def search_contacts(
        self,
        filters: List[Dict[str, Any]],
        limit: int = 100,
        properties: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Search for contacts using filters.

        Args:
            filters: List of filter objects (e.g., [{"propertyName": "email", "operator": "EQ", "value": "test@example.com"}])
            limit: Maximum number of results
            properties: Properties to retrieve

        Returns:
            Search results with contacts

        Raises:
            ConnectorError: If search fails
        """
        try:
            search_request = {
                "filterGroups": [{"filters": filters}],
                "limit": limit,
            }

            if properties:
                search_request["properties"] = properties

            response = await self.post(
                "/crm/v3/objects/contacts/search",
                json=search_request,
            )

            return {
                "total": response.get("total", 0),
                "results": response.get("results", []),
            }

        except Exception as e:
            logger.error(f"Failed to search HubSpot contacts: {e}", exc_info=True)
            raise ConnectorError(f"Failed to search contacts: {str(e)}")

    # ========================================================================
    # Company Methods
    # ========================================================================

    async def create_company(
        self,
        name: str,
        domain: Optional[str] = None,
        industry: Optional[str] = None,
        phone: Optional[str] = None,
        city: Optional[str] = None,
        state: Optional[str] = None,
        additional_properties: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Create a new company in HubSpot.

        Args:
            name: Company name (required)
            domain: Company domain
            industry: Industry
            phone: Phone number
            city: City
            state: State/province
            additional_properties: Additional HubSpot properties

        Returns:
            Created company data including ID

        Raises:
            ConnectorError: If company creation fails
        """
        try:
            # Build company properties
            properties = {"name": name}

            if domain:
                properties["domain"] = domain
            if industry:
                properties["industry"] = industry
            if phone:
                properties["phone"] = phone
            if city:
                properties["city"] = city
            if state:
                properties["state"] = state

            # Add additional properties
            if additional_properties:
                properties.update(additional_properties)

            # Create company
            response = await self.post(
                "/crm/v3/objects/companies",
                json={"properties": properties},
            )

            logger.info(f"HubSpot company created: {response.get('id')}")

            return {
                "id": response.get("id"),
                "properties": response.get("properties", {}),
                "created_at": response.get("createdAt"),
                "updated_at": response.get("updatedAt"),
            }

        except Exception as e:
            logger.error(f"Failed to create HubSpot company: {e}", exc_info=True)
            raise ConnectorError(f"Failed to create company: {str(e)}")

    async def update_company(
        self,
        company_id: str,
        properties: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Update an existing company in HubSpot.

        Args:
            company_id: HubSpot company ID
            properties: Properties to update

        Returns:
            Updated company data

        Raises:
            ConnectorError: If update fails
        """
        try:
            response = await self.patch(
                f"/crm/v3/objects/companies/{company_id}",
                json={"properties": properties},
            )

            logger.info(f"HubSpot company updated: {company_id}")

            return {
                "id": response.get("id"),
                "properties": response.get("properties", {}),
                "updated_at": response.get("updatedAt"),
            }

        except Exception as e:
            logger.error(f"Failed to update HubSpot company: {e}", exc_info=True)
            raise ConnectorError(f"Failed to update company: {str(e)}")

    # ========================================================================
    # Deal Methods
    # ========================================================================

    async def create_deal(
        self,
        deal_name: str,
        pipeline: str,
        deal_stage: str,
        amount: Optional[float] = None,
        close_date: Optional[str] = None,
        additional_properties: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Create a new deal in HubSpot.

        Args:
            deal_name: Deal name (required)
            pipeline: Pipeline ID
            deal_stage: Deal stage ID
            amount: Deal amount
            close_date: Expected close date (YYYY-MM-DD)
            additional_properties: Additional HubSpot properties

        Returns:
            Created deal data including ID

        Raises:
            ConnectorError: If deal creation fails
        """
        try:
            # Build deal properties
            properties = {
                "dealname": deal_name,
                "pipeline": pipeline,
                "dealstage": deal_stage,
            }

            if amount is not None:
                properties["amount"] = str(amount)
            if close_date:
                properties["closedate"] = close_date

            # Add additional properties
            if additional_properties:
                properties.update(additional_properties)

            # Create deal
            response = await self.post(
                "/crm/v3/objects/deals",
                json={"properties": properties},
            )

            logger.info(f"HubSpot deal created: {response.get('id')}")

            return {
                "id": response.get("id"),
                "properties": response.get("properties", {}),
                "created_at": response.get("createdAt"),
                "updated_at": response.get("updatedAt"),
            }

        except Exception as e:
            logger.error(f"Failed to create HubSpot deal: {e}", exc_info=True)
            raise ConnectorError(f"Failed to create deal: {str(e)}")

    async def update_deal(
        self,
        deal_id: str,
        properties: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Update an existing deal in HubSpot.

        Args:
            deal_id: HubSpot deal ID
            properties: Properties to update

        Returns:
            Updated deal data

        Raises:
            ConnectorError: If update fails
        """
        try:
            response = await self.patch(
                f"/crm/v3/objects/deals/{deal_id}",
                json={"properties": properties},
            )

            logger.info(f"HubSpot deal updated: {deal_id}")

            return {
                "id": response.get("id"),
                "properties": response.get("properties", {}),
                "updated_at": response.get("updatedAt"),
            }

        except Exception as e:
            logger.error(f"Failed to update HubSpot deal: {e}", exc_info=True)
            raise ConnectorError(f"Failed to update deal: {str(e)}")

    # ========================================================================
    # Association Methods
    # ========================================================================

    async def associate_objects(
        self,
        from_object_type: str,
        from_object_id: str,
        to_object_type: str,
        to_object_id: str,
        association_type_id: int,
    ) -> Dict[str, Any]:
        """
        Create an association between two objects.

        Args:
            from_object_type: Source object type (e.g., "contacts")
            from_object_id: Source object ID
            to_object_type: Target object type (e.g., "companies")
            to_object_id: Target object ID
            association_type_id: Association type ID

        Returns:
            Association result

        Raises:
            ConnectorError: If association fails
        """
        try:
            await self.put(
                f"/crm/v3/objects/{from_object_type}/{from_object_id}/associations/{to_object_type}/{to_object_id}/{association_type_id}"
            )

            logger.info(
                f"HubSpot association created: {from_object_type}/{from_object_id} -> {to_object_type}/{to_object_id}"
            )

            return {
                "success": True,
                "from_object_id": from_object_id,
                "to_object_id": to_object_id,
            }

        except Exception as e:
            logger.error(f"Failed to create HubSpot association: {e}", exc_info=True)
            raise ConnectorError(f"Failed to create association: {str(e)}")

    # ========================================================================
    # Analytics Methods
    # ========================================================================

    async def get_analytics(
        self,
        object_type: str = "contacts",
    ) -> Dict[str, Any]:
        """
        Get analytics for object type.

        Args:
            object_type: Object type (contacts, companies, deals)

        Returns:
            Analytics data

        Raises:
            ConnectorError: If retrieval fails
        """
        try:
            # Get total count
            response = await self.get(
                f"/crm/v3/objects/{object_type}",
                params={"limit": 1},
            )

            total = response.get("total", 0)

            return {
                "object_type": object_type,
                "total_count": total,
            }

        except Exception as e:
            logger.error(f"Failed to get HubSpot analytics: {e}", exc_info=True)
            raise ConnectorError(f"Failed to get analytics: {str(e)}")

    # ========================================================================
    # Batch Operations
    # ========================================================================

    async def batch_create_contacts(
        self,
        contacts: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        Create multiple contacts in a single batch.

        Args:
            contacts: List of contact property dictionaries

        Returns:
            Batch creation results

        Raises:
            ConnectorError: If batch creation fails
        """
        try:
            inputs = [{"properties": contact} for contact in contacts]

            response = await self.post(
                "/crm/v3/objects/contacts/batch/create",
                json={"inputs": inputs},
            )

            logger.info(f"HubSpot batch created {len(contacts)} contacts")

            return {
                "status": response.get("status"),
                "results": response.get("results", []),
                "num_errors": response.get("numErrors", 0),
            }

        except Exception as e:
            logger.error(f"Failed to batch create HubSpot contacts: {e}", exc_info=True)
            raise ConnectorError(f"Failed to batch create contacts: {str(e)}")

    async def batch_update_contacts(
        self,
        updates: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        Update multiple contacts in a single batch.

        Args:
            updates: List of update objects with 'id' and 'properties'

        Returns:
            Batch update results

        Raises:
            ConnectorError: If batch update fails
        """
        try:
            response = await self.post(
                "/crm/v3/objects/contacts/batch/update",
                json={"inputs": updates},
            )

            logger.info(f"HubSpot batch updated {len(updates)} contacts")

            return {
                "status": response.get("status"),
                "results": response.get("results", []),
                "num_errors": response.get("numErrors", 0),
            }

        except Exception as e:
            logger.error(f"Failed to batch update HubSpot contacts: {e}", exc_info=True)
            raise ConnectorError(f"Failed to batch update contacts: {str(e)}")
