"""
Stripe Connector.

Integration with Stripe Payment API.
"""
import logging
from typing import Dict, Any, Optional, List

from app.services.integrations.connector_base import BaseConnector, ConnectorError

logger = logging.getLogger(__name__)


class StripeConnector(BaseConnector):
    """
    Stripe payment connector.

    Provides methods to interact with Stripe API:
    - Create/retrieve customers
    - Create/manage payment methods
    - Create payment intents
    - Create subscriptions
    - Manage invoices
    - Handle refunds
    - Get balance and transactions
    """

    async def test_connection(self) -> Dict[str, Any]:
        """
        Test Stripe connection by fetching account info.

        Returns:
            Test result dictionary
        """
        try:
            # Get account info
            account = await self.get("/v1/account")

            return {
                "success": True,
                "message": "Stripe connection successful",
                "details": {
                    "account_id": account.get("id"),
                    "business_name": account.get("business_profile", {}).get("name"),
                    "country": account.get("country"),
                    "currency": account.get("default_currency"),
                },
            }

        except Exception as e:
            logger.error(f"Stripe connection test failed: {e}", exc_info=True)
            return {
                "success": False,
                "message": f"Stripe connection test failed: {str(e)}",
                "details": {},
            }

    # ========================================================================
    # Customer Methods
    # ========================================================================

    async def create_customer(
        self,
        email: str,
        name: Optional[str] = None,
        phone: Optional[str] = None,
        description: Optional[str] = None,
        metadata: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """
        Create a new customer.

        Args:
            email: Customer email
            name: Customer name
            phone: Customer phone
            description: Customer description
            metadata: Custom metadata

        Returns:
            Created customer data

        Raises:
            ConnectorError: If creation fails
        """
        try:
            customer_data = {"email": email}

            if name:
                customer_data["name"] = name
            if phone:
                customer_data["phone"] = phone
            if description:
                customer_data["description"] = description
            if metadata:
                customer_data["metadata"] = metadata

            response = await self.post("/v1/customers", data=customer_data)

            logger.info(f"Stripe customer created: {response.get('id')}")

            return {
                "id": response.get("id"),
                "email": response.get("email"),
                "name": response.get("name"),
                "created": response.get("created"),
            }

        except Exception as e:
            logger.error(f"Failed to create Stripe customer: {e}", exc_info=True)
            raise ConnectorError(f"Failed to create customer: {str(e)}")

    async def get_customer(self, customer_id: str) -> Dict[str, Any]:
        """
        Retrieve a customer by ID.

        Args:
            customer_id: Stripe customer ID

        Returns:
            Customer data

        Raises:
            ConnectorError: If retrieval fails
        """
        try:
            response = await self.get(f"/v1/customers/{customer_id}")

            return {
                "id": response.get("id"),
                "email": response.get("email"),
                "name": response.get("name"),
                "phone": response.get("phone"),
                "description": response.get("description"),
                "balance": response.get("balance"),
                "currency": response.get("currency"),
                "metadata": response.get("metadata", {}),
                "created": response.get("created"),
            }

        except Exception as e:
            logger.error(f"Failed to get Stripe customer: {e}", exc_info=True)
            raise ConnectorError(f"Failed to get customer: {str(e)}")

    async def update_customer(
        self,
        customer_id: str,
        email: Optional[str] = None,
        name: Optional[str] = None,
        phone: Optional[str] = None,
        description: Optional[str] = None,
        metadata: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """
        Update a customer.

        Args:
            customer_id: Stripe customer ID
            email: New email
            name: New name
            phone: New phone
            description: New description
            metadata: New metadata

        Returns:
            Updated customer data

        Raises:
            ConnectorError: If update fails
        """
        try:
            update_data = {}

            if email:
                update_data["email"] = email
            if name:
                update_data["name"] = name
            if phone:
                update_data["phone"] = phone
            if description:
                update_data["description"] = description
            if metadata:
                update_data["metadata"] = metadata

            response = await self.post(f"/v1/customers/{customer_id}", data=update_data)

            logger.info(f"Stripe customer updated: {customer_id}")

            return {
                "id": response.get("id"),
                "email": response.get("email"),
                "name": response.get("name"),
            }

        except Exception as e:
            logger.error(f"Failed to update Stripe customer: {e}", exc_info=True)
            raise ConnectorError(f"Failed to update customer: {str(e)}")

    async def delete_customer(self, customer_id: str) -> Dict[str, Any]:
        """
        Delete a customer.

        Args:
            customer_id: Stripe customer ID

        Returns:
            Deletion result

        Raises:
            ConnectorError: If deletion fails
        """
        try:
            response = await self.delete(f"/v1/customers/{customer_id}")

            logger.info(f"Stripe customer deleted: {customer_id}")

            return {
                "id": response.get("id"),
                "deleted": response.get("deleted", False),
            }

        except Exception as e:
            logger.error(f"Failed to delete Stripe customer: {e}", exc_info=True)
            raise ConnectorError(f"Failed to delete customer: {str(e)}")

    # ========================================================================
    # Payment Intent Methods
    # ========================================================================

    async def create_payment_intent(
        self,
        amount: int,
        currency: str = "usd",
        customer: Optional[str] = None,
        payment_method: Optional[str] = None,
        description: Optional[str] = None,
        metadata: Optional[Dict[str, str]] = None,
        automatic_payment_methods: bool = True,
    ) -> Dict[str, Any]:
        """
        Create a payment intent.

        Args:
            amount: Amount in cents (e.g., 1000 = $10.00)
            currency: Currency code (default: "usd")
            customer: Customer ID
            payment_method: Payment method ID
            description: Payment description
            metadata: Custom metadata
            automatic_payment_methods: Enable automatic payment methods

        Returns:
            Created payment intent data

        Raises:
            ConnectorError: If creation fails
        """
        try:
            intent_data = {
                "amount": amount,
                "currency": currency,
            }

            if customer:
                intent_data["customer"] = customer
            if payment_method:
                intent_data["payment_method"] = payment_method
            if description:
                intent_data["description"] = description
            if metadata:
                intent_data["metadata"] = metadata
            if automatic_payment_methods:
                intent_data["automatic_payment_methods"] = {"enabled": True}

            response = await self.post("/v1/payment_intents", data=intent_data)

            logger.info(f"Stripe payment intent created: {response.get('id')}")

            return {
                "id": response.get("id"),
                "amount": response.get("amount"),
                "currency": response.get("currency"),
                "status": response.get("status"),
                "client_secret": response.get("client_secret"),
                "created": response.get("created"),
            }

        except Exception as e:
            logger.error(f"Failed to create Stripe payment intent: {e}", exc_info=True)
            raise ConnectorError(f"Failed to create payment intent: {str(e)}")

    async def confirm_payment_intent(
        self,
        intent_id: str,
        payment_method: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Confirm a payment intent.

        Args:
            intent_id: Payment intent ID
            payment_method: Payment method ID

        Returns:
            Confirmed payment intent data

        Raises:
            ConnectorError: If confirmation fails
        """
        try:
            confirm_data = {}

            if payment_method:
                confirm_data["payment_method"] = payment_method

            response = await self.post(
                f"/v1/payment_intents/{intent_id}/confirm",
                data=confirm_data,
            )

            logger.info(f"Stripe payment intent confirmed: {intent_id}")

            return {
                "id": response.get("id"),
                "status": response.get("status"),
                "amount": response.get("amount"),
            }

        except Exception as e:
            logger.error(f"Failed to confirm Stripe payment intent: {e}", exc_info=True)
            raise ConnectorError(f"Failed to confirm payment intent: {str(e)}")

    async def cancel_payment_intent(
        self,
        intent_id: str,
    ) -> Dict[str, Any]:
        """
        Cancel a payment intent.

        Args:
            intent_id: Payment intent ID

        Returns:
            Cancelled payment intent data

        Raises:
            ConnectorError: If cancellation fails
        """
        try:
            response = await self.post(f"/v1/payment_intents/{intent_id}/cancel")

            logger.info(f"Stripe payment intent cancelled: {intent_id}")

            return {
                "id": response.get("id"),
                "status": response.get("status"),
            }

        except Exception as e:
            logger.error(f"Failed to cancel Stripe payment intent: {e}", exc_info=True)
            raise ConnectorError(f"Failed to cancel payment intent: {str(e)}")

    # ========================================================================
    # Subscription Methods
    # ========================================================================

    async def create_subscription(
        self,
        customer: str,
        items: List[Dict[str, Any]],
        trial_period_days: Optional[int] = None,
        metadata: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """
        Create a subscription.

        Args:
            customer: Customer ID
            items: List of subscription items (e.g., [{"price": "price_xxx"}])
            trial_period_days: Trial period in days
            metadata: Custom metadata

        Returns:
            Created subscription data

        Raises:
            ConnectorError: If creation fails
        """
        try:
            subscription_data = {
                "customer": customer,
                "items": items,
            }

            if trial_period_days is not None:
                subscription_data["trial_period_days"] = trial_period_days
            if metadata:
                subscription_data["metadata"] = metadata

            response = await self.post("/v1/subscriptions", data=subscription_data)

            logger.info(f"Stripe subscription created: {response.get('id')}")

            return {
                "id": response.get("id"),
                "customer": response.get("customer"),
                "status": response.get("status"),
                "current_period_start": response.get("current_period_start"),
                "current_period_end": response.get("current_period_end"),
                "created": response.get("created"),
            }

        except Exception as e:
            logger.error(f"Failed to create Stripe subscription: {e}", exc_info=True)
            raise ConnectorError(f"Failed to create subscription: {str(e)}")

    async def cancel_subscription(
        self,
        subscription_id: str,
        immediately: bool = False,
    ) -> Dict[str, Any]:
        """
        Cancel a subscription.

        Args:
            subscription_id: Subscription ID
            immediately: Cancel immediately (vs at period end)

        Returns:
            Cancelled subscription data

        Raises:
            ConnectorError: If cancellation fails
        """
        try:
            if immediately:
                response = await self.delete(f"/v1/subscriptions/{subscription_id}")
            else:
                # Cancel at period end
                response = await self.post(
                    f"/v1/subscriptions/{subscription_id}",
                    data={"cancel_at_period_end": True},
                )

            logger.info(f"Stripe subscription cancelled: {subscription_id}")

            return {
                "id": response.get("id"),
                "status": response.get("status"),
                "cancel_at_period_end": response.get("cancel_at_period_end"),
            }

        except Exception as e:
            logger.error(f"Failed to cancel Stripe subscription: {e}", exc_info=True)
            raise ConnectorError(f"Failed to cancel subscription: {str(e)}")

    # ========================================================================
    # Refund Methods
    # ========================================================================

    async def create_refund(
        self,
        payment_intent: str,
        amount: Optional[int] = None,
        reason: Optional[str] = None,
        metadata: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """
        Create a refund.

        Args:
            payment_intent: Payment intent ID
            amount: Amount to refund in cents (None = full refund)
            reason: Refund reason (duplicate, fraudulent, requested_by_customer)
            metadata: Custom metadata

        Returns:
            Created refund data

        Raises:
            ConnectorError: If creation fails
        """
        try:
            refund_data = {"payment_intent": payment_intent}

            if amount is not None:
                refund_data["amount"] = amount
            if reason:
                refund_data["reason"] = reason
            if metadata:
                refund_data["metadata"] = metadata

            response = await self.post("/v1/refunds", data=refund_data)

            logger.info(f"Stripe refund created: {response.get('id')}")

            return {
                "id": response.get("id"),
                "amount": response.get("amount"),
                "status": response.get("status"),
                "reason": response.get("reason"),
                "created": response.get("created"),
            }

        except Exception as e:
            logger.error(f"Failed to create Stripe refund: {e}", exc_info=True)
            raise ConnectorError(f"Failed to create refund: {str(e)}")

    # ========================================================================
    # Invoice Methods
    # ========================================================================

    async def create_invoice(
        self,
        customer: str,
        auto_advance: bool = True,
        collection_method: str = "charge_automatically",
        description: Optional[str] = None,
        metadata: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """
        Create an invoice.

        Args:
            customer: Customer ID
            auto_advance: Automatically finalize invoice
            collection_method: Collection method (charge_automatically, send_invoice)
            description: Invoice description
            metadata: Custom metadata

        Returns:
            Created invoice data

        Raises:
            ConnectorError: If creation fails
        """
        try:
            invoice_data = {
                "customer": customer,
                "auto_advance": auto_advance,
                "collection_method": collection_method,
            }

            if description:
                invoice_data["description"] = description
            if metadata:
                invoice_data["metadata"] = metadata

            response = await self.post("/v1/invoices", data=invoice_data)

            logger.info(f"Stripe invoice created: {response.get('id')}")

            return {
                "id": response.get("id"),
                "customer": response.get("customer"),
                "status": response.get("status"),
                "total": response.get("total"),
                "created": response.get("created"),
            }

        except Exception as e:
            logger.error(f"Failed to create Stripe invoice: {e}", exc_info=True)
            raise ConnectorError(f"Failed to create invoice: {str(e)}")

    async def finalize_invoice(
        self,
        invoice_id: str,
    ) -> Dict[str, Any]:
        """
        Finalize an invoice.

        Args:
            invoice_id: Invoice ID

        Returns:
            Finalized invoice data

        Raises:
            ConnectorError: If finalization fails
        """
        try:
            response = await self.post(f"/v1/invoices/{invoice_id}/finalize")

            logger.info(f"Stripe invoice finalized: {invoice_id}")

            return {
                "id": response.get("id"),
                "status": response.get("status"),
                "hosted_invoice_url": response.get("hosted_invoice_url"),
            }

        except Exception as e:
            logger.error(f"Failed to finalize Stripe invoice: {e}", exc_info=True)
            raise ConnectorError(f"Failed to finalize invoice: {str(e)}")

    async def pay_invoice(
        self,
        invoice_id: str,
    ) -> Dict[str, Any]:
        """
        Pay an invoice.

        Args:
            invoice_id: Invoice ID

        Returns:
            Paid invoice data

        Raises:
            ConnectorError: If payment fails
        """
        try:
            response = await self.post(f"/v1/invoices/{invoice_id}/pay")

            logger.info(f"Stripe invoice paid: {invoice_id}")

            return {
                "id": response.get("id"),
                "status": response.get("status"),
                "amount_paid": response.get("amount_paid"),
            }

        except Exception as e:
            logger.error(f"Failed to pay Stripe invoice: {e}", exc_info=True)
            raise ConnectorError(f"Failed to pay invoice: {str(e)}")

    # ========================================================================
    # Balance & Transaction Methods
    # ========================================================================

    async def get_balance(self) -> Dict[str, Any]:
        """
        Get account balance.

        Returns:
            Balance information

        Raises:
            ConnectorError: If retrieval fails
        """
        try:
            response = await self.get("/v1/balance")

            return {
                "available": response.get("available", []),
                "pending": response.get("pending", []),
            }

        except Exception as e:
            logger.error(f"Failed to get Stripe balance: {e}", exc_info=True)
            raise ConnectorError(f"Failed to get balance: {str(e)}")

    async def list_charges(
        self,
        customer: Optional[str] = None,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """
        List charges.

        Args:
            customer: Filter by customer ID
            limit: Number of charges to retrieve

        Returns:
            List of charges

        Raises:
            ConnectorError: If retrieval fails
        """
        try:
            params = {"limit": limit}

            if customer:
                params["customer"] = customer

            response = await self.get("/v1/charges", params=params)

            charges = response.get("data", [])

            return [
                {
                    "id": charge.get("id"),
                    "amount": charge.get("amount"),
                    "currency": charge.get("currency"),
                    "status": charge.get("status"),
                    "customer": charge.get("customer"),
                    "description": charge.get("description"),
                    "created": charge.get("created"),
                }
                for charge in charges
            ]

        except Exception as e:
            logger.error(f"Failed to list Stripe charges: {e}", exc_info=True)
            raise ConnectorError(f"Failed to list charges: {str(e)}")
