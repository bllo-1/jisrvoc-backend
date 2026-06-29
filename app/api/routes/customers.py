from fastapi import APIRouter
from ... import mock, schemas as s

router = APIRouter()


@router.get("", response_model=list[s.Customer])
async def search_customers(q: str | None = None):
    return mock.customers(q)


@router.get("/{customer_id}/feedback", response_model=list[s.FeedbackItem])
async def customer_feedback(customer_id: str):
    return [i for i in mock._feedback_items() if i.customer_id == customer_id]


@router.get("/{customer_id}/bets", response_model=list[s.BetSummary])
async def customer_bets(customer_id: str):
    return mock.bets()
