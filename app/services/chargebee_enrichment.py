"""Chargebee enrichment service for calculating customer metrics."""

import logging
from typing import Optional, Dict, Any
from datetime import datetime, timedelta
from decimal import Decimal
from enum import Enum

from app.connectors.chargebee_connector import ChargebeeConnector

logger = logging.getLogger(__name__)


class CustomerSegment(str, Enum):
    """Customer segment based on MRR."""
    SMB = "smb"  # <$1,000 MRR
    MID_MARKET = "mid_market"  # $1,000-$10,000 MRR
    ENTERPRISE = "enterprise"  # >$10,000 MRR


class ChargebeeEnrichmentService:
    """Service for enriching feedback with Chargebee customer data.

    Calculates:
    - Customer LTV (lifetime value)
    - MRR (monthly recurring revenue)
    - Customer segment (SMB, Mid-Market, Enterprise)
    - Churn risk score (0-100)
    - Subscription plan and status
    """

    def __init__(self, connector: Optional[ChargebeeConnector] = None):
        """Initialize enrichment service.

        Args:
            connector: Chargebee connector (optional, creates new one if not provided)
        """
        self.connector = connector or ChargebeeConnector()

    async def enrich_customer(self, email: str) -> Optional[Dict[str, Any]]:
        """Enrich customer data from Chargebee.

        Args:
            email: Customer email address

        Returns:
            Enrichment data dict with LTV, MRR, segment, churn_risk, plan, or None if not found
        """
        # Fetch data from Chargebee
        data = await self.connector.get_enrichment_data(email)
        if not data:
            logger.info(f"No Chargebee data found for email {email}")
            return None

        customer = data["customer"]
        subscriptions = data["subscriptions"]
        invoices = data["invoices"]

        # Calculate metrics
        mrr = self._calculate_mrr(subscriptions)
        ltv = self._calculate_ltv(invoices)
        segment = self._classify_segment(mrr)
        churn_risk = self._calculate_churn_risk(customer, subscriptions, invoices)
        plan = self._extract_plan_info(subscriptions)

        enrichment = {
            "customer_id": customer["id"],
            "customer_mrr": float(mrr),
            "customer_ltv": float(ltv),
            "customer_segment": segment.value,
            "churn_risk_score": churn_risk,
            "subscription_plan": plan["plan_id"] if plan else None,
            "subscription_status": plan["status"] if plan else None,
            "enriched_at": datetime.utcnow(),
        }

        logger.info(
            f"Enriched customer {email}: MRR=${mrr}, LTV=${ltv}, "
            f"segment={segment.value}, churn_risk={churn_risk}"
        )

        return enrichment

    def _calculate_mrr(self, subscriptions: list) -> Decimal:
        """Calculate total MRR from active subscriptions.

        Args:
            subscriptions: List of Chargebee subscription dicts

        Returns:
            Total MRR in USD
        """
        total_mrr = Decimal("0")

        for sub in subscriptions:
            # Only count active, non-renewing, or trial subscriptions
            if sub.get("status") in ["active", "non_renewing", "in_trial"]:
                # Get the MRR from subscription (Chargebee stores this as `mrr` field)
                mrr = Decimal(str(sub.get("mrr", 0))) / 100  # Chargebee stores cents
                total_mrr += mrr

        return total_mrr

    def _calculate_ltv(self, invoices: list) -> Decimal:
        """Calculate customer LTV from invoice history.

        LTV = Total revenue from all paid invoices

        Args:
            invoices: List of Chargebee invoice dicts

        Returns:
            LTV in USD
        """
        total_ltv = Decimal("0")

        for invoice in invoices:
            # Only count paid invoices
            if invoice.get("status") == "paid":
                # Get total amount from invoice
                total = Decimal(str(invoice.get("total", 0))) / 100  # Chargebee stores cents
                total_ltv += total

        return total_ltv

    def _classify_segment(self, mrr: Decimal) -> CustomerSegment:
        """Classify customer segment based on MRR.

        Segments (matching finance team rules):
        - SMB: <$1,000 MRR
        - Mid-Market: $1,000-$10,000 MRR
        - Enterprise: >$10,000 MRR

        Args:
            mrr: Monthly recurring revenue

        Returns:
            Customer segment enum
        """
        if mrr < Decimal("1000"):
            return CustomerSegment.SMB
        elif mrr < Decimal("10000"):
            return CustomerSegment.MID_MARKET
        else:
            return CustomerSegment.ENTERPRISE

    def _calculate_churn_risk(
        self,
        customer: dict,
        subscriptions: list,
        invoices: list,
    ) -> int:
        """Calculate churn risk score (0-100).

        Risk factors:
        - Failed payments in last 90 days (+30 points)
        - Non-renewing subscription (+20 points)
        - Overdue invoices (+25 points)
        - Account auto-collection disabled (+15 points)
        - No activity in last 60 days (+10 points)

        Args:
            customer: Chargebee customer dict
            subscriptions: List of subscription dicts
            invoices: List of invoice dicts

        Returns:
            Churn risk score (0-100, higher = more risk)
        """
        risk_score = 0

        # Check for failed payments in last 90 days
        ninety_days_ago = datetime.utcnow() - timedelta(days=90)
        recent_failed_payments = sum(
            1 for inv in invoices
            if inv.get("status") == "payment_due"
            and datetime.fromtimestamp(inv.get("date", 0)) > ninety_days_ago
        )
        if recent_failed_payments > 0:
            risk_score += 30
            logger.debug(f"Churn risk +30: {recent_failed_payments} failed payments")

        # Check for non-renewing subscriptions
        has_non_renewing = any(sub.get("status") == "non_renewing" for sub in subscriptions)
        if has_non_renewing:
            risk_score += 20
            logger.debug("Churn risk +20: non-renewing subscription")

        # Check for overdue invoices
        has_overdue = any(inv.get("status") == "payment_due" for inv in invoices[:5])  # Last 5 invoices
        if has_overdue:
            risk_score += 25
            logger.debug("Churn risk +25: overdue invoices")

        # Check if auto-collection is disabled
        auto_collection = customer.get("auto_collection", "on")
        if auto_collection == "off":
            risk_score += 15
            logger.debug("Churn risk +15: auto-collection disabled")

        # Check for recent activity (last 60 days)
        sixty_days_ago = datetime.utcnow() - timedelta(days=60)
        recent_activity = any(
            datetime.fromtimestamp(inv.get("date", 0)) > sixty_days_ago
            for inv in invoices[:10]
        )
        if not recent_activity:
            risk_score += 10
            logger.debug("Churn risk +10: no activity in 60 days")

        return min(risk_score, 100)  # Cap at 100

    def _extract_plan_info(self, subscriptions: list) -> Optional[Dict[str, Any]]:
        """Extract primary subscription plan info.

        Uses the subscription with highest MRR as primary.

        Args:
            subscriptions: List of subscription dicts

        Returns:
            Dict with plan_id and status, or None if no subscriptions
        """
        if not subscriptions:
            return None

        # Find subscription with highest MRR
        primary_sub = max(
            subscriptions,
            key=lambda s: Decimal(str(s.get("mrr", 0))),
            default=None,
        )

        if not primary_sub:
            return None

        return {
            "plan_id": primary_sub.get("plan_id"),
            "status": primary_sub.get("status"),
        }
