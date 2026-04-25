"""Compatibility shim for the unified synchronous Beam node client."""

from .query_client import (
    BODY_FLAG_FULL,
    BODY_FLAG_NONE,
    BODY_FLAG_RECOVERY1,
    BodyFetchPlan,
    NodeQueryClient,
)


NodeBlockFetcher = NodeQueryClient
