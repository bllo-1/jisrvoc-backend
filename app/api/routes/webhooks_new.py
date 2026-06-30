"""
Webhook endpoints - inbound data from external systems (HubSpot, Zendesk, Canny, Jira).
These are public endpoints (no auth) that receive webhook payloads from source connectors.

In production:
1. Verify HMAC signature to ensure payload authenticity
2. Enqueue raw payload for async processing
3. Worker processes payload: normalize, dedupe, persist to DB
4. Return 200 immediately to acknowledge receipt
"""
from fastapi import APIRouter, Request, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Dict, Any
import logging

from app.db.session import get_db
from app.connectors.hubspot import HubSpotConnector
from app.repositories.feedback import FeedbackRepository
from app.services.identity_resolution import IdentityResolutionService

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/hubspot")
async def hubspot_webhook(request: Request, db: AsyncSession = Depends(get_db)):
    """
    @endpoint POST /api/public/webhooks/hubspot
    Receives ticket updates from HubSpot.

    HubSpot sends webhooks for:
    - New tickets created
    - Ticket status changes
    - Ticket comments added

    Payload example:
    {
        "objectId": "12345",
        "portalId": "9876",
        "subscriptionType": "ticket.propertyChange",
        "propertyName": "hs_ticket_status",
        "propertyValue": "Closed"
    }
    """
    try:
        payload: Dict[str, Any] = await request.json()
        object_id = payload.get("objectId")

        if not object_id:
            logger.warning("HubSpot webhook received without objectId")
            return {"status": "rejected", "reason": "Missing objectId"}

        # TODO: In production - verify HMAC signature from X-HubSpot-Signature header
        # signature = request.headers.get("X-HubSpot-Signature")
        # verify_hubspot_signature(payload, signature)

        logger.info(f"HubSpot webhook received for ticket {object_id}")

        # Initialize HubSpot connector and fetch the full ticket
        hubspot = HubSpotConnector(session=db)

        # Fetch the specific ticket from HubSpot API
        import httpx
        headers = {
            "Authorization": f"Bearer {hubspot.api_key}",
            "Content-Type": "application/json",
        }

        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{hubspot.base_url}/crm/v3/objects/tickets/{object_id}",
                headers=headers,
                params={
                    "properties": "subject,content,hs_ticket_id,hs_ticket_category,hs_ticket_priority,hs_pipeline_stage,createdate,hs_lastmodifieddate,source_type"
                },
                timeout=30.0,
            )
            response.raise_for_status()
            ticket = response.json()

        # Sync the ticket to feedback (with identity resolution)
        feedback = await hubspot.sync_ticket_to_feedback(ticket)

        logger.info(f"HubSpot webhook processed: created/updated feedback {feedback.id}")

        return {
            "status": "accepted",
            "source": "hubspot",
            "feedback_id": feedback.id
        }

    except httpx.HTTPStatusError as e:
        logger.error(f"Failed to fetch HubSpot ticket: {e}")
        raise HTTPException(status_code=502, detail="Failed to fetch ticket from HubSpot")
    except Exception as e:
        logger.error(f"HubSpot webhook processing failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Webhook processing failed")


@router.post("/zendesk")
async def zendesk_webhook(request: Request):
    """
    @endpoint POST /api/public/webhooks/zendesk
    Receives ticket updates from Zendesk.

    Zendesk sends webhooks for:
    - New tickets created
    - Ticket status changes
    - Comments added

    Payload example:
    {
        "id": "67890",
        "subject": "Cannot process payroll",
        "status": "solved",
        "priority": "high",
        "requester_id": "user123",
        "tags": ["payroll", "bug"]
    }
    """
    try:
        payload: Dict[str, Any] = await request.json()

        # In production:
        # 1. Verify webhook signature from X-Zendesk-Webhook-Signature
        # 2. Validate payload
        # 3. Enqueue to background job
        # 4. Worker normalizes and persists

        logger.info(f"Zendesk webhook received: {payload.get('id')}")

        return {"status": "accepted", "source": "Zendesk"}

    except Exception as e:
        logger.error(f"Zendesk webhook processing failed: {e}")
        raise HTTPException(status_code=500, detail="Webhook processing failed")


@router.post("/canny")
async def canny_webhook(request: Request):
    """
    @endpoint POST /api/public/webhooks/canny
    Receives feature request updates from Canny.

    Canny sends webhooks for:
    - New posts created
    - Posts voted
    - Posts status changed

    Payload example:
    {
        "type": "post.created",
        "object": {
            "id": "abc123",
            "title": "Add bulk payroll import",
            "details": "We need to import 500+ employees...",
            "score": 42,
            "board": "feature-requests"
        }
    }
    """
    try:
        payload: Dict[str, Any] = await request.json()

        # In production:
        # 1. Verify signature from X-Canny-Signature
        # 2. Validate event type and payload
        # 3. Enqueue to background job
        # 4. Worker processes Canny-specific schema

        logger.info(f"Canny webhook received: {payload.get('type')}")

        return {"status": "accepted", "source": "Canny"}

    except Exception as e:
        logger.error(f"Canny webhook processing failed: {e}")
        raise HTTPException(status_code=500, detail="Webhook processing failed")


@router.post("/jira")
async def jira_webhook(request: Request):
    """
    @endpoint POST /api/public/webhooks/jira
    Receives issue updates from Jira.

    Jira sends webhooks for:
    - Issues created
    - Issues updated
    - Comments added
    - Status transitions

    Payload example:
    {
        "webhookEvent": "jira:issue_updated",
        "issue": {
            "key": "PROD-123",
            "fields": {
                "summary": "Mobile app crashes on payroll submit",
                "status": {"name": "In Progress"},
                "priority": {"name": "High"},
                "description": "..."
            }
        }
    }
    """
    try:
        payload: Dict[str, Any] = await request.json()

        # In production:
        # 1. Verify JWT signature from Authorization header
        # 2. Validate webhook event type
        # 3. Enqueue to background job
        # 4. Worker extracts fields, normalizes, persists

        logger.info(f"Jira webhook received: {payload.get('webhookEvent')}")

        return {"status": "accepted", "source": "Jira"}

    except Exception as e:
        logger.error(f"Jira webhook processing failed: {e}")
        raise HTTPException(status_code=500, detail="Webhook processing failed")


@router.post("/{source}")
async def generic_webhook(
    source: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """
    @endpoint POST /api/public/webhooks/{source}
    Generic webhook endpoint for real-time feedback ingestion from any source.

    This endpoint accepts feedback data directly (not wrapped in source-specific format).
    Useful for:
    - Custom integrations
    - Testing
    - Sources without dedicated webhooks (Zendesk, Canny, Jira)

    Expected payload:
    {
        "external_id": "ticket-123",
        "title": "Cannot process payroll",
        "content": "Detailed description...",
        "customer_email": "john@company.com",
        "customer_name": "John Doe",
        "source_channel": "email",
        "priority": "high",
        "status": "open",
        "metadata": {
            "custom_field": "value"
        }
    }
    """
    try:
        payload: Dict[str, Any] = await request.json()

        # Validate source
        valid_sources = ["hubspot", "zendesk", "canny", "jira", "email", "chat", "api"]
        if source.lower() not in valid_sources:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid source '{source}'. Valid sources: {', '.join(valid_sources)}"
            )

        # Extract required fields
        external_id = payload.get("external_id")
        title = payload.get("title")
        content = payload.get("content")

        if not title or not content:
            raise HTTPException(
                status_code=400,
                detail="Missing required fields: title and content are required"
            )

        # Extract optional customer info for identity resolution
        customer_email = payload.get("customer_email")
        customer_name = payload.get("customer_name")

        logger.info(f"Generic webhook received from {source}: {external_id or 'no ID'}")

        # Initialize repositories and services
        feedback_repo = FeedbackRepository(db)
        identity_service = IdentityResolutionService(db)

        # Check if feedback already exists (if external_id provided)
        if external_id:
            existing = await feedback_repo.get_by_source_and_external_id(
                source=source.lower(),
                external_id=external_id,
            )
            if existing:
                logger.info(f"Feedback already exists: {existing.id}, skipping")
                return {
                    "status": "duplicate",
                    "source": source.lower(),
                    "feedback_id": existing.id
                }

        # Create feedback
        feedback = await feedback_repo.create(
            source=source.lower(),
            external_id=external_id,
            source_channel=payload.get("source_channel", "api"),
            title=title,
            content=content,
            customer_email=customer_email,
            priority=payload.get("priority"),
            status=payload.get("status", "open"),
            metadata=payload.get("metadata", {}),
        )

        await feedback_repo.commit()
        logger.info(f"Created feedback {feedback.id} from {source} webhook")

        # Resolve customer identity if email provided
        if customer_email:
            logger.info(f"Resolving identity for feedback {feedback.id}")
            customer = await identity_service.resolve_feedback_identity(
                feedback=feedback,
                email=customer_email,
                name=customer_name,
            )
            if customer:
                logger.info(f"Linked feedback {feedback.id} to customer {customer.id}")

        return {
            "status": "accepted",
            "source": source.lower(),
            "feedback_id": feedback.id,
            "customer_linked": customer_email is not None
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"{source} webhook processing failed: {e}", exc_info=True)
        await db.rollback()
        raise HTTPException(status_code=500, detail="Webhook processing failed")
