class IndexNotDeployedError(Exception):
    """Qdrant has no collection yet — nothing has been indexed (see Task 10's /deploy).

    Distinct from the state's `error` field: that's for a specific SQL attempt
    failing mid-loop (handled by the repair cycle). This is "the agent can't even
    start" — the caller (Task 13's /ask) should catch it and say so plainly.
    """
