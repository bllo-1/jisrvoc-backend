from fastapi import APIRouter
from ... import mock, schemas as s

router = APIRouter()


@router.get("/metrics", response_model=s.OverviewMetrics)
async def metrics():
    return mock.overview_metrics()


@router.get("/volume-trend", response_model=list[s.TrendPoint])
async def volume_trend(weeks: int = 12):
    return mock.volume_trend(weeks)


@router.get("/by-source", response_model=list[s.CountBucket])
async def by_source():
    return mock.by_source()


@router.get("/by-product-area", response_model=list[s.CountBucket])
async def by_product_area():
    return mock.by_product_area()


@router.get("/top-themes", response_model=list[s.ThemeSummary])
async def top_themes(limit: int = 5):
    return mock.top_themes(limit)
