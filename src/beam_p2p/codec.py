"""Binary encoding and decoding helpers for the Beam wire protocol."""

from __future__ import annotations

import struct
from collections.abc import Sequence

from .protocol import Address, MessageType, PROTO_MAGIC


def _coerce_fixed_bytes(value: bytes | bytearray | str, size: int, label: str) -> bytes:
    if isinstance(value, str):
        try:
            data = bytes.fromhex(value)
        except ValueError as exc:
            raise ValueError(f"{label} must be valid hex") from exc
    else:
        data = bytes(value)

    if len(data) != size:
        raise ValueError(f"{label} must be {size} bytes, got {len(data)}")
    return data


def encode_uint(value: int) -> bytes:
    """Encode a non-negative integer using Beam's compact varuint format."""
    if value < 0:
        raise ValueError(f"value must be >= 0, got {value}")
    if value < 128:
        return bytes([value | 0x80])

    size = 1
    while value >= (1 << (size * 8)):
        size += 1
    return bytes([size]) + value.to_bytes(size, "little")


def decode_uint(
    buf: bytes | bytearray,
    offset: int = 0,
    *,
    off: int | None = None,
) -> tuple[int, int]:
    """Decode a Beam compact varuint from ``buf`` at ``offset``.

    ``off`` is accepted as a compatibility alias for older callers.
    """
    if off is not None:
        offset = off

    size = buf[offset]
    if (size >> 7) & 1:
        return size & 0x7F, 1

    count = size & 0x7F
    return int.from_bytes(buf[offset + 1 : offset + 1 + count], "little"), 1 + count


def encode_height_range(min_height: int, max_height: int) -> bytes:
    """Encode a Beam ``HeightRange`` payload."""
    if min_height < 0:
        raise ValueError(f"minimum height must be >= 0, got {min_height}")
    if max_height < min_height:
        raise ValueError(
            f"maximum height {max_height} must be >= minimum height {min_height}"
        )
    return encode_uint(min_height) + encode_uint(max_height - min_height)


def encode_bool(value: bool) -> bytes:
    """Encode a Beam ``bool`` value."""
    return b"\x01" if value else b"\x00"


def encode_hash32(value: bytes | bytearray | str, *, label: str = "hash") -> bytes:
    """Encode a 32-byte Beam hash-like value."""
    return _coerce_fixed_bytes(value, 32, label)


def encode_fixed_uint(value: int, size: int) -> bytes:
    """Encode a non-negative integer into a fixed-width big-endian buffer."""
    if value < 0:
        raise ValueError(f"value must be >= 0, got {value}")
    try:
        return value.to_bytes(size, "big")
    except OverflowError as exc:
        raise ValueError(f"value does not fit in {size} bytes: {value}") from exc


def encode_point(x: bytes | bytearray | str, y_flag: bool) -> bytes:
    """Encode a Beam ``ECC::Point`` or ``ECC::Point::Storage`` value."""
    return encode_hash32(x, label="point") + encode_bool(y_flag)


def encode_height_pos(height: int, pos: int) -> bytes:
    """Encode a Beam ``HeightPos`` value."""
    return encode_uint(height) + encode_uint(pos)


def encode_system_state_id(height: int, block_hash: bytes | bytearray | str) -> bytes:
    """Encode a Beam ``Block::SystemState::ID`` payload."""
    if height < 0:
        raise ValueError(f"block height must be >= 0, got {height}")
    return encode_uint(height) + encode_hash32(block_hash, label="block hash")


def encode_byte_buffer(value: bytes) -> bytes:
    """Encode a Beam ``ByteBuffer`` payload."""
    return encode_uint(len(value)) + value


def encode_hash_vector(values: Sequence[bytes | bytearray | str]) -> bytes:
    """Encode a vector of 32-byte hashes."""
    return encode_uint(len(values)) + b"".join(
        encode_hash32(value, label="hash vector item") for value in values
    )


def encode_body_payload(*, perishable: bytes, eternal: bytes) -> bytes:
    """Encode a Beam ``Body`` payload from raw body buffers."""
    return encode_byte_buffer(perishable) + encode_byte_buffer(eternal)


def encode_get_body_pack_payload(
    *,
    top_height: int,
    top_hash: bytes,
    flag_perishable: int,
    flag_eternal: int,
    count_extra: int,
    block0: int,
    horizon_lo1: int,
    horizon_hi1: int,
) -> bytes:
    """Encode a Beam ``GetBodyPack`` request payload."""
    return b"".join(
        (
            encode_system_state_id(top_height, top_hash),
            bytes((flag_perishable, flag_eternal)),
            encode_uint(count_extra),
            encode_uint(block0),
            encode_uint(horizon_lo1),
            encode_uint(horizon_hi1),
        )
    )


def encode_get_hdr_payload(height: int, block_hash: bytes | bytearray | str) -> bytes:
    """Encode a Beam ``GetHdr`` request payload."""
    return encode_system_state_id(height, block_hash)


def encode_get_hdr_pack_payload(
    top_height: int,
    top_hash: bytes | bytearray | str,
    count: int,
) -> bytes:
    """Encode a Beam ``GetHdrPack`` request payload."""
    return encode_system_state_id(top_height, top_hash) + encode_uint(count)


def encode_get_body_payload(height: int, block_hash: bytes | bytearray | str) -> bytes:
    """Encode a Beam ``GetBody`` request payload."""
    return encode_system_state_id(height, block_hash)


def encode_get_proof_state_payload(number: int) -> bytes:
    """Encode a Beam ``GetProofState`` request payload."""
    return encode_uint(number)


def encode_get_common_state_payload(
    ids: Sequence[tuple[int, bytes | bytearray | str]],
) -> bytes:
    """Encode a Beam ``GetCommonState`` request payload."""
    return encode_uint(len(ids)) + b"".join(
        encode_system_state_id(number, block_hash) for number, block_hash in ids
    )


def encode_get_proof_kernel_payload(kernel_id: bytes | bytearray | str) -> bytes:
    """Encode a Beam ``GetProofKernel`` request payload."""
    return encode_hash32(kernel_id, label="kernel id")


def encode_get_proof_kernel2_payload(
    kernel_id: bytes | bytearray | str,
    *,
    fetch: bool,
) -> bytes:
    """Encode a Beam ``GetProofKernel2`` request payload."""
    return encode_hash32(kernel_id, label="kernel id") + encode_bool(fetch)


def encode_get_proof_kernel3_payload(
    *,
    height: int,
    pos: int,
    with_proof: bool,
) -> bytes:
    """Encode a Beam ``GetProofKernel3`` request payload."""
    return encode_height_pos(height, pos) + encode_bool(with_proof)


def encode_get_proof_utxo_payload(
    *,
    commitment_x: bytes | bytearray | str,
    y_flag: bool,
    maturity_min: int = 0,
) -> bytes:
    """Encode a Beam ``GetProofUtxo`` request payload."""
    return encode_point(commitment_x, y_flag) + encode_uint(maturity_min)


def encode_get_proof_shielded_outp_payload(
    *,
    serial_pub_x: bytes | bytearray | str,
    y_flag: bool,
) -> bytes:
    """Encode a Beam ``GetProofShieldedOutp`` request payload."""
    return encode_point(serial_pub_x, y_flag)


def encode_get_proof_shielded_inp_payload(
    *,
    spend_pk_x: bytes | bytearray | str,
    y_flag: bool,
) -> bytes:
    """Encode a Beam ``GetProofShieldedInp`` request payload."""
    return encode_point(spend_pk_x, y_flag)


def encode_get_proof_asset_payload(
    *,
    asset_id: int,
    owner: bytes | bytearray | str,
) -> bytes:
    """Encode a Beam ``GetProofAsset`` request payload."""
    return encode_uint(asset_id) + encode_hash32(owner, label="asset owner")


def encode_get_shielded_list_payload(*, id0: int, count: int) -> bytes:
    """Encode a Beam ``GetShieldedList`` request payload."""
    return encode_uint(id0) + encode_uint(count)


def encode_get_proof_chain_work_payload(lower_bound: int | bytes | bytearray | str) -> bytes:
    """Encode a Beam ``GetProofChainWork`` request payload."""
    if isinstance(lower_bound, int):
        return encode_fixed_uint(lower_bound, 32)
    return _coerce_fixed_bytes(lower_bound, 32, "difficulty lower bound")


def encode_get_events_payload(height_min: int) -> bytes:
    """Encode a Beam ``GetEvents`` request payload."""
    return encode_uint(height_min)


def encode_get_state_summary_payload() -> bytes:
    """Encode a Beam ``GetStateSummary`` request payload."""
    return b""


def encode_get_shielded_outputs_at_payload(height: int) -> bytes:
    """Encode a Beam ``GetShieldedOutputsAt`` request payload."""
    return encode_uint(height)


def encode_get_assets_list_at_payload(*, height: int, aid0: int) -> bytes:
    """Encode a Beam ``GetAssetsListAt`` request payload."""
    return encode_uint(height) + encode_uint(aid0)


def encode_contract_vars_enum_payload(
    *,
    key_min: bytes = b"",
    key_max: bytes = b"",
    skip_min: bool = False,
) -> bytes:
    """Encode a Beam ``ContractVarsEnum`` request payload."""
    return encode_byte_buffer(key_min) + encode_byte_buffer(key_max) + encode_bool(skip_min)


def encode_contract_logs_enum_payload(
    *,
    key_min: bytes = b"",
    key_max: bytes = b"",
    pos_min: tuple[int, int] = (0, 0),
    pos_max: tuple[int, int] = (0, 0),
) -> bytes:
    """Encode a Beam ``ContractLogsEnum`` request payload."""
    return b"".join(
        (
            encode_byte_buffer(key_min),
            encode_byte_buffer(key_max),
            encode_height_pos(*pos_min),
            encode_height_pos(*pos_max),
        )
    )


def encode_get_contract_var_payload(key: bytes) -> bytes:
    """Encode a Beam ``GetContractVar`` request payload."""
    return encode_byte_buffer(key)


def encode_get_contract_log_proof_payload(*, height: int, pos: int) -> bytes:
    """Encode a Beam ``GetContractLogProof`` request payload."""
    return encode_height_pos(height, pos)


def encode_optional_hash(value: bytes | bytearray | str | None) -> bytes:
    """Encode an optional 32-byte hash-like value using Beam's pointer layout."""
    if value is None:
        return encode_bool(False)
    return encode_bool(True) + encode_hash32(value, label="optional hash")


def make_header(message_type: int | MessageType, size: int) -> bytes:
    """Build an 8-byte Beam message frame header."""
    header = bytearray(8)
    header[0:3] = PROTO_MAGIC
    header[3] = int(message_type)
    struct.pack_into("<I", header, 4, size)
    return bytes(header)


def parse_header(header: bytes) -> tuple[MessageType, int]:
    """Parse an 8-byte Beam frame header."""
    if header[0:3] != PROTO_MAGIC:
        raise ValueError(f"bad protocol magic: {header[0:3].hex()}")
    return MessageType(header[3]), struct.unpack_from("<I", header, 4)[0]


def encode_transaction_id(tx_id: bytes | bytearray | str) -> bytes:
    """Validate and return a 32-byte transaction identifier."""
    return encode_hash32(tx_id, label="transaction id")


def decode_transaction_id(payload: bytes | bytearray) -> bytes:
    """Validate and return a 32-byte transaction identifier payload."""
    if len(payload) != 32:
        raise ValueError(f"transaction id payload must be 32 bytes, got {len(payload)}")
    return bytes(payload)


def decode_address(packed: int) -> Address:
    """Decode a packed IPv4 address/port pair used in crawler peer records."""
    port = packed & 0xFFFF
    ip = (packed >> 16) & 0xFFFFFFFF
    data = ip.to_bytes(4, "big")
    return f"{data[0]}.{data[1]}.{data[2]}.{data[3]}", port


def decode_peer_info(payload: bytes) -> tuple[bytes, Address] | None:
    """Decode a crawler ``PeerInfo`` payload into ``(peer_id, address)``."""
    if len(payload) < 33:
        return None
    try:
        packed_addr, size = decode_uint(payload, 32)
    except IndexError:
        return None
    if 32 + size > len(payload):
        return None
    return payload[:32], decode_address(packed_addr)