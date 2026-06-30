"""Chargebee connector for customer subscription data enrichment."""

import logging
from typing import Optional, Dict, Any, List
from datetime import datetime
from decimal import Decimal

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)


class ChargebeeConnector:
    """Connector for fetching customer subscription data from Chargebee API.

    Used to enrich feedback items with:
    - Customer LTV (lifetime value)
    - MRR (monthly recurring revenue)
    - Subscription plan and status
    - Churn risk signals (failed payments, cancellation requests)
    """

    def __init__(self, api_key: Optional[str] = None, site: Optional[str] = None):
        """Initialize Chargebee connector.

        Args:
            api_key: Chargebee API key (defaults to settings.chargebee_api_key)
            site: Chargebee site name (defaults to settings.chargebee_site)
        """
        self.api_key = api_key or settings.chargebee_api_key
        self.site = site or settings.chargebee_site
        self.base_url = f"https://{self.site}.chargebee.com/api/v2"

        if not self.api_key or not self.site:
            logger.warning("Chargebee API key or site not configured. Enrichment will be skipped.")

    async def get_customer_by_email(self, email: str) -> Optional[Dict[str, Any]]:
        """Get Chargebee customer by email.

        Args:
            email: Customer email address

        Returns:
            Customer data dict or None if not found

        Raises:
            httpx.HTTPStatusError: If API request fails (except 404)
        """
        if not self.api_key:
            return None

        url = f"{self.base_url}/customers"
        params = {"email[is]": email}

        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(
                    url,
                    params=params,
                    auth=(self.api_key, ""),
                    headers={"Accept": "application/json"},
                    timeout=10.0,
                )
                response.raise_for_status()
                data = response.json()

                if data.get("list") and len(data["list"]) > 0:
                    customer = data["list"][0]["customer"]
                    logger.info(f"Found Chargebee customer for email {email}: {customer['id']}")
                    return customer
                else:
                    logger.info(f"No Chargebee customer found for email {email}")
                    return None

            except httpx.HTTPStatusError as e:
                if e.response.status_code == 404:
                    return None
                logger.error(f"Chargebee API error for email {email}: {e}")
                raise
            except Exception as e:
                logger.error(f"Error fetching Chargebee customer by email {email}: {e}")
                return None

    async def get_customer_subscriptions(self, customer_id: str) -> List[Dict[str, Any]]:
        """Get active subscriptions for a customer.

        Args:
            customer_id: Chargebee customer ID

        Returns:
            List of active subscription dicts
        """
        if not self.api_key:
            return []

        url = f"{self.base_url}/subscriptions"
        params = {
            "customer_id[is]": customer_id,
            "status[in]": "[active,non_renewing,in_trial]",  # Active states
        }

        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(
                    url,
                    params=params,
                    auth=(self.api_key, ""),
                    headers={"Accept": "application/json"},
                    timeout=10.0,
                )
                response.raise_for_status()
                data = response.json()

                subscriptions = [item["subscription"] for item in data.get("list", [])]
                logger.info(f"Found {len(subscriptions)} active subscriptions for customer {customer_id}")
                return subscriptions

            except Exception as e:
                logger.error(f"Error fetching subscriptions for customer {customer_id}: {e}")
                return []

    async def get_customer_invoices(
        self,
        customer_id: str,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """Get recent invoices for a customer (for LTV calculation).

        Args:
            customer_id: Chargebee customer ID
            limit: Maximum number of invoices to fetch

        Returns:
            List of invoice dicts
        """
        if not self.api_key:
            return []

        url = f"{self.base_url}/invoices"
        params = {
            "customer_id[is]": customer_id,
            "limit": limit,
            "sort_by[desc]": "date",
        }

        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(
                    url,
                    params=params,
                    auth=(self.api_key, ""),
                    headers={"Accept": "application/json"},
                    timeout=10.0,
                )
                response.raise_for_status()
                data = response.json()

                invoices = [item["invoice"] for item in data.get("list", [])]
                logger.info(f"Found {len(invoices)} invoices for customer {customer_id}")
                return invoices

            except Exception as e:
                logger.error(f"Error fetching invoices for customer {customer_id}: {e}")
                return []

    async def get_enrichment_data(self, email: str) -> Optional[Dict[str, Any]]:
        """Get all enrichment data for a customer by email.

        This is the main method used by the enrichment service.
        Fetches customer, subscriptions, and invoices in one go.

        Uses Redis caching (24h TTL) to reduce API calls.

        Args:
            email: Customer email address

        Returns:
            Dict with customer, subscriptions, and invoices, or None if customer not found
        """
        # Check cache first
        from app.core.cache import get_cached_customer_enrichment, cache_customer_enrichment
        import hashlib

        # Use email hash as cache key (for privacy)
        cache_key = hashlib.md5(email.encode()).hexdigest()
        cached_data = get_cached_customer_enrichment(cache_key)

        if cached_data:
            logger.info(f"Using cached Chargebee data for email {email}")
            return cached_data

        # Cache miss - fetch from Chargebee
        customer = await self.get_customer_by_email(email)
        if not customer:
            return None

        customer_id = customer["id"]

        # Fetch subscriptions and invoices in parallel
        subscriptions, invoices = await asyncio.gather(
            self.get_customer_subscriptions(customer_id),
            self.get_customer_invoices(customer_id, limit=50),  # 50 invoices for accurate LTV
        )

        data = {
            "customer": customer,
            "subscriptions": subscriptions,
            "invoices": invoices,
        }

        # Cache the result (24 hour TTL)
        cache_customer_enrichment(cache_key, data, ttl=86400)

        return data


# Import asyncio at the end to avoid circular import issues
import asyncio
