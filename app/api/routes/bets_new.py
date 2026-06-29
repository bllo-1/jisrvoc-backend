"""
Bets API endpoints - product bets, evidence, status changes, writeback.
Matches frontend contract from jisrvoc-frontend/src/lib/api/bets.ts
"""
from fastapi import APIRouter
from typing import List
from ...schemas_new import (
    ProductBet,
    FeedbackItem,
    WritebackEntry,
    BetStatusChangeRequest,
    BetStatusChangeResponse,
)
from ... import mock_data

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
async def change_status(bet_id: str, request: BetStatusChangeRequest):
    """
    @endpoint PATCH /api/v1/bets/:id/status
    Changes bet status and triggers writeback to source tickets.

    In production, this would:
    1. Update bet status in database
    2. Find all feedback items linked to this bet's theme
    3. Trigger async writeback jobs to HubSpot/Zendesk/Canny/Jira
    4. Create WritebackEntry records for each ticket
    5. Return summary of writeback results
    """
    bet = next((b for b in mock_data.BETS if b.id == bet_id), None)
    if not bet:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail=f"Bet {bet_id} not found")

    # Find all feedback items linked to this bet's theme
    theme_feedback = []
    if bet.theme_id:
        theme_feedback = mock_data.get_feedback_for_theme(bet.theme_id)

    # In production, this would trigger async writeback jobs
    # For mock, we simulate success/failure
    triggered_count = len(theme_feedback)
    failed_count = 1 if triggered_count > 5 else 0  # Simulate occasional failure
    succeeded_count = triggered_count - failed_count

    return BetStatusChangeResponse(
        bet_id=bet_id,
        new_status=request.status,
        writebacks_triggered=triggered_count,
        writebacks_succeeded=succeeded_count,
        writebacks_failed=failed_count,
    )
