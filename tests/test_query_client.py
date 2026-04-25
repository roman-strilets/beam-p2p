from collections import deque

from beam_p2p.codec import (
    encode_bool,
    encode_byte_buffer,
    encode_get_assets_list_at_payload,
    encode_get_proof_kernel3_payload,
    encode_height_range,
    encode_uint,
)
from beam_p2p.protocol import MessageType
from beam_p2p.query_client import NodeQueryClient


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