"""
Stripe Connector.

Integration with Stripe Payment API.
"""
import json
import logging
from typing import Dict, Any, Optional, List
from urllib.parse import quote

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

    async def post(self, endpoint: str, **kwargs) -> Dict[str, Any]:
        """POST with the body in Stripe's form encoding (see ``_form``)."""
        if kwargs.get("data"):
            kwargs["data"] = _form(kwargs["data"])
        return await super().post(endpoint, **kwargs)

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
            raise ConnectorError(f"Failed to create customer: {_reason(e)}")

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
            raise ConnectorError(f"Failed to get customer: {_reason(e)}")

    async def find_customers(self, email: str, limit: int = 5) -> Dict[str, Any]:
        """Customers with this email (Stripe matches it exactly, ignoring case)."""
        if not (email or "").strip():
            raise ConnectorError("Give the customer's email to look them up.")
        try:
            response = await self.get("/v1/customers", params={"email": email.strip(), "limit": max(1, min(int(limit or 5), 20))})
        except Exception as e:
            raise ConnectorError(f"Failed to find customers: {_reason(e)}")
        customers = [
            {"id": c.get("id"), "name": c.get("name"), "email": c.get("email"), "phone": c.get("phone")}
            for c in response.get("data", [])
        ]
        return {"customers": customers, "count": len(customers)}

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
            raise ConnectorError(f"Failed to update customer: {_reason(e)}")

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
            raise ConnectorError(f"Failed to delete customer: {_reason(e)}")

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

            result = {
                "id": response.get("id"),
                "amount": response.get("amount"),
                "currency": response.get("currency"),
                "status": response.get("status"),
                "client_secret": response.get("client_secret"),
                "created": response.get("created"),
            }
            # An intent is only the start of a payment. Without this an agent
            # reads "created" as "paid" and tells the caller so.
            if response.get("status") != "succeeded":
                result["message"] = (
                    "No money has been taken yet: this payment still needs a card. "
                    "To get paid, send the customer a payment link or an invoice."
                )
            return result

        except Exception as e:
            logger.error(f"Failed to create Stripe payment intent: {e}", exc_info=True)
            raise ConnectorError(f"Failed to create payment intent: {_reason(e)}")

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
            raise ConnectorError(f"Failed to confirm payment intent: {_reason(e)}")

    async def get_payment_intent(self, intent_id: str) -> Dict[str, Any]:
        """A payment intent by id."""
        try:
            pi = await self.get(f"/v1/payment_intents/{intent_id}")
        except Exception as e:
            raise ConnectorError(f"Failed to get payment intent: {_reason(e)}")
        return {"id": pi.get("id"), "amount": pi.get("amount"), "currency": pi.get("currency"),
                "status": pi.get("status"), "customer": pi.get("customer"), "description": pi.get("description")}

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
            raise ConnectorError(f"Failed to cancel payment intent: {_reason(e)}")

    # ========================================================================
    # Payment Link Methods
    # ========================================================================

    async def create_payment_link(
        self,
        amount: int,
        description: str,
        currency: str = "usd",
        email: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Create a link to a Stripe-hosted page where the customer pays by card.

        The link takes one payment and then closes, so a link shared twice
        cannot be paid twice. Stripe does not send it to anyone: the caller of
        this method shares the URL.

        Args:
            amount: Amount in the smallest currency unit (e.g., 1000 = $10.00)
            description: What the payment is for, shown on the payment page
            currency: Currency code (default: "usd")
            email: Customer email, filled in on the payment page for them

        Returns:
            The payment link and its URL

        Raises:
            ConnectorError: If creation fails
        """
        amount = _minor_units(amount)
        if not (description or "").strip():
            raise ConnectorError("Say what the payment is for.")
        try:
            # A payment link sells a price, so the amount becomes one first.
            price = await self.post("/v1/prices", data={
                "unit_amount": amount,
                "currency": _currency(currency),
                "product_data": {"name": description.strip()},
            })
            link = await self.post("/v1/payment_links", data={
                "line_items": [{"price": price.get("id"), "quantity": 1}],
                "restrictions": {"completed_sessions": {"limit": 1}},
            })
        except Exception as e:
            logger.error(f"Failed to create Stripe payment link: {e}", exc_info=True)
            raise ConnectorError(f"Failed to create payment link: {_reason(e)}")

        logger.info(f"Stripe payment link created: {link.get('id')}")

        url = link.get("url")
        if url and (email or "").strip():
            url = f"{url}?prefilled_email={quote(email.strip())}"
        return {
            "id": link.get("id"),
            "url": url,
            "amount": amount,
            "currency": _currency(currency),
            "description": description.strip(),
            "message": (
                "Nothing has been paid yet and Stripe has not sent this link to anyone. "
                "Give the customer the url in a message; do not read it out loud."
            ),
        }

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
            raise ConnectorError(f"Failed to create subscription: {_reason(e)}")

    async def get_subscription(self, subscription_id: str) -> Dict[str, Any]:
        """A subscription by id."""
        try:
            sub = await self.get(f"/v1/subscriptions/{subscription_id}")
        except Exception as e:
            raise ConnectorError(f"Failed to get subscription: {_reason(e)}")
        return _subscription_summary(sub)

    async def list_subscriptions(self, customer_id: str, status: str = "active") -> Dict[str, Any]:
        """A customer's subscriptions: the lookup before cancelling one."""
        try:
            response = await self.get("/v1/subscriptions", params={"customer": customer_id, "status": status or "all", "limit": 20})
        except Exception as e:
            raise ConnectorError(f"Failed to list subscriptions: {_reason(e)}")
        subs = [_subscription_summary(s) for s in response.get("data", [])]
        return {"subscriptions": subs, "count": len(subs)}

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
            raise ConnectorError(f"Failed to cancel subscription: {_reason(e)}")

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
            raise ConnectorError(f"Failed to create refund: {_reason(e)}")

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
            raise ConnectorError(f"Failed to create invoice: {_reason(e)}")

    async def send_invoice(
        self,
        amount: int,
        description: str,
        email: Optional[str] = None,
        customer_id: Optional[str] = None,
        name: Optional[str] = None,
        currency: str = "usd",
        days_until_due: int = 7,
    ) -> Dict[str, Any]:
        """
        Bill a customer by email: Stripe sends them an invoice with a pay link.

        The customer is ``customer_id`` when given, otherwise the existing
        customer with that email, otherwise a new one.

        Args:
            amount: Amount in the smallest currency unit (e.g., 1000 = $10.00)
            description: What the invoice is for, shown as its one line
            email: Where the invoice is sent (needed unless customer_id is given)
            customer_id: Existing Stripe customer to bill
            name: Customer name, used when a new customer is created
            currency: Currency code (default: "usd")
            days_until_due: Days the customer has to pay

        Returns:
            The sent invoice and its hosted payment page

        Raises:
            ConnectorError: If the invoice could not be sent
        """
        amount = _minor_units(amount)
        if not (description or "").strip():
            raise ConnectorError("Say what the invoice is for.")
        email = (email or "").strip()
        if not customer_id and not email:
            raise ConnectorError("Give the customer's email address to send the invoice to.")

        invoice_id = None
        try:
            if not customer_id:
                found = await self.find_customers(email, limit=1)
                if found["customers"]:
                    customer_id = found["customers"][0]["id"]
                else:
                    customer_id = (await self.create_customer(email=email, name=name))["id"]

            invoice = await self.post("/v1/invoices", data={
                "customer": customer_id,
                "collection_method": "send_invoice",
                "days_until_due": max(1, int(days_until_due or 7)),
                "currency": _currency(currency),
                "description": description.strip(),
                # Only what this call bills. Anything already pending on the
                # customer stays off this invoice.
                "pending_invoice_items_behavior": "exclude",
                "auto_advance": False,
            })
            invoice_id = invoice.get("id")
            await self.post("/v1/invoiceitems", data={
                "customer": customer_id,
                "invoice": invoice_id,
                "amount": amount,
                "currency": _currency(currency),
                "description": description.strip(),
            })
            await self.post(f"/v1/invoices/{invoice_id}/finalize")
            sent = await self.post(f"/v1/invoices/{invoice_id}/send")
        except Exception as e:
            logger.error(f"Failed to send Stripe invoice: {e}", exc_info=True)
            await self._discard_draft_invoice(invoice_id)
            raise ConnectorError(f"Failed to send invoice: {_reason(e)}")

        logger.info(f"Stripe invoice sent: {invoice_id}")

        return {
            "id": sent.get("id"),
            "number": sent.get("number"),
            "customer": customer_id,
            "sent_to": sent.get("customer_email") or email or None,
            "amount_due": sent.get("amount_due"),
            "currency": sent.get("currency"),
            "status": sent.get("status"),
            "due_date": sent.get("due_date"),
            "hosted_invoice_url": sent.get("hosted_invoice_url"),
            "message": "The invoice was emailed to the customer with a link to pay it. Nothing has been paid yet.",
        }

    async def _discard_draft_invoice(self, invoice_id: Optional[str]) -> None:
        """Remove an invoice that failed part-way, so no stray draft is left."""
        if not invoice_id:
            return
        try:
            # Stripe only deletes drafts; a finalized invoice is left as it is.
            await self.delete(f"/v1/invoices/{invoice_id}")
        except Exception as e:  # noqa: BLE001 - the original error is the one to report
            logger.info(f"Left Stripe invoice {invoice_id} in place: {e}")

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
            raise ConnectorError(f"Failed to finalize invoice: {_reason(e)}")

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
            raise ConnectorError(f"Failed to pay invoice: {_reason(e)}")

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
            raise ConnectorError(f"Failed to get balance: {_reason(e)}")

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
            raise ConnectorError(f"Failed to list charges: {_reason(e)}")


def _form(data: Dict[str, Any], prefix: str = "") -> Dict[str, Any]:
    """Flatten a request body into Stripe's form encoding.

    Stripe takes form bodies, with nested values written in brackets:
    ``automatic_payment_methods[enabled]=true``, ``items[0][price]=price_x``.
    Handed a nested dict as it is, the HTTP client sends its Python repr
    (``{'enabled': True}``) and Stripe answers 400 "Invalid object". Every
    payment intent failed that way, as did subscriptions and anything carrying
    metadata.
    """
    flat: Dict[str, Any] = {}
    for key, value in data.items():
        name = f"{prefix}[{key}]" if prefix else str(key)
        if value is None:
            continue
        if isinstance(value, dict):
            flat.update(_form(value, name))
        elif isinstance(value, (list, tuple)):
            flat.update(_form(dict(enumerate(value)), name))
        elif isinstance(value, bool):
            flat[name] = "true" if value else "false"
        else:
            flat[name] = value
    return flat


def _reason(error: Exception) -> str:
    """Stripe's own sentence for a failed request, without the HTTP wrapping.

    A failure arrives as ``Request failed: HTTP 400: {"error": {...}}``. The
    ``message`` inside is written for people ("Amount must be at least $0.50
    usd") and is what an agent should be given to say.
    """
    text = str(error)
    start = text.find("{")
    if start != -1:
        try:
            message = (json.loads(text[start:]).get("error") or {}).get("message")
        except (ValueError, AttributeError):
            message = None
        if message:
            return str(message)
    return text


def _minor_units(amount: Any) -> int:
    """An amount as a whole number of the currency's smallest unit."""
    try:
        value = float(amount)
    except (TypeError, ValueError):
        value = 0
    if value <= 0 or value != int(value):
        raise ConnectorError(
            "The amount must be a whole number in the smallest currency unit "
            "(cents for USD, so 1000 means $10.00)."
        )
    return int(value)


def _currency(currency: Optional[str]) -> str:
    return (currency or "usd").strip().lower() or "usd"


def _subscription_summary(sub: Dict[str, Any]) -> Dict[str, Any]:
    """The parts of a subscription a caller asks about."""
    items = ((sub.get("items") or {}).get("data") or [])
    return {
        "id": sub.get("id"),
        "status": sub.get("status"),
        "customer": sub.get("customer"),
        "cancel_at_period_end": sub.get("cancel_at_period_end"),
        "current_period_end": sub.get("current_period_end"),
        "plans": [
            {
                "price": (i.get("price") or {}).get("id"),
                "product": (i.get("price") or {}).get("product"),
                "amount": (i.get("price") or {}).get("unit_amount"),
                "interval": ((i.get("price") or {}).get("recurring") or {}).get("interval"),
            }
            for i in items
        ],
    }

