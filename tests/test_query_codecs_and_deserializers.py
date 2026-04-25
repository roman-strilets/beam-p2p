from beam_p2p.codec import (
    encode_bool,
    encode_byte_buffer,
    encode_contract_logs_enum_payload,
    encode_get_proof_kernel2_payload,
    encode_uint,
)
from beam_p2p.deserializers import (
    deserialize_assets_list_at_payload,
    deserialize_contract_logs_payload,
    deserialize_contract_vars_payload,
    deserialize_proof_kernel2_payload,
    deserialize_state_summary_payload,
)


MAX_HEIGHT = (1 << 64) - 1


def _uint256(value: int) -> bytes:
    return value.to_bytes(32, "big")


def _amount_big(value: int) -> bytes:
    return value.to_bytes(16, "big")


def _merkle_proof(nodes: list[tuple[bool, bytes]]) -> bytes:
    return encode_uint(len(nodes)) + b"".join(
        encode_bool(on_right) + node_hash for on_right, node_hash in nodes
    )


def _asset_full_payload(
    *,
    asset_id: int,
    owner: bytes,
    value: int,
    lock_height: int,
    metadata: bytes,
    flags: int | None = None,
    actual_lock_height: int | None = None,
    deposit: int | None = None,
) -> bytes:
    payload = bytearray()
    payload.extend(encode_uint(asset_id))
    payload.extend(owner)
    payload.extend(_amount_big(value))
    payload.extend(encode_uint(lock_height))
    payload.extend(encode_byte_buffer(metadata))

    if flags is not None:
        payload.extend(encode_uint(flags))
        payload.extend(encode_uint(actual_lock_height or 0))
        if flags & 1:
            payload.extend(encode_uint(deposit or 0))

    return bytes(payload)


def test_encode_get_proof_kernel2_payload_matches_beam_layout() -> None:
    payload = encode_get_proof_kernel2_payload(b"\x11" * 32, fetch=True)

    assert payload == (b"\x11" * 32) + b"\x01"


def test_encode_contract_logs_enum_payload_matches_beam_layout() -> None:
    payload = encode_contract_logs_enum_payload(
        key_min=b"a",
        key_max=b"b",
        pos_min=(7, 3),
        pos_max=(9, 4),
    )

    assert payload == b"".join(
        (
            encode_byte_buffer(b"a"),
            encode_byte_buffer(b"b"),
            encode_uint(7),
            encode_uint(3),
            encode_uint(9),
            encode_uint(4),
        )
    )


def test_deserialize_state_summary_payload() -> None:
    payload = b"".join(encode_uint(value) for value in (1, 2, 3, 4, 5, 6, 7, 8))

    summary = deserialize_state_summary_payload(payload)

    assert summary.txo_lo == 1
    assert summary.kernels == 2
    assert summary.txos == 3
    assert summary.utxos == 4
    assert summary.shielded_outs == 5
    assert summary.shielded_ins == 6
    assert summary.assets_max == 7
    assert summary.assets_active == 8


def test_deserialize_assets_list_at_payload_handles_default_and_contract_assets() -> None:
    asset_default = _asset_full_payload(
        asset_id=7,
        owner=b"\x11" * 32,
        value=123,
        lock_height=21,
        metadata=b"beam",
    )
    asset_contract = _asset_full_payload(
        asset_id=8,
        owner=b"\x22" * 32,
        value=456,
        lock_height=MAX_HEIGHT,
        metadata=b"contract-owned",
        flags=3,
        actual_lock_height=42,
        deposit=999,
    )
    payload = b"".join((encode_uint(2), asset_default, asset_contract, encode_bool(False)))

    page = deserialize_assets_list_at_payload(payload)

    assert [asset.asset_id for asset in page.assets] == [7, 8]
    assert page.more is False
    assert page.next_asset_id == 9

    default_asset, contract_asset = page.assets
    assert default_asset.info.owner == "11" * 32
    assert default_asset.info.contract_id is None
    assert default_asset.info.uses_default_deposit is True
    assert default_asset.info.deposit is None
    assert default_asset.info.metadata.text == "beam"

    assert contract_asset.info.owner == "22" * 32
    assert contract_asset.info.contract_id == "22" * 32
    assert contract_asset.info.uses_default_deposit is False
    assert contract_asset.info.deposit == 999
    assert contract_asset.info.lock_height == 42
    assert contract_asset.info.value == 456


def test_deserialize_contract_vars_payload() -> None:
    raw = b"".join(
        (
            encode_uint(3),
            encode_uint(5),
            b"one",
            b"first",
            encode_uint(3),
            encode_uint(6),
            b"two",
            b"second",
        )
    )
    payload = encode_byte_buffer(raw) + encode_bool(True)

    page = deserialize_contract_vars_payload(payload)

    assert page.more is True
    assert [(entry.key, entry.value) for entry in page.entries] == [
        (b"one", b"first"),
        (b"two", b"second"),
    ]


def test_deserialize_contract_logs_payload_applies_delta_positions() -> None:
    raw = b"".join(
        (
            encode_uint(5),
            encode_uint(3),
            encode_uint(2),
            encode_uint(2),
            b"k1",
            b"v1",
            encode_uint(0),
            encode_uint(4),
            encode_uint(2),
            encode_uint(2),
            b"k2",
            b"v2",
        )
    )
    payload = encode_byte_buffer(raw) + encode_bool(False)

    page = deserialize_contract_logs_payload(payload)

    assert page.more is False
    assert [(entry.position.height, entry.position.pos) for entry in page.entries] == [
        (5, 3),
        (5, 7),
    ]
    assert [entry.key for entry in page.entries] == [b"k1", b"k2"]


def test_deserialize_proof_kernel2_payload_supports_null_kernel() -> None:
    payload = b"".join(
        (
            _merkle_proof([(True, b"\xaa" * 32)]),
            encode_uint(99),
            b"\x00",
        )
    )

    proof = deserialize_proof_kernel2_payload(payload)

    assert proof.height == 99
    assert proof.kernel is None
    assert proof.proof[0].on_right is True
    assert proof.proof[0].hash == "aa" * 32