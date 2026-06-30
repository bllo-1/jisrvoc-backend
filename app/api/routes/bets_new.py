"""
Bets API endpoints - product bets, evidence, status changes, writeback.
Matches frontend contract from jisrvoc-frontend/src/lib/api/bets.ts
"""
from fastapi import APIRouter, Depends, HTTPException
from typing import List
from sqlalchemy.ext.asyncio import AsyncSession
from ...schemas_new import (
    ProductBet,
    FeedbackItem,
    WritebackEntry,
    BetStatusChangeRequest,
    BetStatusChangeResponse,
)
from ... import mock_data
from ...db.session import get_db
from ...repositories.bet import BetRepository
from ...repositories.writeback_log import WritebackLogRepository
from ...workers.writeback_worker import writeback_to_hubspot
from ...models.bet import BetStatus

router = APIRouter()


@router.get("", response_model=List[ProductBet])
async def list_bets():
    """
    @endpoint GET /api/v1/bets
    Returns all product bets.
    """
    # Sort by vote_weight descending (highest priority first)
    sorted_bets = sorted(mock_data.BETS, key=lambda b: b.vote_weight, reverse=True)
    return sorted_bets


@router.get("/{bet_id}", response_model=ProductBet)
async def get_bet(bet_id: str):
    """
    @endpoint GET /api/v1/bets/:id
    Returns single bet by ID.
    """
    bet = next((b for b in mock_data.BETS if b.id == bet_id), None)
    if not bet:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail=f"Bet {bet_id} not found")
    return bet


@router.get("/{bet_id}/evidence", response_model=List[FeedbackItem])
async def get_evidence(bet_id: str):
    """
    @endpoint GET /api/v1/bets/:id/evidence
    Returns all feedback items used as evidence for this bet.
    Evidence IDs are stored in bet.evidence_ids.
    """
    bet = next((b for b in mock_data.BETS if b.id == bet_id), None)
    if not bet:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail=f"Bet {bet_id} not found")

    # Get feedback items by IDs
    evidence = [f for f in mock_data.FEEDBACK if f.id in bet.evidence_ids]

    # Sort by date descending
    evidence.sort(key=lambda f: f.date, reverse=True)

    return evidence


@router.get("/{bet_id}/writeback-log", response_model=List[WritebackEntry])
async def get_writeback_log(bet_id: str):
    """
    @endpoint GET /api/v1/bets/:id/writeback-log
    Returns writeback log entries for this bet.
    Shows history of status updates pushed back to source systems.
    """
    bet = next((b for b in mock_data.BETS if b.id == bet_id), None)
    if not bet:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail=f"Bet {bet_id} not found")

    # Get writeback entries for this bet
    log = mock_data.get_writeback_for_bet(bet_id)

    # Sort by performedAt descending (most recent first)
    log.sort(key=lambda e: e.performed_at, reverse=True)

    return log


@router.patch("/{bet_id}/status", response_model=BetStatusChangeResponse)
async def change_status(
    bet_id: str,
    request: BetStatusChangeRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    @endpoint PATCH /api/v1/bets/:id/status
    Changes bet status and triggers writeback to source tickets.

    Phase 4 Implementation:
    1. Update bet status in database
    2. Find all feedback items linked to this bet's theme
    3. Trigger async writeback jobs to HubSpot via Celery
    4. Create WritebackEntry records for each ticket
    5. Return summary of writeback results
    """
    # Try to get bet from database first
    bet_repo = BetRepository(db)
    try:
        # Convert string ID to UUID if needed
        import uuid as uuid_module
        if not bet_id.count('-') == 4:  # Not a UUID format (e.g., "b1")
            # Fall back to mock data for non-UUID IDs
            bet = None
        else:
            bet = await bet_repo.get_by_id(bet_id)
    except (ValueError, TypeError):
        bet = None

    # If not in database, check mock data
    if not bet:
        mock_bet = next((b for b in mock_data.BETS if b.id == bet_id), None)
        if not mock_bet:
            raise HTTPException(status_code=404, detail=f"Bet {bet_id} not found")

        # For mock data, simulate the status update without database persistence
        # Return success response with mock writeback
        return BetStatusChangeResponse(
            bet_id=bet_id,
            new_status=request.status,
            writebacks_triggered=0,  # No actual tickets to update for mock data
            writebacks_succeeded=0,
            writebacks_failed=0,
        )

    # Map string status from request to BetStatus enum (from models)
    # schemas_new.BetStatus has values like "Draft", "Shipped"
    # models.bet.BetStatus has values like "draft", "shipped"
    status_mapping = {
        "Draft": "draft",
        "In Backlog": "in_backlog",
        "In Discovery": "in_discovery",
        "In Build": "in_build",
        "Shipped": "shipped",
        "Declined": "declined",
    }

    try:
        db_status_value = status_mapping.get(request.status)
        if not db_status_value:
            raise ValueError(f"Unknown status: {request.status}")
        bet_status = BetStatus(db_status_value)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid status: {request.status}")

    # Update bet status in database
    await bet_repo.update_status(
        bet_id=bet_id,
        status=bet_status,
        owner_pm=bet.owner_pm,
        declined_reason=request.declined_reason if bet_status == BetStatus.DECLINED else None,
    )
    await bet_repo.commit()

    # Get HubSpot ticket IDs from evidence
    # TODO: Extract actual HubSpot ticket IDs from bet.evidence
    # For now, use mock data to simulate ticket extraction
    mock_bet = next((b for b in mock_data.BETS if b.id == bet_id), None)
    ticket_ids = []  # In production: extract from evidence where source="hubspot"

    # If mock bet has theme, get feedback count for simulation
    triggered_count = 0
    if mock_bet and mock_bet.theme_id:
        theme_feedback = mock_data.get_feedback_for_theme(mock_bet.theme_id)
        triggered_count = len(theme_feedback)

    # Create initial writeback_log entries (will be updated by worker)
    log_repo = WritebackLogRepository(db)
    if ticket_ids:
        for ticket_id in ticket_ids:
            await log_repo.create_log_entry(
                bet_id=bet_id,
                hubspot_ticket_id=ticket_id,
                action="property_update",
                status_value=bet_status,
                pm_id=bet.owner_pm or "system",
                result="pending",
            )
        await log_repo.commit()

    # Enqueue Celery task for async HubSpot write-back (fire-and-forget)
    if ticket_ids:
        writeback_to_hubspot.delay(
            bet_id=str(bet.id),
            ticket_ids=ticket_ids,
            status=bet_status.value,
            resolution_notes=request.declined_reason,
            pm_id=bet.owner_pm,
        )

    # Return response with writeback summary
    # Note: succeeded/failed counts will be 0 initially since writeback is async
    return BetStatusChangeResponse(
        bet_id=bet_id,
        new_status=request.status,
        writebacks_triggered=len(ticket_ids),
        writebacks_succeeded=0,  # Async - will be updated in writeback_log
        writebacks_failed=0,     # Check writeback_log for actual results
    )
