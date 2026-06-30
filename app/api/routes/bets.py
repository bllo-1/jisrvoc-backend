from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from ... import mock, schemas as s
from ...db.session import get_db
from ...repositories.bet import BetRepository
from ...repositories.writeback_log import WritebackLogRepository
from ...workers.writeback_worker import writeback_to_hubspot

router = APIRouter()


@router.get("", response_model=list[s.BetSummary])
async def list_bets(status: s.BetStatus | None = None):
    return mock.bets(status)


@router.post("", response_model=s.BetDetail, status_code=201)
async def create_bet(body: s.BetCreate):
    # TODO: persist; for now echo a created bet.
    return s.BetDetail(id="b-new", title=body.title, status=s.BetStatus.draft,
                       affected_segments=body.affected_segments,
                       est_customer_count=body.est_customer_count,
                       problem_statement=body.problem_statement, theme_id=body.theme_id)


@router.get("/{bet_id}", response_model=s.BetDetail)
async def get_bet(bet_id: str):
    detail = mock.bet_detail(bet_id)
    if not detail:
        raise HTTPException(404, "Not found")
    return detail


@router.patch("/{bet_id}", response_model=s.BetUpdateResult)
async def update_bet(
    bet_id: str,
    body: s.BetUpdate,
    db: AsyncSession = Depends(get_db),
):
    """Update bet with Phase 4 Loop Closure: HubSpot write-back."""

    # For non-status updates, use mock (TODO: implement real persistence)
    if body.status is None:
        detail = mock.bet_detail(bet_id)
        if not detail:
            raise HTTPException(404, "Not found")
        result = s.BetUpdateResult(**detail.model_dump())
        if body.title is not None:
            result.title = body.title
        if body.problem_statement is not None:
            result.problem_statement = body.problem_statement
        if body.declined_reason is not None:
            result.declined_reason = body.declined_reason
        return result

    # PHASE 4: Real implementation for status updates with HubSpot write-back
    bet_repo = BetRepository(db)
    bet = await bet_repo.get_by_id(bet_id)

    if not bet:
        raise HTTPException(404, "Bet not found")

    # Capture old status for audit
    old_status = bet.status

    # Update bet status in database
    await bet_repo.update_status(
        bet_id=bet_id,
        status=body.status,
        owner_pm=bet.owner_pm,
        declined_reason=body.declined_reason,
    )
    await bet_repo.commit()

    # Get HubSpot ticket IDs from evidence (feedback items linked to this bet)
    ticket_ids = await bet_repo.get_hubspot_ticket_ids(bet_id)

    # Create initial writeback_log entry (will be updated by worker)
    log_repo = WritebackLogRepository(db)
    if ticket_ids:
        for ticket_id in ticket_ids:
            await log_repo.create_log_entry(
                bet_id=bet_id,
                hubspot_ticket_id=ticket_id,
                action="property_update",
                status_value=body.status,
                pm_id=bet.owner_pm or "system",
                result="pending",
            )
        await log_repo.commit()

    # Enqueue Celery task for async HubSpot write-back (fire-and-forget)
    if ticket_ids:
        writeback_to_hubspot.delay(
            bet_id=str(bet.id),
            ticket_ids=ticket_ids,
            status=body.status.value,
            resolution_notes=body.declined_reason if body.status == s.BetStatus.declined else None,
            pm_id=bet.owner_pm,
        )

    # Refresh bet to get updated data
    await db.refresh(bet)

    # Return updated bet with writeback info
    # TODO: Convert bet model to BetDetail schema properly
    # For now, use mock detail structure but with real status
    detail = mock.bet_detail(bet_id)
    if detail:
        result = s.BetUpdateResult(**detail.model_dump())
        result.status = body.status
        result.writeback = s.Writeback(
            tickets_updated=len(ticket_ids),
            action="property_update",
            status_value=body.status,
        )
        return result
    else:
        # Fallback: construct minimal response from DB bet
        result = s.BetUpdateResult(
            id=str(bet.id),
            title=bet.title,
            status=bet.status,
            problem_statement=bet.problem_statement,
            affected_segments=bet.affected_segments,
            est_customer_count=bet.est_customer_count,
            why_now=bet.why_now,
            theme_id=str(bet.theme_id) if bet.theme_id else None,
            owner_pm=bet.owner_pm,
            declined_reason=bet.declined_reason,
            created_at=bet.created_at,
            updated_at=bet.updated_at,
            writeback=s.Writeback(
                tickets_updated=len(ticket_ids),
                action="property_update",
                status_value=body.status,
            )
        )
        return result
