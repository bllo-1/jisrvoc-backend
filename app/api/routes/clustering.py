"""API routes for clustering operations."""
import logging
from typing import Dict, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel

from app.db.session import get_db
from app.repositories.clustering import ClusteringRunRepository
from app.workers.clustering_worker import (
    trigger_manual_clustering,
    generate_bets_for_themes,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/clustering", tags=["clustering"])


# Pydantic schemas
class TriggerClusteringRequest(BaseModel):
    """Request to trigger manual clustering."""
    days: int = 7
    min_cluster_size: int = 5


class TriggerClusteringResponse(BaseModel):
    """Response with task ID."""
    task_id: str
    status: str
    message: str


class ClusteringRunResponse(BaseModel):
    """Clustering run details."""
    id: str
    started_at: str
    finished_at: Optional[str]
    item_count: Optional[int]
    status: Optional[str]


# Endpoints
@router.post("/trigger", response_model=TriggerClusteringResponse)
async def trigger_clustering(
    request: TriggerClusteringRequest,
) -> TriggerClusteringResponse:
    """Manually trigger clustering job.

    This endpoint queues a Celery task to cluster feedback from the last N days.
    Returns immediately with a task ID that can be used to track progress.

    Args:
        request: Clustering parameters (days, min_cluster_size)

    Returns:
        Task ID and status
    """
    try:
        # Trigger Celery task
        task = trigger_manual_clustering.delay(
            days=request.days,
            min_cluster_size=request.min_cluster_size,
        )

        logger.info(f"Triggered clustering task {task.id}")

        return TriggerClusteringResponse(
            task_id=task.id,
            status="queued",
            message=f"Clustering job queued successfully (days={request.days}, min_cluster_size={request.min_cluster_size})",
        )

    except Exception as e:
        logger.error(f"Failed to trigger clustering: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to trigger clustering: {str(e)}")


@router.post("/generate-bets", response_model=TriggerClusteringResponse)
async def trigger_bet_generation(
    limit: int = Query(5, ge=1, le=20),
    min_customers: int = Query(3, ge=1),
) -> TriggerClusteringResponse:
    """Manually trigger product bet generation from top themes.

    Args:
        limit: Maximum number of bets to generate (1-20)
        min_customers: Minimum customer count threshold

    Returns:
        Task ID and status
    """
    try:
        # Trigger Celery task
        task = generate_bets_for_themes.delay(
            limit=limit,
            min_customers=min_customers,
        )

        logger.info(f"Triggered bet generation task {task.id}")

        return TriggerClusteringResponse(
            task_id=task.id,
            status="queued",
            message=f"Bet generation job queued successfully (limit={limit}, min_customers={min_customers})",
        )

    except Exception as e:
        logger.error(f"Failed to trigger bet generation: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to trigger bet generation: {str(e)}")


@router.get("/runs/latest", response_model=ClusteringRunResponse)
async def get_latest_run(
    session: AsyncSession = Depends(get_db),
) -> ClusteringRunResponse:
    """Get the latest clustering run details.

    Returns:
        Latest clustering run information
    """
    try:
        from sqlalchemy import select
        from app.models.clustering import ClusteringRun

        # Get latest run
        stmt = select(ClusteringRun).order_by(ClusteringRun.started_at.desc()).limit(1)
        result = await session.execute(stmt)
        run = result.scalars().first()

        if not run:
            raise HTTPException(status_code=404, detail="No clustering runs found")

        return ClusteringRunResponse(
            id=str(run.id),
            started_at=run.started_at.isoformat(),
            finished_at=run.finished_at.isoformat() if run.finished_at else None,
            item_count=run.item_count,
            status=run.status,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get latest run: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get latest run: {str(e)}")


@router.get("/runs/{run_id}", response_model=ClusteringRunResponse)
async def get_run_by_id(
    run_id: str,
    session: AsyncSession = Depends(get_db),
) -> ClusteringRunResponse:
    """Get clustering run details by ID.

    Args:
        run_id: Clustering run UUID

    Returns:
        Clustering run information
    """
    try:
        repo = ClusteringRunRepository(session)
        run = await repo.get_run(run_id)

        if not run:
            raise HTTPException(status_code=404, detail=f"Clustering run {run_id} not found")

        return ClusteringRunResponse(
            id=str(run.id),
            started_at=run.started_at.isoformat(),
            finished_at=run.finished_at.isoformat() if run.finished_at else None,
            item_count=run.item_count,
            status=run.status,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get run {run_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get run: {str(e)}")


@router.get("/status")
async def get_clustering_status(
    session: AsyncSession = Depends(get_db),
) -> Dict:
    """Get overall clustering system status.

    Returns:
        System status including run counts and latest run info
    """
    try:
        from sqlalchemy import select, func
        from app.models.clustering import ClusteringRun

        # Get run counts by status
        stmt = select(
            ClusteringRun.status,
            func.count(ClusteringRun.id).label("count")
        ).group_by(ClusteringRun.status)

        result = await session.execute(stmt)
        status_counts = {row.status: row.count for row in result}

        # Get latest run
        stmt = select(ClusteringRun).order_by(ClusteringRun.started_at.desc()).limit(1)
        result = await session.execute(stmt)
        latest_run = result.scalars().first()

        return {
            "status_counts": status_counts,
            "total_runs": sum(status_counts.values()),
            "latest_run": {
                "id": str(latest_run.id),
                "started_at": latest_run.started_at.isoformat(),
                "status": latest_run.status,
            } if latest_run else None,
        }

    except Exception as e:
        logger.error(f"Failed to get clustering status: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get clustering status: {str(e)}")
