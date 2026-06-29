from fastapi import APIRouter, HTTPException
from ... import mock, schemas as s

router = APIRouter()


@router.get("", response_model=list[s.ThemeSummary])
async def list_themes(trend: s.Trend | None = None, cursor: str | None = None, limit: int = 50):
    return mock.themes(trend)


@router.get("/{theme_id}", response_model=s.ThemeDetail)
async def get_theme(theme_id: str):
    detail = mock.theme_detail(theme_id)
    if not detail:
        raise HTTPException(404, "Not found")
    return detail
