"""
Customers API endpoints - customer lookup, feedback history, related bets.
Matches frontend contract from jisrvoc-frontend/src/lib/api/customers.ts
"""
from fastapi import APIRouter, Query
from typing import List, Optional
from ...schemas_new import Customer, FeedbackItem, ProductBet
from ... import mock_data

router = APIRouter()


@router.get("", response_model=List[Customer])
async def list_customers(q: Optional[str] = Query(None)):
    """
    @endpoint GET /api/v1/customers?q=
    Returns all customers with optional search filter.
    """
    customers = list(mock_data.CUSTOMERS)

    # Apply search filter
    if q:
        q_lower = q.lower()
        customers = [
            c for c in customers
            if q_lower in c.name.lower() or q_lower in c.industry.lower()
        ]

    # Sort by name
    customers.sort(key=lambda c: c.name)

    return customers


@router.get("/{customer_id}", response_model=Customer)
async def get_customer(customer_id: str):
    """
    @endpoint GET /api/v1/customers/:id
    Returns single customer by ID.
    """
    customer = next((c for c in mock_data.CUSTOMERS if c.id == customer_id), None)
    if not customer:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail=f"Customer {customer_id} not found")
    return customer


@router.get("/{customer_id}/feedback", response_model=List[FeedbackItem])
async def get_customer_feedback(customer_id: str):
    """
    @endpoint GET /api/v1/customers/:id/feedback
    Returns all feedback from this customer.
    """
    # Verify customer exists
    customer = next((c for c in mock_data.CUSTOMERS if c.id == customer_id), None)
    if not customer:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail=f"Customer {customer_id} not found")

    # Get feedback for this customer
    feedback = mock_data.get_feedback_for_customer(customer_id)

    # Sort by date descending
    feedback.sort(key=lambda f: f.date, reverse=True)

    return feedback


@router.get("/{customer_id}/bets", response_model=List[ProductBet])
async def get_customer_bets(customer_id: str):
    """
    @endpoint GET /api/v1/customers/:id/bets
    Returns all bets related to this customer's feedback.
    Finds bets where bet.theme_id matches any theme from customer's feedback.
    """
    # Verify customer exists
    customer = next((c for c in mock_data.CUSTOMERS if c.id == customer_id), None)
    if not customer:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail=f"Customer {customer_id} not found")

    # Get bets for this customer
    bets = mock_data.get_bets_for_customer(customer_id)

    # Sort by vote_weight descending
    bets.sort(key=lambda b: b.vote_weight, reverse=True)

    return bets
