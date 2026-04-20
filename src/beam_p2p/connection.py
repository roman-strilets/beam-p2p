"""TCP connection handling for the Beam peer-to-peer protocol."""

from __future__ import annotations

import hmac as hmac_mod
import socket
import sys
import time
from collections import deque
from collections.abc import Sequence

from .codec import decode_peer_info, decode_uint, encode_uint, make_header, parse_header
from .protocol import (
    Address,
    DEFAULT_CONNECT_TIMEOUT,
    DEFAULT_REQUEST_TIMEOUT,
    EXTENSION_VERSION,
    HEADER_SIZE,
    LOGIN_FLAG_SEND_PEERS,
    MAC_SIZE,
    MAX_FRAME_SIZE,
    MessageType,
    message_name,
)
from .secure_channel import SecureChannel
from .utils import extension_bits, format_address, is_crawlable_address


def build_login_payload(login_flags: int, fork_hashes: list[bytes]) -> bytes:
    """Build the binary payload for a Beam ``Login`` message."""
    flags = login_flags | (extension_bits(EXTENSION_VERSION) << 4)
    payload = bytearray(encode_uint(len(fork_hashes)))
    for fork_hash in fork_hashes:
        payload.extend(fork_hash)
    payload.extend(encode_uint(flags))
    return bytes(payload)


def parse_login_payload(payload: bytes) -> tuple[list[bytes], int]:
    """Parse a Beam ``Login`` payload into fork hashes and flags."""
    try:
        count, size = decode_uint(payload)
    except IndexError as exc:
        raise ValueError("login payload is empty") from exc

    offset = size
    fork_hashes: list[bytes] = []
    for _ in range(count):
        end = offset + 32
        if end > len(payload):
            raise ValueError("login payload ended before all fork hashes were read")
        fork_hashes.append(payload[offset:end])
        offset = end

    try:
        flags, size = decode_uint(payload, offset)
    except IndexError as exc:
        raise ValueError("login payload is missing the flags field") from exc

    offset += size
    if offset != len(payload):
        raise ValueError(f"login payload has {len(payload) - offset} trailing byte(s)")

    return fork_hashes, flags


class BeamConnection:
    """Manage one encrypted Beam TCP connection."""

    def __init__(
        self,
        host: str,
        port: int,
        connect_timeout: float = DEFAULT_CONNECT_TIMEOUT,
        read_timeout: float = DEFAULT_REQUEST_TIMEOUT,
        verbose: bool = False,
    ) -> None:
        self.host = host
        self.port = port
        self.connect_timeout = connect_timeout
        self.read_timeout = read_timeout
        self.verbose = verbose
        self.sock: socket.socket | None = None
        self.sc = SecureChannel()
        self._buf = bytearray()
        self._pending: deque[tuple[MessageType, bytes]] = deque()
        self.peer_fork_hashes: list[bytes] = []
        self.peer_login_flags: int | None = None

    def _log(self, message: str) -> None:
        if self.verbose:
            print(message, file=sys.stderr)

    def _require_socket(self) -> socket.socket:
        if self.sock is None:
            raise RuntimeError("connection is not open")
        return self.sock

    def connect(self) -> None:
        self.sock = socket.create_connection((self.host, self.port), timeout=self.connect_timeout)
        self.sock.settimeout(self.read_timeout)

    def remote_address(self) -> Address | None:
        if self.sock is None:
            return None
        host, port = self.sock.getpeername()[:2]
        return host, port

    def _recv(self, size: int) -> bytes:
        sock = self._require_socket()
        while len(self._buf) < size:
            chunk = sock.recv(8192)
            if not chunk:
                raise ConnectionError("connection closed")
            self._buf.extend(chunk)

        payload = bytes(self._buf[:size])
        del self._buf[:size]
        return payload

    def send(self, message_type: int | MessageType, payload: bytes = b"") -> None:
        sock = self._require_socket()
        message_type = MessageType(message_type)
        if self.sc.out_on:
            header = make_header(message_type, len(payload) + MAC_SIZE)
            tag = self.sc.mac(header, payload)
            sock.sendall(self.sc.encrypt(header + payload + tag))
            return

        header = make_header(message_type, len(payload))
        sock.sendall(header + payload)

    def recv(self) -> tuple[MessageType, bytes]:
        header = self.sc.decrypt(self._recv(HEADER_SIZE))
        message_type, size = parse_header(header)
        if size > MAX_FRAME_SIZE:
            raise ValueError(f"frame too large: {size}")

        body = self.sc.decrypt(self._recv(size)) if size else b""
        if self.sc.in_on:
            if size < MAC_SIZE:
                raise ValueError(f"secure frame too small: {size}")
            payload, tag = body[:-MAC_SIZE], body[-MAC_SIZE:]
            if not hmac_mod.compare_digest(tag, self.sc.mac(header, payload)):
                raise ValueError("HMAC mismatch")
            return message_type, payload

        return message_type, body

    def recv_message(self, timeout: float | None = None) -> tuple[MessageType, bytes]:
        if self._pending:
            return self._pending.popleft()

        sock = self._require_socket()
        if timeout is None:
            sock.settimeout(None)
        else:
            if timeout <= 0:
                raise socket.timeout()
            sock.settimeout(timeout)
        return self.recv()

    def _queue_message(self, message_type: MessageType, payload: bytes) -> None:
        self._pending.append((message_type, payload))

    def send_time(self) -> None:
        self.send(MessageType.TIME, encode_uint(int(time.time())))

    def handshake(
        self,
        login_flags: int | Sequence[bytes] = 0,
        fork_hashes: list[bytes] | None = None,
    ) -> None:
        """Perform the Beam secure-channel and login handshake.

        For backward compatibility, callers may pass only ``fork_hashes`` as the
        first positional argument. In that mode ``LOGIN_FLAG_SEND_PEERS`` is
        requested automatically.
        """
        if fork_hashes is None and not isinstance(login_flags, int):
            fork_hashes = list(login_flags)
            login_flags = LOGIN_FLAG_SEND_PEERS
        elif fork_hashes is None:
            fork_hashes = []

        nonce = self.sc.generate_nonce()
        node = format_address((self.host, self.port))
        self._log(f"[*] {node} SChannelInitiate ->")
        self.send(MessageType.SCHANNEL_INIT, nonce)

        message_type, payload = self.recv()
        if message_type != MessageType.SCHANNEL_INIT:
            raise RuntimeError(
                f"expected SChannelInitiate, got {message_name(message_type)}"
            )
        self._log(f"[*] {node} <- SChannelInitiate")

        self.send(MessageType.SCHANNEL_READY)
        self.sc.derive_keys(payload)
        self.sc.out_on = True
        self._log(f"[*] {node} outgoing encryption on")

        self.send(MessageType.GET_TIME)
        self.send(MessageType.LOGIN, build_login_payload(login_flags, fork_hashes))

        message_type, _ = self.recv()
        if message_type != MessageType.SCHANNEL_READY:
            raise RuntimeError(
                f"expected SChannelReady, got {message_name(message_type)}"
            )

        self.sc.in_on = True
        self._log(f"[*] {node} duplex encryption on")

        saw_login = False
        while not saw_login:
            message_type, payload = self.recv()
            if message_type == MessageType.BYE:
                raise RuntimeError(
                    f"bye after login: {chr(payload[0]) if payload else '?'}"
                )
            if message_type == MessageType.GET_TIME:
                self.send_time()
                continue
            if message_type == MessageType.TIME:
                server_time, _ = decode_uint(payload)
                self._log(f"[*] {node} time offset: {server_time - int(time.time()):+d}s")
                continue
            if message_type == MessageType.AUTHENTICATION:
                self._log(f"[*] {node} <- Authentication")
                continue
            if message_type == MessageType.PING:
                self.send(MessageType.PONG)
                continue
            if message_type == MessageType.LOGIN:
                self._log(f"[*] {node} <- Login")
                try:
                    self.peer_fork_hashes, self.peer_login_flags = parse_login_payload(payload)
                except ValueError as exc:
                    raise RuntimeError(f"invalid Login payload: {exc}") from exc
                saw_login = True
                continue

            self._log(f"[*] {node} queued {message_name(message_type)} during login")
            self._queue_message(message_type, payload)

    def collect_peers(self, timeout: float) -> dict[Address, bytes]:
        """Collect peer advertisements until ``timeout`` expires."""
        peers: dict[Address, bytes] = {}
        deadline = time.monotonic() + timeout
        sock = self._require_socket()

        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                break

            sock.settimeout(max(min(remaining, self.read_timeout), 0.1))
            try:
                message_type, payload = self.recv_message()
            except (socket.timeout, ConnectionError):
                break

            if message_type == MessageType.PEER_INFO:
                peer = decode_peer_info(payload)
                if peer is None:
                    self._log(f"[*] {self.host}:{self.port} ignored short PeerInfo")
                    continue
                peer_id, address = peer
                if not is_crawlable_address(address):
                    self._log(
                        f"[*] {self.host}:{self.port} ignored unusable peer {format_address(address)}"
                    )
                    continue
                if address not in peers:
                    peers[address] = peer_id
                    self._log(f"[*] {self.host}:{self.port} peer {format_address(address)}")
                continue

            if message_type == MessageType.GET_TIME:
                self.send_time()
                continue
            if message_type == MessageType.TIME:
                server_time, _ = decode_uint(payload)
                self._log(
                    f"[*] {self.host}:{self.port} time offset: {server_time - int(time.time()):+d}s"
                )
                continue
            if message_type == MessageType.AUTHENTICATION:
                self._log(f"[*] {self.host}:{self.port} <- Authentication")
                continue
            if message_type == MessageType.LOGIN:
                self._log(f"[*] {self.host}:{self.port} <- Login")
                continue
            if message_type == MessageType.PING:
                self.send(MessageType.PONG)
                continue
            if message_type == MessageType.BYE:
                self._log(
                    f"[*] {self.host}:{self.port} bye ({chr(payload[0]) if payload else '?'})"
                )
                break
            if message_type == MessageType.NEW_TIP:
                self._log(f"[*] {self.host}:{self.port} <- NewTip")
                continue

            self._log(
                f"[*] {self.host}:{self.port} <- {message_name(message_type)} ({len(payload)}B)"
            )

        return peers

    def close(self) -> None:
        if self.sock is None:
            return
        try:
            self.send(MessageType.BYE, b"s")
        except Exception:
            pass
        self.sock.close()
        self.sock = None
