import pytest

from beam_p2p.deserializers.core import (
    BufferReader,
    DeserializationError,
    KernelSubtype,
    decode_lsb_bits,
    decode_msb_bits,
    decode_utf8,
    get_kernel_subtype_name,
)
from beam_p2p.protocol_models import EcPoint


def test_kernel_subtype_names():
    # Verify all defined subtypes have their expected names
    assert get_kernel_subtype_name(KernelSubtype.STD) == "Std"
    assert get_kernel_subtype_name(KernelSubtype.ASSET_EMIT) == "AssetEmit"
    assert get_kernel_subtype_name(KernelSubtype.SHIELDED_OUTPUT) == "ShieldedOutput"
    assert get_kernel_subtype_name(KernelSubtype.SHIELDED_INPUT) == "ShieldedInput"
    assert get_kernel_subtype_name(KernelSubtype.ASSET_CREATE) == "AssetCreate"
    assert get_kernel_subtype_name(KernelSubtype.ASSET_DESTROY) == "AssetDestroy"
    assert get_kernel_subtype_name(KernelSubtype.CONTRACT_CREATE) == "ContractCreate"
    assert get_kernel_subtype_name(KernelSubtype.CONTRACT_INVOKE) == "ContractInvoke"
    assert get_kernel_subtype_name(KernelSubtype.EVM_INVOKE) == "EvmInvoke"

    # Verify unknown subtype handling
    assert get_kernel_subtype_name(99) == "Unknown(99)"


class TestBufferReader:
    def test_init_and_properties(self):
        data = b"\x01\x02\x03\x04"
        reader = BufferReader(data)
        assert reader.offset == 0
        assert reader.remaining == 4

        reader.read_u8()
        assert reader.offset == 1
        assert reader.remaining == 3

    def test_read_bytes(self):
        data = b"\x01\x02\x03\x04"
        reader = BufferReader(data)

        # Happy path
        assert reader.read_bytes(2) == b"\x01\x02"
        assert reader.offset == 2

        # Read 0 bytes
        assert reader.read_bytes(0) == b""
        assert reader.offset == 2

        # Read exactly remaining
        assert reader.read_bytes(2) == b"\x03\x04"
        assert reader.offset == 4

        # Unexpected end of buffer
        with pytest.raises(DeserializationError, match="unexpected end of buffer"):
            reader.read_bytes(1)

        # Negative read size
        reader2 = BufferReader(data)
        with pytest.raises(DeserializationError, match="negative read size"):
            reader2.read_bytes(-1)

    def test_read_u8(self):
        reader = BufferReader(b"\x05\x0a")
        assert reader.read_u8() == 5
        assert reader.read_u8() == 10
        with pytest.raises(DeserializationError):
            reader.read_u8()

    def test_peek_u8(self):
        reader = BufferReader(b"\x05\x0a")
        assert reader.peek_u8() == 5
        assert reader.offset == 0  # Offset should not move
        assert reader.read_u8() == 5
        assert reader.peek_u8() == 10
        assert reader.read_u8() == 10
        with pytest.raises(DeserializationError):
            reader.peek_u8()

    def test_read_bool(self):
        reader = BufferReader(b"\x00\x01\xff")
        assert reader.read_bool() is False
        assert reader.read_bool() is True
        assert reader.read_bool() is True

    def test_read_var_uint(self):
        # Beam varuint: MSB=1 means 1-byte value (0-127). MSB=0 means first byte is count of bytes following.

        # Value 5: 5 | 0x80 = 0x85
        reader = BufferReader(b"\x85")
        assert reader.read_var_uint() == 5

        # Value 129: 1 byte follows (0x01), value is 0x81 (129)
        reader = BufferReader(b"\x01\x81")
        assert reader.read_var_uint() == 129

        # Truncated: MSB=0 means 1 byte follows, but buffer ends
        reader = BufferReader(b"\x01")
        with pytest.raises(
            DeserializationError, match="unexpected end of compact unsigned integer"
        ):
            reader.read_var_uint()

    def test_read_var_int(self):
        # Positive small (one_byte=1)
        # head = 0x41 (0100 0001) -> negative=0, one_byte=1, value=1
        reader = BufferReader(b"\x41")
        assert reader.read_var_int() == 1

        # Negative small (one_byte=1)
        # head = 0xC1 (1100 0001) -> negative=1, one_byte=1, value=1
        reader = BufferReader(b"\xc1")
        assert reader.read_var_int() == -1

        # Positive large (one_byte=0)
        # head = 0x01 (0000 0001) -> negative=0, one_byte=0, value=1. read_bytes(1)
        reader = BufferReader(b"\x01\x05")
        assert reader.read_var_int() == 5

        # Negative large (one_byte=0)
        # head = 0x81 (1000 0001) -> negative=1, one_byte=0, value=1. read_bytes(1)
        reader = BufferReader(b"\x81\x05")
        assert reader.read_var_int() == -5

        # Zero
        reader = BufferReader(b"\x00")
        assert reader.read_var_int() == 0

        # Truncated
        reader = BufferReader(b"\x01")  # indicates 1 byte follows, but none do
        with pytest.raises(DeserializationError):
            reader.read_var_int()

    def test_read_big_uint(self):
        reader = BufferReader(b"\x00\x01\x00\x00\x00\x01")
        assert reader.read_big_uint(2) == 1
        assert reader.read_big_uint(4) == 1
        with pytest.raises(DeserializationError):
            reader.read_big_uint(1)

    def test_read_fixed_hex(self):
        reader = BufferReader(b"\x01\x02\xab\xcd")
        assert reader.read_fixed_hex(2) == "0102"
        assert reader.read_fixed_hex(2) == "abcd"

    def test_specialized_readers(self):
        # Setup 32 bytes of dummy data
        scalar_bytes = b"\x01" * 32
        data = scalar_bytes + b"\x01" + scalar_bytes + b"\x00"
        reader = BufferReader(data)

        # read_scalar / read_hash32
        assert reader.read_scalar() == scalar_bytes.hex()
        # read_point (reads scalar + bool)
        point = reader.read_point()
        assert isinstance(point, EcPoint)
        assert point.x == scalar_bytes.hex()
        assert point.y is True

        # reset and test others
        reader = BufferReader(data)
        assert reader.read_hash32() == scalar_bytes.hex()
        # read_point_x
        point_x = reader.read_point_x(y_flag=False)
        assert point_x.x == scalar_bytes.hex()
        assert point_x.y is False

    def test_read_byte_buffer(self):
        # var_uint 3 (0x83) then 3 bytes
        data = b"\x83\xaa\xbb\xcc"
        reader = BufferReader(data)
        assert reader.read_byte_buffer() == b"\xaa\xbb\xcc"

        # size 0
        reader = BufferReader(b"\x00")
        assert reader.read_byte_buffer() == b""

        # truncated size
        reader = BufferReader(b"\x81")
        with pytest.raises(DeserializationError):
            reader.read_byte_buffer()

        # truncated data
        reader = BufferReader(b"\x05\x01\x02")
        with pytest.raises(DeserializationError):
            reader.read_byte_buffer()

    def test_slice(self):
        reader = BufferReader(b"\x01\x02\x03\x04\x05")
        assert reader.slice(1, 4) == b"\x02\x03\x04"
        assert reader.slice(0, 10) == b"\x01\x02\x03\x04\x05"


def test_decode_msb_bits():
    # 0x80 = 1000 0000
    assert decode_msb_bits(b"\x80", 1) == [True]
    assert decode_msb_bits(b"\x80", 8) == [
        True,
        False,
        False,
        False,
        False,
        False,
        False,
        False,
    ]
    # 0x01 = 0000 0001
    assert decode_msb_bits(b"\x01", 8) == [
        False,
        False,
        False,
        False,
        False,
        False,
        False,
        True,
    ]
    # Multi-byte: 0x80 0x01 = 1000 0000 0000 0001
    # 9th bit is MSB of 0x01, which is 0
    assert decode_msb_bits(b"\x80\x01", 9) == [
        True,
        False,
        False,
        False,
        False,
        False,
        False,
        False,
        False,
    ]


def test_decode_lsb_bits():
    # 0x01 = 0000 0001
    assert decode_lsb_bits(b"\x01", 1) == [True]
    assert decode_lsb_bits(b"\x01", 8) == [
        True,
        False,
        False,
        False,
        False,
        False,
        False,
        False,
    ]
    # 0x80 = 1000 0000
    assert decode_lsb_bits(b"\x80", 8) == [
        False,
        False,
        False,
        False,
        False,
        False,
        False,
        True,
    ]
    # Multi-byte: 0x01 0x80 = 0000 0001 1000 0000
    # Byte 0: 1,0,0,0,0,0,0,0
    # Byte 1: 0 (LSB of 0x80 is 0)
    assert decode_lsb_bits(b"\x01\x80", 9) == [
        True,
        False,
        False,
        False,
        False,
        False,
        False,
        False,
        False,
    ]


def test_decode_utf8():
    assert decode_utf8(b"hello") == "hello"
    assert decode_utf8(b"") == ""
    # Invalid UTF-8
    assert decode_utf8(b"\xff\xfe\xfd") is None
