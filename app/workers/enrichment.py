"""Async enrichment pipeline (Phase 1). Wire to Celery/Arq + an in-region LLM.

Pipeline per raw ticket:
  1. decompose()  -> split multi-point tickets into cards (PRD 6.3)
  2. enrich()     -> category, area, sentiment, urgency, language, EN summary (PRD 6.1/6.2)
  3. embed()      -> multilingual vector for cross-language clustering
All steps persist structured output + model/version for audit and re-runs.
"""


async def decompose(raw_text: str) -> list[str]:
    """Return distinct points. Single-topic tickets return one element."""
    raise NotImplementedError("Phase 1: structured LLM call with schema + confidence threshold")


async def enrich(card_text: str) -> dict:
    """Return {summary_en, category, area, sentiment, urgency, language} via in-region LLM."""
    raise NotImplementedError("Phase 1: structured-output LLM call; English output regardless of input language")


async def embed(text: str) -> list[float]:
    """Return a multilingual embedding (dim must match db schema vector(N))."""
    raise NotImplementedError("Phase 1: in-region / self-hosted multilingual embedding model")


async def process_ticket(ticket_id: str) -> None:
    """Entry point consumed from the ingestion queue."""
    raise NotImplementedError
