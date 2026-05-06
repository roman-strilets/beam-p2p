"""Utility helpers shared across the Beam Python tools."""

from __future__ import annotations

from datetime import datetime, timezone

from .protocol import Address
from .protocol_models import EcPoint

CONTRACT_ID_SIZE = 32
SHADER_ID_SIZE = 32
CONTRACT_KEY_TAG_SIZE = 1
CONTRACT_KEY_MAX_SIZE = 256
CONTRACT_STORAGE_KEY_SUFFIX_MAX_SIZE = CONTRACT_KEY_TAG_SIZE + CONTRACT_KEY_MAX_SIZE
CONTRACT_SID_CID_TAG = 16
CONTRACT_LOCKED_AMOUNT_TAG = 1
ASSET_ID_SIZE = 4
AMOUNT_BIG_COMPONENT_SIZE = 8
AMOUNT_BIG_SIZE = AMOUNT_BIG_COMPONENT_SIZE * 2
HEIGHT_SIZE = 8

_CONTRACT_SID_CID_PREFIX = (b"\x00" * CONTRACT_ID_SIZE) + bytes([CONTRACT_SID_CID_TAG])
_CONTRACT_SID_CID_PAYLOAD_SIZE = SHADER_ID_SIZE + CONTRACT_ID_SIZE
_CONTRACT_LOCKED_FUNDS_PREFIX_SIZE = CONTRACT_ID_SIZE + CONTRACT_KEY_TAG_SIZE


def format_address(address: Address) -> str:
    """Format a ``(host, port)`` tuple as ``host:port``."""
    return f"{address[0]}:{address[1]}"


def parse_endpoint(value: str, default_port: int) -> Address:
    """Parse ``host`` or ``host:port`` into an address tuple."""
    host = value
    port = default_port
    if ":" in value:
        host, port_text = value.rsplit(":", 1)
        if not host:
            raise ValueError(f"invalid address: {value!r}")
        try:
            port = int(port_text)
        except ValueError as exc:
            raise ValueError(f"invalid port in address: {value!r}") from exc

    if not 0 < port < 65536:
        raise ValueError(f"port out of range in address: {value!r}")

    return host, port


def parse_fork_hashes(values: list[str]) -> list[bytes]:
    """Decode and validate a list of hex-encoded fork hashes."""
    fork_hashes: list[bytes] = []
    for value in values:
        try:
            raw = bytes.fromhex(value.strip())
        except ValueError as exc:
            raise ValueError(f"invalid fork hash hex: {value!r}") from exc
        if len(raw) != 32:
            raise ValueError(
                f"fork hash must be 32 bytes (64 hex chars), got {len(raw)}"
            )
        fork_hashes.append(raw)
    return fork_hashes


def parse_contract_id(value: str | bytes | bytearray) -> bytes:
    """Decode and validate one Beam contract ID."""
    if isinstance(value, str):
        text = value.strip()
        if text.startswith(("0x", "0X")):
            text = text[2:]
        try:
            raw = bytes.fromhex(text)
        except ValueError as exc:
            raise ValueError(f"invalid contract ID hex: {value!r}") from exc
    elif isinstance(value, (bytes, bytearray)):
        raw = bytes(value)
    else:
        raise TypeError(f"contract ID must be hex text or bytes, got {type(value).__name__}")

    if len(raw) != CONTRACT_ID_SIZE:
        raise ValueError(
            "contract ID must be 32 bytes "
            f"({CONTRACT_ID_SIZE * 2} hex chars), got {len(raw)}"
        )

    return raw


def contract_shader_key(contract_id: str | bytes | bytearray) -> bytes:
    """Return the exact key used to store a deployed contract shader blob."""
    return parse_contract_id(contract_id)


def contract_storage_key_range(
    contract_id: str | bytes | bytearray,
) -> tuple[bytes, bytes]:
    """Return the inclusive Beam storage-key range for one contract's state.

    Beam stores the deployed shader body at the exact key equal to the contract
    ID, while other contract-scoped records use ``contract_id + tag + key``.
    This range intentionally excludes the exact shader key and spans the
    maximum Beam key suffix size derived from ``Shaders::KeyTag``.
    """
    raw_contract_id = parse_contract_id(contract_id)
    return (
        raw_contract_id + b"\x00",
        raw_contract_id + (b"\xff" * CONTRACT_STORAGE_KEY_SUFFIX_MAX_SIZE),
    )


def contract_locked_funds_key_range(
    contract_id: str | bytes | bytearray,
) -> tuple[bytes, bytes]:
    """Return the inclusive Beam key range for one contract's locked funds.

    Beam stores locked funds under the key layout
    ``{contract_id}{tag:LockedAmount}{asset_id_be}``, where ``asset_id_be`` is a
    4-byte big-endian asset ID.
    """
    raw_contract_id = parse_contract_id(contract_id)
    prefix = raw_contract_id + bytes([CONTRACT_LOCKED_AMOUNT_TAG])
    return (
        prefix + (b"\x00" * ASSET_ID_SIZE),
        prefix + (b"\xff" * ASSET_ID_SIZE),
    )


def contract_sid_cid_key_range() -> tuple[bytes, bytes]:
    """Return the inclusive Beam key range for the live ``(sid, cid)`` index.

    Beam stores a synthetic global contract index under the key layout
    ``{00...00}{tag:SidCid}{sid}{cid}`` with the deployment height as a fixed
    big-endian ``Height`` value. Enumerating this range yields the contracts
    currently deployed in the queried node state.
    """
    return (
        _CONTRACT_SID_CID_PREFIX + (b"\x00" * _CONTRACT_SID_CID_PAYLOAD_SIZE),
        _CONTRACT_SID_CID_PREFIX + (b"\xff" * _CONTRACT_SID_CID_PAYLOAD_SIZE),
    )


def parse_contract_sid_cid_entry(key: bytes, value: bytes) -> tuple[bytes, bytes, int]:
    """Decode one Beam synthetic ``(sid, cid) -> create_height`` entry."""
    if len(key) != len(_CONTRACT_SID_CID_PREFIX) + _CONTRACT_SID_CID_PAYLOAD_SIZE:
        raise ValueError(
            "contract SidCid key must be "
            f"{len(_CONTRACT_SID_CID_PREFIX) + _CONTRACT_SID_CID_PAYLOAD_SIZE} bytes, "
            f"got {len(key)}"
        )

    if key[:CONTRACT_ID_SIZE] != b"\x00" * CONTRACT_ID_SIZE:
        raise ValueError("contract SidCid key must start with a zero contract prefix")

    if key[CONTRACT_ID_SIZE] != CONTRACT_SID_CID_TAG:
        raise ValueError(
            "contract SidCid key must use tag "
            f"{CONTRACT_SID_CID_TAG}, got {key[CONTRACT_ID_SIZE]}"
        )

    if len(value) != HEIGHT_SIZE:
        raise ValueError(
            f"contract SidCid value must be {HEIGHT_SIZE} bytes, got {len(value)}"
        )

    shader_start = len(_CONTRACT_SID_CID_PREFIX)
    shader_end = shader_start + SHADER_ID_SIZE
    shader_id = key[shader_start:shader_end]
    contract_id = key[shader_end:]
    height = int.from_bytes(value, byteorder="big", signed=False)

    return shader_id, contract_id, height


def parse_contract_locked_funds_entry(
    key: bytes,
    value: bytes,
) -> tuple[bytes, int, int]:
    """Decode one Beam ``contract_id + LockedAmount + asset_id`` entry."""
    expected_key_size = _CONTRACT_LOCKED_FUNDS_PREFIX_SIZE + ASSET_ID_SIZE
    if len(key) != expected_key_size:
        raise ValueError(
            "contract locked-funds key must be "
            f"{expected_key_size} bytes, got {len(key)}"
        )

    if key[CONTRACT_ID_SIZE] != CONTRACT_LOCKED_AMOUNT_TAG:
        raise ValueError(
            "contract locked-funds key must use tag "
            f"{CONTRACT_LOCKED_AMOUNT_TAG}, got {key[CONTRACT_ID_SIZE]}"
        )

    if len(value) != AMOUNT_BIG_SIZE:
        raise ValueError(
            f"contract locked-funds value must be {AMOUNT_BIG_SIZE} bytes, got {len(value)}"
        )

    contract_id = key[:CONTRACT_ID_SIZE]
    asset_id = int.from_bytes(
        key[_CONTRACT_LOCKED_FUNDS_PREFIX_SIZE:],
        byteorder="big",
        signed=False,
    )
    amount_hi = int.from_bytes(
        value[:AMOUNT_BIG_COMPONENT_SIZE],
        byteorder="big",
        signed=False,
    )
    amount_lo = int.from_bytes(
        value[AMOUNT_BIG_COMPONENT_SIZE:],
        byteorder="big",
        signed=False,
    )

    return contract_id, asset_id, (amount_hi << 64) | amount_lo


def extension_bits(version: int) -> int:
    """Compute the Beam extension capability bitmask."""
    if version < 4:
        return (1 << version) - 1
    return ((version - 4 + 1) << 4) - 1


def utc_now_iso() -> str:
    """Return the current UTC time in ISO-8601 form ending with ``Z``."""
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def is_crawlable_address(address: Address) -> bool:
    """Return whether a crawler-discovered address is usable."""
    host, port = address
    return host != "0.0.0.0" and port > 0


def format_commitment(point: EcPoint) -> str:
    """Format a commitment point as a stable string key."""
    return f"{point.x}:{1 if point.y else 0}"