from fastapi import APIRouter, HTTPException
from ... import mock, schemas as s

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
async def update_bet(bet_id: str, body: s.BetUpdate):
    detail = mock.bet_detail(bet_id)
    if not detail:
        raise HTTPException(404, "Not found")
    result = s.BetUpdateResult(**detail.model_dump())
    if body.status is not None:
        result.status = body.status
        # Loop closure: in real impl, enqueue HubSpot write-back to every evidence ticket
        # and append to writeback_log. Here we mock the result the UI shows in a toast.
        result.writeback = s.Writeback(
            tickets_updated=detail.evidence_count, action="note", status_value=body.status)
    if body.title is not None:
        result.title = body.title
    if body.problem_statement is not None:
        result.problem_statement = body.problem_statement
    if body.declined_reason is not None:
        result.declined_reason = body.declined_reason
    return result
