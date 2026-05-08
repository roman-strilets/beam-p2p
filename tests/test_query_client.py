from collections import deque

from beam_p2p.codec import (
    encode_bool,
    encode_byte_buffer,
    encode_get_assets_list_at_payload,
    encode_get_body_payload,
    encode_get_proof_kernel3_payload,
    encode_height_range,
    encode_uint,
)
from beam_p2p.protocol import MessageType
from beam_p2p.protocol_models import BlockHeader, DecodedBlock, TxCounts
from beam_p2p.query_client import BodyFetchPlan, NodeQueryClient


def _asset_full_payload(*, asset_id: int) -> bytes:
    return b"".join(
        (
            encode_uint(asset_id),
            b"\x01" * 32,
            (asset_id * 10).to_bytes(16, "big"),
            encode_uint(7),
            encode_byte_buffer(f"asset-{asset_id}".encode()),
        )
    )


def _header_pack_payload(*, start_height: int) -> bytes:
    return b"".join(
        (
            encode_uint(start_height),
            b"\x11" * 32,
            b"\x00" * 32,
            encode_uint(1),
            b"\x22" * 32,
            b"\x33" * 32,
            encode_uint(123456),
            b"\x44" * 104,
            encode_uint(0),
            b"\x55" * 8,
        )
    )


def _new_tip_payload(*, height: int) -> bytes:
    return b"".join(
        (
            encode_uint(height),
            b"\x11" * 32,
            b"\x00" * 32,
            b"\x22" * 32,
            b"\x33" * 32,
            encode_uint(123456),
            b"\x44" * 104,
            encode_uint(0),
            b"\x55" * 8,
        )
    )


def _body_payload(*, perishable: bytes = b"", eternal: bytes = b"") -> bytes:
    return encode_byte_buffer(perishable) + encode_byte_buffer(eternal)


class FakeConnection:
    def __init__(self, responses: list[tuple[MessageType, bytes]]) -> None:
        self.host = "127.0.0.1"
        self.port = 10000
        self.peer_fork_hashes: list[bytes] = []
        self.sent: list[tuple[MessageType, bytes]] = []
        self._responses = deque(responses)

    def send(self, message_type: int | MessageType, payload: bytes = b"") -> None:
        self.sent.append((MessageType(message_type), payload))

    def recv_message(self, timeout: float | None = None) -> tuple[MessageType, bytes]:
        return self._responses.popleft()

    def send_time(self) -> None:
        self.send(MessageType.TIME, b"time")


def test_get_state_summary_handles_ping_while_waiting() -> None:
    summary_payload = b"".join(encode_uint(value) for value in (10, 20, 30, 40, 50, 60, 70, 80))
    connection = FakeConnection(
        [
            (MessageType.PING, b""),
            (MessageType.STATE_SUMMARY, summary_payload),
        ]
    )
    client = NodeQueryClient(connection, request_timeout=1.0, verbose=False)

    summary = client.get_state_summary()

    assert summary.txo_lo == 10
    assert connection.sent == [
        (MessageType.GET_STATE_SUMMARY, b""),
        (MessageType.PONG, b""),
    ]


def test_get_assets_list_at_auto_paginates() -> None:
    first_page = b"".join(
        (
            encode_uint(1),
            _asset_full_payload(asset_id=7),
            encode_bool(True),
        )
    )
    second_page = b"".join(
        (
            encode_uint(1),
            _asset_full_payload(asset_id=8),
            encode_bool(False),
        )
    )
    connection = FakeConnection(
        [
            (MessageType.ASSETS_LIST_AT, first_page),
            (MessageType.ASSETS_LIST_AT, second_page),
        ]
    )
    client = NodeQueryClient(connection, request_timeout=1.0, verbose=False)

    page = client.get_assets_list_at(height=100, aid0=7)

    assert [asset.asset_id for asset in page.assets] == [7, 8]
    assert page.more is False
    assert connection.sent == [
        (MessageType.GET_ASSETS_LIST_AT, encode_get_assets_list_at_payload(height=100, aid0=7)),
        (MessageType.GET_ASSETS_LIST_AT, encode_get_assets_list_at_payload(height=100, aid0=8)),
    ]


def test_get_proof_kernel3_uses_position_payload() -> None:
    proof_payload = b"".join((encode_uint(0), encode_uint(77), b"\x00"))
    connection = FakeConnection([(MessageType.PROOF_KERNEL2, proof_payload)])
    client = NodeQueryClient(connection, request_timeout=1.0, verbose=False)

    proof = client.get_proof_kernel3((12, 5), with_proof=False)

    assert proof.height == 77
    assert proof.kernel is None
    assert connection.sent == [
        (
            MessageType.GET_PROOF_KERNEL3,
            encode_get_proof_kernel3_payload(height=12, pos=5, with_proof=False),
        )
    ]


def test_set_dependent_context_sends_optional_hash_payload() -> None:
    connection = FakeConnection([])
    client = NodeQueryClient(connection, request_timeout=1.0, verbose=False)

    client.set_dependent_context("aa" * 32)

    assert connection.sent == [(MessageType.SET_DEPENDENT_CONTEXT, b"\x01" + bytes.fromhex("aa" * 32))]


def test_request_headers_handles_ping_while_waiting() -> None:
    connection = FakeConnection(
        [
            (MessageType.PING, b""),
            (MessageType.HDR_PACK, _header_pack_payload(start_height=12)),
        ]
    )
    client = NodeQueryClient(connection, request_timeout=1.0, verbose=False)

    headers = client.request_headers(start_height=12, stop_height=12)

    assert [header.height for header in headers] == [12]
    assert headers[0].previous_hash == ("11" * 32)
    assert connection.sent == [
        (MessageType.ENUM_HDRS, encode_height_range(12, 12)),
        (MessageType.PONG, b""),
    ]


def test_wait_for_tip_handles_ping_while_waiting() -> None:
    connection = FakeConnection(
        [
            (MessageType.PING, b""),
            (MessageType.NEW_TIP, _new_tip_payload(height=12)),
        ]
    )
    client = NodeQueryClient(connection, request_timeout=1.0, verbose=False)

    header = client.wait_for_tip()

    assert header.height == 12
    assert header.previous_hash == ("11" * 32)
    assert header.timestamp == 123456
    assert connection.sent == [(MessageType.PONG, b"")]


def test_get_treasury_payload_requests_zero_body_and_extracts_eternal() -> None:
    connection = FakeConnection(
        [
            (MessageType.BODY, _body_payload(perishable=b"ignored", eternal=b"treasury")),
        ]
    )
    client = NodeQueryClient(connection, request_timeout=1.0, verbose=False)

    payload = client.get_treasury_payload()

    assert payload == b"treasury"
    assert connection.sent == [
        (MessageType.GET_BODY, encode_get_body_payload(0, b"\x00" * 32)),
    ]


def test_fetch_blocks_rejects_partial_body_pack(monkeypatch) -> None:
    connection = FakeConnection([])
    client = NodeQueryClient(connection, request_timeout=1.0, verbose=False)
    headers = [
        BlockHeader(
            height=12,
            hash="11" * 32,
            previous_hash="22" * 32,
            chainwork="00" * 32,
            kernels="33" * 32,
            definition="44" * 32,
            timestamp=123456,
            packed_difficulty=0,
            difficulty=1.0,
            rules_hash=None,
            pow_indices_hex="55" * 104,
            pow_nonce_hex="66" * 8,
        ),
        BlockHeader(
            height=13,
            hash="77" * 32,
            previous_hash="11" * 32,
            chainwork="00" * 32,
            kernels="88" * 32,
            definition="99" * 32,
            timestamp=123457,
            packed_difficulty=0,
            difficulty=1.0,
            rules_hash=None,
            pow_indices_hex="aa" * 104,
            pow_nonce_hex="bb" * 8,
        ),
    ]
    partial_blocks = [
        DecodedBlock(
            header=headers[0],
            inputs=[],
            outputs=[],
            counts=TxCounts(inputs=0, outputs=0, kernels=0, kernels_mixed=False),
            kernels=[],
            offset=None,
            raw_payload=None,
        )
    ]

    monkeypatch.setattr(client, "request_headers", lambda **_: headers)
    monkeypatch.setattr(
        client,
        "request_body_range_payload",
        lambda **_: (MessageType.BODY_PACK, b"ignored"),
    )
    monkeypatch.setattr(
        "beam_p2p.query_client.deserialize_body_pack_payloads",
        lambda payload, decoded_headers: partial_blocks,
    )

    try:
        client.fetch_blocks(
            plan=BodyFetchPlan(
                start_height=12,
                stop_height=13,
                flag_perishable=0,
                flag_eternal=0,
                block0=0,
                horizon_lo1=0,
                horizon_hi1=0,
            )
        )
    except RuntimeError as exc:
        assert "node returned 1 body payload(s) for 2 header(s)" in str(exc)
    else:
        raise AssertionError("expected fetch_blocks to reject partial BodyPack data")