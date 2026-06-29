from fastapi import APIRouter
from ... import mock, schemas as s

router = APIRouter()


@router.get("/connectors", response_model=list[s.Connector])
async def connectors():
    return mock.connectors()


@router.get("/pm-routing", response_model=list[s.RoutingRule])
async def pm_routing():
    return mock.routing_rules()
