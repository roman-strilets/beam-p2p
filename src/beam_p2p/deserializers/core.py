"""Core reader and helper utilities for Beam payload deserializers."""

from __future__ import annotations

from enum import IntEnum

from ..codec import decode_uint
from ..protocol_models import EcPoint


class KernelSubtype(IntEnum):
    """Beam protocol kernel subtype codes."""

    STD = 1
    ASSET_EMIT = 2
    SHIELDED_OUTPUT = 3
    SHIELDED_INPUT = 4
    ASSET_CREATE = 5
    ASSET_DESTROY = 6
    CONTRACT_CREATE = 7
    CONTRACT_INVOKE = 8
    EVM_INVOKE = 9


_KERNEL_SUBTYPE_NAMES = {
    KernelSubtype.STD: "Std",
    KernelSubtype.ASSET_EMIT: "AssetEmit",
    KernelSubtype.SHIELDED_OUTPUT: "ShieldedOutput",
    KernelSubtype.SHIELDED_INPUT: "ShieldedInput",
    KernelSubtype.ASSET_CREATE: "AssetCreate",
    KernelSubtype.ASSET_DESTROY: "AssetDestroy",
    KernelSubtype.CONTRACT_CREATE: "ContractCreate",
    KernelSubtype.CONTRACT_INVOKE: "ContractInvoke",
    KernelSubtype.EVM_INVOKE: "EvmInvoke",
}


def get_kernel_subtype_name(subtype: KernelSubtype) -> str:
    """Return a human-readable name for a kernel subtype."""
    return _KERNEL_SUBTYPE_NAMES.get(subtype, f"Unknown({subtype})")


class DeserializationError(ValueError):
    """Raised when a Beam payload cannot be parsed."""


class BufferReader:
    """Cursor-based reader over an immutable bytes buffer."""

    def __init__(self, data: bytes):
        self._data = data
        self._offset = 0

    @property
    def offset(self) -> int:
        return self._offset

    @property
    def remaining(self) -> int:
        return len(self._data) - self._offset

    def read_bytes(self, size: int) -> bytes:
        if size < 0:
            raise DeserializationError(f"negative read size: {size}")
        end = self._offset + size
        if end > len(self._data):
            raise DeserializationError(
                f"unexpected end of buffer at offset {self._offset}, need {size} bytes"
            )
        chunk = self._data[self._offset : end]
        self._offset = end
        return chunk

    def read_u8(self) -> int:
        return self.read_bytes(1)[0]

    def peek_u8(self) -> int:
        if self.remaining < 1:
            raise DeserializationError(
                f"unexpected end of buffer at offset {self._offset}, need 1 byte"
            )
        return self._data[self._offset]

    def read_bool(self) -> bool:
        return self.read_u8() != 0

    def read_var_uint(self) -> int:
        try:
            value, size = decode_uint(self._data, self._offset)
        except IndexError as exc:
            raise DeserializationError(
                f"unexpected end of compact unsigned integer at offset {self._offset}"
            ) from exc

        self._offset += size
        return value

    def read_var_int(self) -> int:
        head = self.read_u8()
        negative = (head >> 7) & 1
        one_byte = (head >> 6) & 1
        value = head & 0x3F

        if one_byte:
            return -value if negative else value

        raw = int.from_bytes(self.read_bytes(value), "little") if value else 0
        return -raw if negative else raw

    def read_big_uint(self, size: int) -> int:
        return int.from_bytes(self.read_bytes(size), "big")

    def read_fixed_hex(self, size: int) -> str:
        return self.read_bytes(size).hex()

    def read_scalar(self) -> str:
        return self.read_fixed_hex(32)

    def read_hash32(self) -> str:
        return self.read_fixed_hex(32)

    def read_point(self) -> EcPoint:
        return EcPoint(x=self.read_fixed_hex(32), y=self.read_bool())

    def read_point_x(self, y_flag: bool) -> EcPoint:
        return EcPoint(x=self.read_fixed_hex(32), y=y_flag)

    def read_byte_buffer(self) -> bytes:
        size = self.read_var_uint()
        return self.read_bytes(size)

    def slice(self, start: int, end: int) -> bytes:
        return self._data[start:end]


def decode_msb_bits(data: bytes, bit_count: int) -> list[bool]:
    """Decode bits from ``data`` using most-significant-bit ordering."""
    bits: list[bool] = []
    for index in range(bit_count):
        byte = data[index // 8]
        bits.append(bool((byte >> (7 - (index % 8))) & 1))
    return bits


def decode_lsb_bits(data: bytes, bit_count: int) -> list[bool]:
    """Decode bits from ``data`` using least-significant-bit ordering."""
    bits: list[bool] = []
    for index in range(bit_count):
        byte = data[index // 8]
        bits.append(bool((byte >> (index % 8)) & 1))
    return bits


def decode_utf8(data: bytes) -> str | None:
    """Decode ``data`` as UTF-8, returning ``None`` on failure."""
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        return None
