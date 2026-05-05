# Unit Test Plan for `beam_p2p/deserializers/core.py`

## Overview
The `core.py` module provides essential deserialization utilities, including the `BufferReader` class, bit-decoding functions, and UTF-8 decoding. The goal of these tests is to ensure robustness, correctness, and proper error handling during the parsing of Beam protocol payloads.

## Test Targets

### 1. `KernelSubtype` and `get_kernel_subtype_name`
- **Test cases:**
    - Verify `get_kernel_subtype_name` returns the correct string for all `KernelSubtype` enum members.
    - Verify `get_kernel_subtype_name` returns `Unknown(<value>)` for a value not defined in the enum.

### 2. `BufferReader`
`BufferReader` is a cursor-based reader. Tests should verify that the offset advances correctly and that it handles buffer boundaries strictly.

#### A. Basic Properties
- **Test cases:**
    - Initial state: `offset` is 0 and `remaining` equals the length of the input data.
    - After reading: `offset` increases by the number of bytes read, and `remaining` decreases accordingly.

#### B. `read_bytes(size)`
- **Test cases:**
    - Read a valid number of bytes.
    - Read 0 bytes (should return empty bytes and not move offset).
    - Read more bytes than available (should raise `DeserializationError`).
    - Read a negative size (should raise `DeserializationError`).

#### C. `read_u8()`
- **Test cases:**
    - Read a single byte successfully.
    - Read from an empty buffer or at the end of the buffer (should raise `DeserializationError`).

#### D. `peek_u8()`
- **Test cases:**
    - Peek a byte and verify the value is correct and `offset` remains unchanged.
    - Peek from an empty buffer or at the end of the buffer (should raise `DeserializationError`).

#### E. `read_bool()`
- **Test cases:**
    - `0x00` -> `False`.
    - `0x01` -> `True`.
    - `0xFF` -> `True`.
    - End of buffer (should raise `DeserializationError`).

#### F. `read_var_uint()`
- **Test cases:**
    - Small value (single byte).
    - Larger value (multiple bytes).
    - Unexpected end of buffer while decoding the variable integer (should raise `DeserializationError`).

#### G. `read_var_int()`
- **Test cases:**
    - Positive small value (1 byte).
    - Positive large value (multi-byte).
    - Negative small value (1 byte).
    - Negative large value (multi-byte).
    - Zero value.
    - Unexpected end of buffer (should raise `DeserializationError`).

#### H. `read_big_uint(size)`
- **Test cases:**
    - Read 1, 2, 4, and 8 byte big-endian integers.
    - Unexpected end of buffer (should raise `DeserializationError`).

#### I. `read_fixed_hex(size)`
- **Test cases:**
    - Read specified size and verify the resulting hex string.
    - Unexpected end of buffer (should raise `DeserializationError`).

#### J. Specialized Readers (`read_scalar`, `read_hash32`, `read_point`, `read_point_x`)
- **Test cases:**
    - `read_scalar`: Verify it reads exactly 32 bytes and returns hex.
    - `read_hash32`: Verify it reads exactly 32 bytes and returns hex.
    - `read_point`: Verify it reads 32 bytes (X) and 1 byte (Y flag), returning an `EcPoint`.
    - `read_point_x`: Verify it reads 32 bytes (X) and uses the provided `y_flag`.

#### K. `read_byte_buffer()`
- **Test cases:**
    - Read a valid length (var_uint) followed by that many bytes.
    - Read a buffer with size 0.
    - Unexpected end of buffer during size read.
    - Unexpected end of buffer during data read (buffer truncated).

#### L. `slice(start, end)`
- **Test cases:**
    - Slice a valid range of the original buffer.
    - Slice out of bounds (verify Python's default slicing behavior).

### 3. Bit Decoding Utilities

#### A. `decode_msb_bits(data, bit_count)`
- **Test cases:**
    - Single byte, various bit patterns.
    - Multiple bytes, verify MSB order.
    - `bit_count` that is not a multiple of 8.

#### B. `decode_lsb_bits(data, bit_count)`
- **Test cases:**
    - Single byte, various bit patterns.
    - Multiple bytes, verify LSB order.
    - `bit_count` that is not a multiple of 8.

### 4. `decode_utf8(data)`
- **Test cases:**
    - Valid UTF-8 string.
    - Invalid UTF-8 byte sequence (should return `None`).
    - Empty byte string.

## Error Handling Summary
Ensure that `DeserializationError` is raised in all "unexpected end of buffer" or "invalid input size" scenarios to maintain consistency across the deserialization layer.