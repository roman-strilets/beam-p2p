from beam_p2p import (
    BEAM_GROTH,
    BlockchainCirculation,
    FIRST_EMISSION_DROP_HEIGHT,
    INITIAL_EMISSION_GROTH,
    MAINNET_TREASURY_SCHEDULE,
    circulation_at_height,
    emission_at_height,
    emission_for_range,
    fetch_blockchain_circulation,
    fetch_published_circulation,
    parse_explorer_status_payload,
    total_emission,
    treasury_bursts,
    treasury_released,
    treasury_total,
)
from beam_p2p.protocol_models import BlockHeader
from beam_p2p.treasury import TreasuryData, TreasuryGroup


class DummyBlockchainClient:
    def __init__(self, tip_header: BlockHeader, treasury_payload: bytes) -> None:
        self.tip_header = tip_header
        self.treasury_payload = treasury_payload
        self.tip_timeouts: list[float] = []

    def wait_for_tip(self, *, timeout: float | None = None) -> BlockHeader:
        self.tip_timeouts.append(0.0 if timeout is None else timeout)
        return self.tip_header

    def get_treasury_payload(self) -> bytes:
        return self.treasury_payload


def test_parse_explorer_status_payload() -> None:
    payload = """{
        "status": "success",
        "data": {
            "height": 3851812,
            "timestamp": 1778266013,
            "total_coins_emission": 262800000,
            "coins_in_circulation_treasury": 43362000,
            "coins_in_circulation_mined": 155384150,
            "total_coins_in_circulation": 198746150,
            "difficulty": 9922855
        }
    }"""

    status = parse_explorer_status_payload(payload)

    assert status.height == 3_851_812
    assert status.total_emission_groth == 262_800_000 * BEAM_GROTH
    assert status.treasury_circulation_groth == 43_362_000 * BEAM_GROTH
    assert status.mined_circulation_groth == 155_384_150 * BEAM_GROTH
    assert status.total_circulation_groth == 198_746_150 * BEAM_GROTH


def test_fetch_published_circulation_uses_urlopen(monkeypatch) -> None:
    payload = b'{"status":"success","data":{"height":1,"timestamp":2,"total_coins_emission":3,"coins_in_circulation_treasury":4,"coins_in_circulation_mined":5,"total_coins_in_circulation":9,"difficulty":6}}'

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def read(self) -> bytes:
            return payload

    def fake_urlopen(url: str, timeout: float):
        assert url == "https://example.test/status"
        assert timeout == 7.5
        return FakeResponse()

    monkeypatch.setattr("beam_p2p.circulation.urlopen", fake_urlopen)

    status = fetch_published_circulation(
        url="https://example.test/status",
        timeout=7.5,
    )

    assert status.total_emission_groth == 3 * BEAM_GROTH
    assert status.treasury_circulation_groth == 4 * BEAM_GROTH
    assert status.mined_circulation_groth == 5 * BEAM_GROTH
    assert status.total_circulation_groth == 9 * BEAM_GROTH


def test_emission_matches_source_boundaries() -> None:
    assert emission_at_height(0) == 0
    assert emission_at_height(1) == 80 * BEAM_GROTH
    assert emission_at_height(FIRST_EMISSION_DROP_HEIGHT) == 80 * BEAM_GROTH
    assert emission_at_height(FIRST_EMISSION_DROP_HEIGHT + 1) == 40 * BEAM_GROTH
    assert emission_at_height(2_628_000) == 40 * BEAM_GROTH
    assert emission_at_height(2_628_001) == 25 * BEAM_GROTH


def test_emission_range_matches_first_two_segments() -> None:
    assert emission_for_range(1, FIRST_EMISSION_DROP_HEIGHT) == (
        FIRST_EMISSION_DROP_HEIGHT * INITIAL_EMISSION_GROTH
    )
    assert emission_for_range(FIRST_EMISSION_DROP_HEIGHT + 1, 2_628_000) == (
        2_102_400 * 40 * BEAM_GROTH
    )


def test_treasury_schedule_uses_monthly_bursts() -> None:
    bursts = treasury_bursts()

    assert len(bursts) == MAINNET_TREASURY_SCHEDULE.bursts
    assert bursts[0].height == 43_800
    assert bursts[0].value_groth == 43_800 * 20 * BEAM_GROTH
    assert bursts[12].value_groth == 43_800 * 10 * BEAM_GROTH


def test_treasury_release_is_cumulative_by_height() -> None:
    first_burst = treasury_bursts()[0]

    assert treasury_released(first_burst.height - 1) == 0
    assert treasury_released(first_burst.height) == first_burst.value_groth
    assert treasury_released(2_628_000) == treasury_total()


def test_circulation_breakdown_adds_treasury_separately() -> None:
    breakdown = circulation_at_height(FIRST_EMISSION_DROP_HEIGHT)

    assert breakdown.current_emission_groth == emission_for_range(
        1,
        FIRST_EMISSION_DROP_HEIGHT,
    )
    assert breakdown.treasury_released_groth == FIRST_EMISSION_DROP_HEIGHT * 20 * BEAM_GROTH
    assert breakdown.current_circulation_groth == (
        breakdown.current_emission_groth + breakdown.treasury_released_groth
    )


def test_fetch_blockchain_circulation_uses_tip_and_treasury_payload(monkeypatch) -> None:
    tip_header = BlockHeader(
        height=50,
        hash="11" * 32,
        previous_hash="22" * 32,
        chainwork="00" * 32,
        kernels="33" * 32,
        definition="44" * 32,
        timestamp=1234567890,
        packed_difficulty=0,
        difficulty=1.0,
        rules_hash=None,
        pow_indices_hex="55" * 104,
        pow_nonce_hex="66" * 8,
    )
    client = DummyBlockchainClient(tip_header=tip_header, treasury_payload=b"treasury")
    treasury_data = TreasuryData(
        custom_message="beam",
        groups=(
            TreasuryGroup(outputs=(), value_groth=100, asset_id=0, release_height=25),
            TreasuryGroup(outputs=(), value_groth=200, asset_id=0, release_height=60),
            TreasuryGroup(outputs=(), value_groth=300, asset_id=7, release_height=10),
        ),
    )

    monkeypatch.setattr("beam_p2p.circulation.deserialize_treasury_data", lambda payload: treasury_data)

    circulation = fetch_blockchain_circulation(client, tip_timeout=7.5)

    assert isinstance(circulation, BlockchainCirculation)
    assert client.tip_timeouts == [7.5]
    assert circulation.height == 50
    assert circulation.timestamp == 1_234_567_890
    assert circulation.treasury_circulation_groth == 100
    assert circulation.mined_circulation_groth == emission_for_range(1, 50)
    assert circulation.total_circulation_groth == emission_for_range(1, 50) + 100
    assert circulation.total_emission_groth == total_emission() + 300