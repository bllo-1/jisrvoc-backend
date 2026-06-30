"""API routes for intelligence layer (themes and bets)."""
import logging
from typing import List, Optional, Dict
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
from datetime import datetime

from app.db.session import get_db
from app.repositories.theme import ThemeRepository
from app.repositories.bet import BetRepository
from app.models.theme import ThemeTrend
from app.models.bet import BetStatus, Segment

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/intelligence", tags=["intelligence"])


# Pydantic schemas
class ThemeResponse(BaseModel):
    """Theme details."""
    id: str
    name_en: str
    description_en: Optional[str]
    trend: str
    item_count: int
    customer_count: int
    vote_weight: int
    is_active: bool
    first_seen_at: str
    last_run_id: Optional[str]


class BetResponse(BaseModel):
    """Product bet details."""
    id: str
    theme_id: Optional[str]
    title: str
    problem_statement: Optional[str]
    affected_segments: List[str]
    est_customer_count: Optional[int]
    why_now: Optional[str]
    status: str
    owner_pm: Optional[str]
    declined_reason: Optional[str]
    created_at: str


class UpdateBetStatusRequest(BaseModel):
    """Request to update bet status."""
    status: str
    owner_pm: Optional[str] = None
    declined_reason: Optional[str] = None


# Theme endpoints
@router.get("/themes", response_model=List[ThemeResponse])
async def list_themes(
    active_only: bool = Query(True, description="Filter to active themes only"),
    limit: int = Query(20, ge=1, le=100),
    session: AsyncSession = Depends(get_db),
) -> List[ThemeResponse]:
    """List themes ordered by vote weight.

    Args:
        active_only: Filter to active themes only
        limit: Maximum number of themes to return

    Returns:
        List of themes
    """
    try:
        from sqlalchemy import select
        from app.models.theme import Theme

        stmt = select(Theme)

        if active_only:
            stmt = stmt.where(Theme.is_active == True)

        stmt = stmt.order_by(Theme.vote_weight.desc()).limit(limit)

        result = await session.execute(stmt)
        themes = list(result.scalars().all())

        return [
            ThemeResponse(
                id=str(theme.id),
                name_en=theme.name_en,
                description_en=theme.description_en,
                trend=theme.trend.value,
                item_count=theme.item_count,
                customer_count=theme.customer_count,
                vote_weight=theme.vote_weight,
                is_active=theme.is_active,
                first_seen_at=theme.first_seen_at.isoformat(),
                last_run_id=str(theme.last_run_id) if theme.last_run_id else None,
            )
            for theme in themes
        ]

    except Exception as e:
        logger.error(f"Failed to list themes: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to list themes: {str(e)}")


@router.get("/themes/{theme_id}", response_model=ThemeResponse)
async def get_theme(
    theme_id: str,
    session: AsyncSession = Depends(get_db),
) -> ThemeResponse:
    """Get theme details by ID.

    Args:
        theme_id: Theme UUID

    Returns:
        Theme details
    """
    try:
        repo = ThemeRepository(session)
        theme = await repo.get_by_id(theme_id)

        if not theme:
            raise HTTPException(status_code=404, detail=f"Theme {theme_id} not found")

        return ThemeResponse(
            id=str(theme.id),
            name_en=theme.name_en,
            description_en=theme.description_en,
            trend=theme.trend.value,
            item_count=theme.item_count,
            customer_count=theme.customer_count,
            vote_weight=theme.vote_weight,
            is_active=theme.is_active,
            first_seen_at=theme.first_seen_at.isoformat(),
            last_run_id=str(theme.last_run_id) if theme.last_run_id else None,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get theme {theme_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get theme: {str(e)}")


@router.get("/themes/{theme_id}/feedback")
async def get_theme_feedback(
    theme_id: str,
    limit: int = Query(50, ge=1, le=200),
    session: AsyncSession = Depends(get_db),
) -> Dict:
    """Get feedback items belonging to a theme.

    Args:
        theme_id: Theme UUID
        limit: Maximum number of feedback items to return

    Returns:
        List of feedback items with similarity scores
    """
    try:
        from sqlalchemy import select
        from app.models.feedback import Feedback
        from app.models.theme import Theme
        from app.models.clustering import ThemeMembership

        # Verify theme exists
        repo = ThemeRepository(session)
        theme = await repo.get_by_id(theme_id)

        if not theme:
            raise HTTPException(status_code=404, detail=f"Theme {theme_id} not found")

        # Get feedback via theme membership
        stmt = (
            select(Feedback, ThemeMembership.similarity)
            .join(ThemeMembership, ThemeMembership.feedback_id == Feedback.id)
            .where(ThemeMembership.theme_id == theme_id)
            .where(ThemeMembership.run_id == theme.last_run_id)
            .order_by(ThemeMembership.similarity.desc())
            .limit(limit)
        )

        result = await session.execute(stmt)
        rows = list(result.all())

        return {
            "theme_id": theme_id,
            "theme_name": theme.name_en,
            "feedback_count": len(rows),
            "feedback": [
                {
                    "id": str(feedback.id),
                    "title": feedback.title,
                    "content": feedback.content,
                    "classification": feedback.classification,
                    "sentiment": feedback.sentiment,
                    "similarity": similarity,
                    "created_at": feedback.created_at.isoformat(),
                }
                for feedback, similarity in rows
            ],
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get theme feedback: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get theme feedback: {str(e)}")


# Bet endpoints
@router.get("/bets", response_model=List[BetResponse])
async def list_bets(
    status: Optional[str] = Query(None, description="Filter by status"),
    limit: int = Query(20, ge=1, le=100),
    session: AsyncSession = Depends(get_db),
) -> List[BetResponse]:
    """List product bets.

    Args:
        status: Filter by status (draft, in_backlog, etc.)
        limit: Maximum number of bets to return

    Returns:
        List of product bets
    """
    try:
        from sqlalchemy import select
        from app.models.bet import ProductBet

        stmt = select(ProductBet)

        if status:
            try:
                status_enum = BetStatus(status)
                stmt = stmt.where(ProductBet.status == status_enum)
            except ValueError:
                raise HTTPException(status_code=400, detail=f"Invalid status: {status}")

        stmt = stmt.order_by(ProductBet.created_at.desc()).limit(limit)

        result = await session.execute(stmt)
        bets = list(result.scalars().all())

        return [
            BetResponse(
                id=str(bet.id),
                theme_id=str(bet.theme_id) if bet.theme_id else None,
                title=bet.title,
                problem_statement=bet.problem_statement,
                affected_segments=[seg.value for seg in bet.affected_segments],
                est_customer_count=bet.est_customer_count,
                why_now=bet.why_now,
                status=bet.status.value,
                owner_pm=bet.owner_pm,
                declined_reason=bet.declined_reason,
                created_at=bet.created_at.isoformat(),
            )
            for bet in bets
        ]

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to list bets: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to list bets: {str(e)}")


@router.get("/bets/{bet_id}", response_model=BetResponse)
async def get_bet(
    bet_id: str,
    session: AsyncSession = Depends(get_db),
) -> BetResponse:
    """Get bet details by ID.

    Args:
        bet_id: Bet UUID

    Returns:
        Bet details
    """
    try:
        repo = BetRepository(session)
        bet = await repo.get_by_id(bet_id)

        if not bet:
            raise HTTPException(status_code=404, detail=f"Bet {bet_id} not found")

        return BetResponse(
            id=str(bet.id),
            theme_id=str(bet.theme_id) if bet.theme_id else None,
            title=bet.title,
            problem_statement=bet.problem_statement,
            affected_segments=[seg.value for seg in bet.affected_segments],
            est_customer_count=bet.est_customer_count,
            why_now=bet.why_now,
            status=bet.status.value,
            owner_pm=bet.owner_pm,
            declined_reason=bet.declined_reason,
            created_at=bet.created_at.isoformat(),
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get bet {bet_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get bet: {str(e)}")


@router.patch("/bets/{bet_id}/status", response_model=BetResponse)
async def update_bet_status(
    bet_id: str,
    request: UpdateBetStatusRequest,
    session: AsyncSession = Depends(get_db),
) -> BetResponse:
    """Update bet status.

    Args:
        bet_id: Bet UUID
        request: Status update request

    Returns:
        Updated bet details
    """
    try:
        # Validate status
        try:
            status_enum = BetStatus(request.status)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid status: {request.status}")

        # Update bet
        repo = BetRepository(session)
        bet = await repo.update_status(
            bet_id=bet_id,
            status=status_enum,
            owner_pm=request.owner_pm,
            declined_reason=request.declined_reason,
        )

        await session.commit()

        return BetResponse(
            id=str(bet.id),
            theme_id=str(bet.theme_id) if bet.theme_id else None,
            title=bet.title,
            problem_statement=bet.problem_statement,
            affected_segments=[seg.value for seg in bet.affected_segments],
            est_customer_count=bet.est_customer_count,
            why_now=bet.why_now,
            status=bet.status.value,
            owner_pm=bet.owner_pm,
            declined_reason=bet.declined_reason,
            created_at=bet.created_at.isoformat(),
        )

    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update bet status: {e}", exc_info=True)
        await session.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to update bet status: {str(e)}")


@router.get("/bets/{bet_id}/evidence")
async def get_bet_evidence(
    bet_id: str,
    session: AsyncSession = Depends(get_db),
) -> Dict:
    """Get feedback evidence for a bet.

    Args:
        bet_id: Bet UUID

    Returns:
        List of feedback items linked as evidence
    """
    try:
        from sqlalchemy import select
        from app.models.feedback import Feedback
        from app.models.bet import BetEvidence, ProductBet

        # Verify bet exists
        repo = BetRepository(session)
        bet = await repo.get_by_id(bet_id)

        if not bet:
            raise HTTPException(status_code=404, detail=f"Bet {bet_id} not found")

        # Get evidence
        stmt = (
            select(Feedback)
            .join(BetEvidence, BetEvidence.feedback_id == Feedback.id)
            .where(BetEvidence.bet_id == bet_id)
            .order_by(Feedback.created_at.desc())
        )

        result = await session.execute(stmt)
        feedback_items = list(result.scalars().all())

        return {
            "bet_id": bet_id,
            "bet_title": bet.title,
            "evidence_count": len(feedback_items),
            "evidence": [
                {
                    "id": str(f.id),
                    "title": f.title,
                    "content": f.content,
                    "classification": f.classification,
                    "sentiment": f.sentiment,
                    "customer_email": f.customer_email,
                    "created_at": f.created_at.isoformat(),
                }
                for f in feedback_items
            ],
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get bet evidence: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get bet evidence: {str(e)}")
