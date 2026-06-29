"""Weekly theme clustering + bet generation (Phase 2). Run via scheduler/Temporal.

  1. load embeddings for in-scope items
  2. cluster (HDBSCAN/agglomerative)
  3. match new clusters to existing themes by centroid similarity -> STABLE identity (PRD 6.4)
  4. compute trend, vote_weight, segment breakdown, representative verbatims
  5. for top themes, generate draft product bets (PRD 6.5)
"""


async def run_weekly_clustering(run_id: str) -> None:
    raise NotImplementedError(
        "Phase 2: embed -> cluster -> stable-identity match -> persist themes -> generate bets")
