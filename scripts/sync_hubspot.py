#!/usr/bin/env python3
"""
CLI script to sync HubSpot tickets to the feedback table.

Usage:
    python scripts/sync_hubspot.py [--limit 100]
"""

import asyncio
import argparse
import logging
import sys
from pathlib import Path

# Add parent directory to path to import app modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.connectors.hubspot import HubSpotConnector
from app.db.session import AsyncSessionLocal
from app.core.config import settings


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def sync_hubspot_tickets(limit: int = 100):
    """
    Sync HubSpot tickets to feedback table.

    Args:
        limit: Maximum number of tickets to sync (default: 100)
    """
    # Validate API key is configured
    if not settings.hubspot_api_key:
        logger.error("HUBSPOT_API_KEY is not configured in .env file")
        sys.exit(1)

    logger.info(f"Starting HubSpot ingestion with limit={limit}")
    logger.info(f"Using API key: {settings.hubspot_api_key[:10]}...")

    async with AsyncSessionLocal() as session:
        try:
            # Initialize connector
            connector = HubSpotConnector(session=session)

            # Sync tickets
            feedback_items = await connector.sync_tickets(limit=limit)

            logger.info("=" * 60)
            logger.info(f"✅ Successfully synced {len(feedback_items)} feedback items")
            logger.info("=" * 60)

            # Print summary
            if feedback_items:
                logger.info("\nSynced feedback items:")
                for item in feedback_items[:10]:  # Show first 10
                    logger.info(f"  - ID: {item.id}, Title: {item.title[:50]}...")

                if len(feedback_items) > 10:
                    logger.info(f"  ... and {len(feedback_items) - 10} more items")

            return feedback_items

        except Exception as e:
            logger.error(f"❌ Error during HubSpot sync: {e}", exc_info=True)
            await session.rollback()
            raise


def main():
    """Main entry point for the CLI script."""
    parser = argparse.ArgumentParser(
        description="Sync HubSpot tickets to feedback table"
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=100,
        help="Maximum number of tickets to sync (default: 100)"
    )

    args = parser.parse_args()

    # Run async sync
    try:
        asyncio.run(sync_hubspot_tickets(limit=args.limit))
    except KeyboardInterrupt:
        logger.info("Sync interrupted by user")
        sys.exit(130)
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
