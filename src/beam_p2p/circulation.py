"""Beam consensus helpers plus live node-backed circulation queries.

This module exposes three related surfaces:

- Deterministic consensus helpers derived from Beam's mainnet emission rules.
- Live blockchain-backed latest-tip circulation obtained from a Beam node.
- Legacy explorer-status parsing helpers retained for compatibility.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import TYPE_CHECKING
from urllib.request import urlopen

from .protocol_models import BlockHeader
from .treasury import deserialize_treasury_data, treasury_amount_at_height

if TYPE_CHECKING:
    from .query_client import NodeQueryClient


BEAM_GROTH = 100_000_000
INITIAL_EMISSION_GROTH = 80 * BEAM_GROTH
FIRST_EMISSION_DROP_HEIGHT = 1440 * 365
EMISSION_DROP_CYCLE_HEIGHT = 1440 * 365 * 4
EXPLORER_STATUS_URL = "https://explorer-api.beam.mw/mainnet/api/v1/status"
TREASURY_FIRST_PERIOD_GROTH = 20 * BEAM_GROTH
TREASURY_REST_PERIOD_GROTH = 10 * BEAM_GROTH


@dataclass(frozen=True)
class TreasurySchedule:
    """Treasury release parameters used to build Beam burst schedules."""

    first_period_subsidy_groth: int = TREASURY_FIRST_PERIOD_GROTH
    rest_period_subsidy_groth: int = TREASURY_REST_PERIOD_GROTH
    first_period_bursts: int = 12
    maturity0_height: int = 0
    maturity_step_height: int = 1440 * 365 // 12
    bursts: int = 12 * 5


@dataclass(frozen=True)
class TreasuryBurst:
    """One cumulative treasury release boundary."""

    height: int
    value_groth: int


@dataclass(frozen=True)
class CirculationBreakdown:
    """Source-derived Beam circulation values at one height."""

    height: int
    current_emission_groth: int
    treasury_released_groth: int
    current_circulation_groth: int
    total_emission_groth: int
    treasury_total_groth: int
    total_circulation_groth: int


@dataclass(frozen=True)
class PublishedCirculation:
    """Published latest-tip circulation values from the Beam explorer API."""

    height: int
    timestamp: int
    difficulty: int
    total_emission_groth: int
    treasury_circulation_groth: int
    mined_circulation_groth: int
    total_circulation_groth: int


@dataclass(frozen=True)
class BlockchainCirculation:
    """Blockchain-backed Beam circulation values at one live tip."""

    height: int
    timestamp: int
    total_emission_groth: int
    treasury_circulation_groth: int
    mined_circulation_groth: int
    total_circulation_groth: int


MAINNET_TREASURY_SCHEDULE = TreasurySchedule()


def _emission_segment(height: int, base_subsidy_groth: int) -> tuple[int, int]:
    if height <= 0 or base_subsidy_groth <= 0:
        return 0, height

    height_zero_based = height - 1
    if height_zero_based < FIRST_EMISSION_DROP_HEIGHT:
        return base_subsidy_groth, FIRST_EMISSION_DROP_HEIGHT + 1

    epoch_index = (
        1
        + (height_zero_based - FIRST_EMISSION_DROP_HEIGHT)
        // EMISSION_DROP_CYCLE_HEIGHT
    )

    adjusted_base = base_subsidy_groth
    if epoch_index >= 2:
        adjusted_base += adjusted_base >> 2

    value_groth = adjusted_base >> epoch_index
    if value_groth == 0:
        return 0, height

    next_height = (
        FIRST_EMISSION_DROP_HEIGHT + epoch_index * EMISSION_DROP_CYCLE_HEIGHT + 1
    )
    return value_groth, next_height


def emission_at_height(height: int, *, base_subsidy_groth: int = INITIAL_EMISSION_GROTH) -> int:
    """Return the Beam emission for one block height in groth."""

    value_groth, _ = _emission_segment(height, base_subsidy_groth)
    return value_groth


def emission_for_range(
    start_height: int,
    stop_height: int,
    *,
    base_subsidy_groth: int = INITIAL_EMISSION_GROTH,
) -> int:
    """Return the inclusive emission sum for ``[start_height, stop_height]``."""

    if stop_height < start_height or stop_height <= 0 or base_subsidy_groth <= 0:
        return 0

    total_groth = 0
    height = max(1, start_height)
    while height <= stop_height:
        value_groth, next_height = _emission_segment(height, base_subsidy_groth)
        if value_groth == 0:
            break

        segment_stop_exclusive = min(stop_height + 1, next_height)
        total_groth += value_groth * (segment_stop_exclusive - height)
        height = next_height

    return total_groth


def total_emission(*, base_subsidy_groth: int = INITIAL_EMISSION_GROTH) -> int:
    """Return the full finite emission implied by one Beam subsidy base."""

    if base_subsidy_groth <= 0:
        return 0

    total_groth = 0
    height = 1
    while True:
        value_groth, next_height = _emission_segment(height, base_subsidy_groth)
        if value_groth == 0:
            return total_groth

        total_groth += value_groth * (next_height - height)
        height = next_height


def treasury_bursts(
    *,
    schedule: TreasurySchedule = MAINNET_TREASURY_SCHEDULE,
) -> list[TreasuryBurst]:
    """Return the treasury burst schedule implied by ``schedule``."""

    bursts: list[TreasuryBurst] = []
    maturity_max = schedule.maturity0_height

    for index in range(schedule.bursts):
        maturity_max += schedule.maturity_step_height
        per_block_subsidy_groth = (
            schedule.first_period_subsidy_groth
            if index < schedule.first_period_bursts
            else schedule.rest_period_subsidy_groth
        )
        value_groth = per_block_subsidy_groth * schedule.maturity_step_height
        if value_groth <= 0:
            continue
        bursts.append(TreasuryBurst(height=maturity_max, value_groth=value_groth))

    return bursts


def treasury_released(
    height: int,
    *,
    schedule: TreasurySchedule = MAINNET_TREASURY_SCHEDULE,
) -> int:
    """Return treasury released at or before ``height``."""

    if height <= 0:
        return 0

    return sum(
        burst.value_groth
        for burst in treasury_bursts(schedule=schedule)
        if burst.height <= height
    )


def treasury_total(*, schedule: TreasurySchedule = MAINNET_TREASURY_SCHEDULE) -> int:
    """Return the full treasury amount implied by ``schedule``."""

    return sum(burst.value_groth for burst in treasury_bursts(schedule=schedule))


def circulation_at_height(
    height: int,
    *,
    schedule: TreasurySchedule = MAINNET_TREASURY_SCHEDULE,
) -> CirculationBreakdown:
    """Return source-derived Beam circulation values for ``height``."""

    current_emission_groth = emission_for_range(1, height)
    treasury_released_groth = treasury_released(height, schedule=schedule)
    total_emission_groth = total_emission()
    treasury_total_groth = treasury_total(schedule=schedule)

    return CirculationBreakdown(
        height=height,
        current_emission_groth=current_emission_groth,
        treasury_released_groth=treasury_released_groth,
        current_circulation_groth=(
            current_emission_groth + treasury_released_groth
        ),
        total_emission_groth=total_emission_groth,
        treasury_total_groth=treasury_total_groth,
        total_circulation_groth=total_emission_groth + treasury_total_groth,
    )


def fetch_blockchain_circulation(
    client: "NodeQueryClient",
    *,
    tip_header: BlockHeader | None = None,
    tip_timeout: float = 5.0,
) -> BlockchainCirculation:
    """Fetch latest-tip Beam circulation directly from a live node.

    The treasury side is derived from the node's treasury blob, while the mined
    side follows Beam's consensus emission rules up to the reported tip height.
    """

    if tip_header is None:
        tip_header = client.wait_for_tip(timeout=tip_timeout)

    treasury_data = deserialize_treasury_data(client.get_treasury_payload())
    treasury_total_groth = sum(
        group.value_groth for group in treasury_data.groups if group.asset_id == 0
    )
    treasury_circulation_groth = treasury_amount_at_height(
        treasury_data,
        tip_header.height,
        asset_id=0,
    )
    mined_circulation_groth = emission_for_range(1, tip_header.height)
    total_emission_groth = total_emission() + treasury_total_groth

    return BlockchainCirculation(
        height=tip_header.height,
        timestamp=tip_header.timestamp,
        total_emission_groth=total_emission_groth,
        treasury_circulation_groth=treasury_circulation_groth,
        mined_circulation_groth=mined_circulation_groth,
        total_circulation_groth=(
            mined_circulation_groth + treasury_circulation_groth
        ),
    )


def parse_explorer_status_payload(payload: str) -> PublishedCirculation:
    """Parse one Beam explorer ``/status`` JSON payload."""

    decoded = json.loads(payload)
    if decoded.get("status") != "success":
        raise ValueError("explorer status payload did not report success")

    data = decoded.get("data")
    if not isinstance(data, dict):
        raise ValueError("explorer status payload is missing the data object")

    try:
        return PublishedCirculation(
            height=int(data["height"]),
            timestamp=int(data["timestamp"]),
            difficulty=int(data["difficulty"]),
            total_emission_groth=int(data["total_coins_emission"]) * BEAM_GROTH,
            treasury_circulation_groth=int(data["coins_in_circulation_treasury"])
            * BEAM_GROTH,
            mined_circulation_groth=int(data["coins_in_circulation_mined"])
            * BEAM_GROTH,
            total_circulation_groth=int(data["total_coins_in_circulation"])
            * BEAM_GROTH,
        )
    except KeyError as exc:
        raise ValueError(
            f"explorer status payload is missing field: {exc.args[0]}"
        ) from exc


def fetch_published_circulation(
    *,
    url: str = EXPLORER_STATUS_URL,
    timeout: float = 10.0,
) -> PublishedCirculation:
    """Fetch the latest published Beam circulation from the explorer API."""

    with urlopen(url, timeout=timeout) as response:
        payload = response.read().decode("utf-8")
    return parse_explorer_status_payload(payload)