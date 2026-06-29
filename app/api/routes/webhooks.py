from fastapi import APIRouter, Request, Response
from ... import schemas as s

router = APIRouter()


@router.post("/{source}", status_code=202)
async def inbound_webhook(source: s.SourceType, request: Request):
    # TODO: verify source signature, then enqueue an ingestion job.
    _ = await request.body()
    return Response(status_code=202)
