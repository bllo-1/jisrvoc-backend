"""
Admin API endpoints - source connectors, sync runs, PM routing, model evaluation metrics, digests.
Matches frontend contract from jisrvoc-frontend/src/lib/api/admin.ts

Note: "Eval" refers to AI model evaluation/assessment (precision/recall/F1 scores),
not the eval() function. This is standard ML terminology for model performance metrics.
"""
from fastapi import APIRouter
from typing import List
from ...schemas_new import (
    SourceConnection,
    SyncRun,
    PmRoutingRule,
    UnmatchedItem,
    UnmatchedResolveRequest,
    EvalScorecard,
    EvalRunResponse,
    DigestPreview,
    DigestSendResponse,
    ResyncResponse,
    Source,
)
from ... import mock_data
from datetime import datetime

router = APIRouter()


@router.get("/connectors", response_model=List[SourceConnection])
async def list_connectors():
    """
    @endpoint GET /api/v1/admin/connectors
    Returns status of all source connectors.
    """
    return mock_data.SOURCE_CONNECTIONS


@router.get("/connectors/{source}/runs", response_model=List[SyncRun])
async def get_sync_runs(source: Source):
    """
    @endpoint GET /api/v1/admin/connectors/:source/runs
    Returns sync run history for a specific source connector.
    """
    runs = mock_data.get_sync_runs_for_connector(source)
    # Sort by started_at descending (most recent first)
    runs.sort(key=lambda r: r.started_at, reverse=True)
    return runs


@router.post("/connectors/{source}/resync", response_model=ResyncResponse)
async def resync_connector(source: Source):
    """
    @endpoint POST /api/v1/admin/connectors/:source/resync
    Triggers a manual resync for a source connector.
    In production, this enqueues a background job.
    """
    # Verify connector exists
    connector = next((c for c in mock_data.SOURCE_CONNECTIONS if c.source == source), None)
    if not connector:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail=f"Connector {source} not found")

    # Generate run ID
    run_id = f"s-{int(datetime.now().timestamp() * 1000)}"

    # In production, this would:
    # 1. Enqueue a Celery/BullMQ job
    # 2. Create SyncRun record with status="Running"
    # 3. Async worker would fetch data from source API
    # 4. Worker would update SyncRun with results

    return ResyncResponse(
        source=source,
        enqueued=True,
        run_id=run_id,
    )


@router.get("/sync-runs", response_model=List[SyncRun])
async def list_all_sync_runs():
    """
    @endpoint GET /api/v1/admin/sync-runs
    Returns sync run history for all connectors.
    """
    runs = list(mock_data.SYNC_RUNS)
    # Sort by started_at descending
    runs.sort(key=lambda r: r.started_at, reverse=True)
    return runs


@router.get("/pm-routing", response_model=List[PmRoutingRule])
async def get_pm_routing():
    """
    @endpoint GET /api/v1/admin/pm-routing
    Returns PM routing rules by product area.
    Used for auto-assigning feedback to product managers.
    """
    return mock_data.PM_ROUTING


@router.get("/unmatched-queue", response_model=List[UnmatchedItem])
async def get_unmatched_queue():
    """
    @endpoint GET /api/v1/admin/unmatched-queue
    Returns queue of customer strings that couldn't be auto-matched.
    PM must manually resolve these.
    """
    # Sort by created_at descending (most recent first)
    queue = sorted(mock_data.UNMATCHED_QUEUE, key=lambda u: u.created_at, reverse=True)
    return queue


@router.post("/unmatched-queue/{unmatched_id}/match")
async def match_unmatched(unmatched_id: str, request: UnmatchedResolveRequest):
    """
    @endpoint POST /api/v1/admin/unmatched-queue/:id/match
    Resolves an unmatched customer by linking to a known customer ID.
    In production, this updates all feedback items with this raw string.
    """
    item = next((u for u in mock_data.UNMATCHED_QUEUE if u.id == unmatched_id), None)
    if not item:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail=f"Unmatched item {unmatched_id} not found")

    # Verify customer exists
    customer = next((c for c in mock_data.CUSTOMERS if c.id == request.customer_id), None)
    if not customer:
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail=f"Customer {request.customer_id} not found")

    # In production, this would:
    # 1. UPDATE feedback SET customer_id = :customer_id WHERE raw_customer = :raw_string
    # 2. DELETE from unmatched_queue WHERE id = :unmatched_id
    # 3. Trigger theme/bet recalculation for affected items

    return {
        "id": unmatched_id,
        "customer_id": request.customer_id,
        "resolved": True,
    }


@router.get("/eval-scorecard", response_model=EvalScorecard)
async def get_eval_scorecard():
    """
    @endpoint GET /api/v1/admin/eval-scorecard
    Returns latest AI model assessment metrics (precision/recall/F1).
    Shows performance for each tag type and language.
    """
    return mock_data.EVAL_SCORECARD


@router.post("/eval-scorecard/run", response_model=EvalRunResponse)
async def run_eval():
    """
    @endpoint POST /api/v1/admin/eval-scorecard/run
    Triggers a new assessment run on the gold-standard test set.
    In production, this enqueues a background job.
    """
    # In production, this would:
    # 1. Enqueue assessment job
    # 2. Job loads gold-standard test set
    # 3. Job runs current AI model on test set
    # 4. Job calculates metrics and updates scorecard
    # 5. Job sends Slack notification with results

    return EvalRunResponse(
        enqueued=True,
        eta_minutes=12,
    )


@router.get("/digest/preview", response_model=DigestPreview)
async def get_digest_preview():
    """
    @endpoint GET /api/v1/admin/digest/preview
    Returns preview of the weekly digest that will be sent to Slack.
    """
    # Get top themes by item count
    sorted_themes = sorted(mock_data.THEMES, key=lambda t: t.item_count, reverse=True)[:5]
    top_themes = [
        {
            "themeId": t.id,
            "name": t.name,
            "delta": (
                "+18% wow" if t.trend.value == "Rising"
                else "new" if t.trend.value == "New"
                else "-12% wow" if t.trend.value == "Declining"
                else "flat"
            ),
        }
        for t in sorted_themes
    ]

    # Get new/backlog bets
    new_bets = [
        {"betId": b.id, "title": b.title}
        for b in mock_data.BETS
        if b.status.value in ["Draft", "In Backlog"]
    ][:3]

    # Count high urgency items
    high_urgency_count = len([f for f in mock_data.FEEDBACK if f.urgency.value == "High"])

    return DigestPreview(
        scheduled_for="Sunday 09:00 Riyadh time",
        recipient_channel="#product-voc-digest",
        top_themes=top_themes,
        new_bets=new_bets,
        high_urgency_count=high_urgency_count,
    )


@router.post("/digest/send-test", response_model=DigestSendResponse)
async def send_test_digest():
    """
    @endpoint POST /api/v1/admin/digest/send-test
    Sends a test digest to the test Slack channel.
    In production, this posts to Slack via webhook.
    """
    # In production, this would:
    # 1. Generate digest markdown
    # 2. POST to Slack webhook
    # 3. Return success/failure

    return DigestSendResponse(
        sent=True,
        channel="#product-voc-digest-test",
    )
