from fastapi import APIRouter, HTTPException
from ... import mock, schemas as s

router = APIRouter()


@router.get("", response_model=s.FeedbackPage)
async def list_feedback(
    source: s.SourceType | None = None,
    area: s.ProductArea | None = None,
    category: s.Category | None = None,
    sentiment: s.Sentiment | None = None,
    urgency: s.Urgency | None = None,
    language: s.Language | None = None,
    segment: s.Segment | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    q: str | None = None,
    cursor: str | None = None,
    limit: int = 50,
):
    return mock.feedback_page(limit=limit)


@router.get("/{item_id}", response_model=s.FeedbackDetail)
async def get_feedback(item_id: str):
    item = mock.feedback_detail(item_id)
    if not item:
        raise HTTPException(404, "Not found")
    return item


@router.patch("/{item_id}/tags", response_model=s.FeedbackItem)
async def correct_tags(item_id: str, body: s.TagCorrection):
    item = mock.feedback_detail(item_id)
    if not item:
        raise HTTPException(404, "Not found")
    data = item.model_dump()
    data.update({k: v for k, v in body.model_dump().items() if v is not None})
    return s.FeedbackItem(**{k: data[k] for k in s.FeedbackItem.model_fields})
