from __future__ import annotations

import pytest

from beam_p2p.utils import (
    CONTRACT_STORAGE_KEY_SUFFIX_MAX_SIZE,
    CONTRACT_SID_CID_TAG,
    contract_shader_key,
    contract_sid_cid_key_range,
    contract_storage_key_range,
    parse_contract_sid_cid_entry,
    parse_contract_id,
)


def test_parse_contract_id_accepts_hex_text() -> None:
    assert parse_contract_id("aa" * 32) == bytes.fromhex("aa" * 32)


def test_parse_contract_id_accepts_hex_text_with_prefix() -> None:
    assert parse_contract_id("0x" + ("bb" * 32)) == bytes.fromhex("bb" * 32)


def test_parse_contract_id_accepts_raw_bytes() -> None:
    raw = bytes.fromhex("cc" * 32)

    assert parse_contract_id(raw) == raw


def test_parse_contract_id_rejects_invalid_hex() -> None:
    with pytest.raises(ValueError, match="invalid contract ID hex"):
        parse_contract_id("zz" * 32)


def test_parse_contract_id_rejects_wrong_length() -> None:
    with pytest.raises(ValueError, match="contract ID must be 32 bytes"):
        parse_contract_id("aa" * 31)


def test_contract_shader_key_matches_exact_contract_id() -> None:
    raw = bytes.fromhex("11" * 32)

    assert contract_shader_key(raw) == raw


def test_contract_storage_key_range_excludes_shader_and_covers_full_suffix() -> None:
    raw = bytes.fromhex("22" * 32)

    key_min, key_max = contract_storage_key_range(raw)

    assert key_min == raw + b"\x00"
    assert len(key_max) == len(raw) + CONTRACT_STORAGE_KEY_SUFFIX_MAX_SIZE
    assert key_max.startswith(raw)
    assert key_max[len(raw) :] == b"\xff" * CONTRACT_STORAGE_KEY_SUFFIX_MAX_SIZE


def test_contract_sid_cid_key_range_covers_live_index() -> None:
    key_min, key_max = contract_sid_cid_key_range()

    prefix = (b"\x00" * 32) + bytes([CONTRACT_SID_CID_TAG])

    assert key_min == prefix + (b"\x00" * 64)
    assert key_max == prefix + (b"\xff" * 64)


def test_parse_contract_sid_cid_entry_decodes_shader_contract_and_height() -> None:
    shader_id = bytes.fromhex("33" * 32)
    contract_id = bytes.fromhex("44" * 32)
    height = 123456789
    key = (b"\x00" * 32) + bytes([CONTRACT_SID_CID_TAG]) + shader_id + contract_id
    value = height.to_bytes(8, byteorder="big", signed=False)

    parsed_shader_id, parsed_contract_id, parsed_height = parse_contract_sid_cid_entry(
        key,
        value,
    )

    assert parsed_shader_id == shader_id
    assert parsed_contract_id == contract_id
    assert parsed_height == height


def test_parse_contract_sid_cid_entry_rejects_non_zero_prefix() -> None:
    key = (b"\x01" + (b"\x00" * 31)) + bytes([CONTRACT_SID_CID_TAG]) + (b"\x00" * 64)
    value = (1).to_bytes(8, byteorder="big", signed=False)

    with pytest.raises(ValueError, match="zero contract prefix"):
        parse_contract_sid_cid_entry(key, value)


def test_parse_contract_sid_cid_entry_rejects_wrong_tag() -> None:
    key = (b"\x00" * 32) + b"\x0f" + (b"\x00" * 64)
    value = (1).to_bytes(8, byteorder="big", signed=False)

    with pytest.raises(ValueError, match="must use tag"):
        parse_contract_sid_cid_entry(key, value)


def test_parse_contract_sid_cid_entry_rejects_wrong_key_length() -> None:
    key = (b"\x00" * 32) + bytes([CONTRACT_SID_CID_TAG]) + (b"\x00" * 63)
    value = (1).to_bytes(8, byteorder="big", signed=False)

    with pytest.raises(ValueError, match="SidCid key must be"):
        parse_contract_sid_cid_entry(key, value)


def test_parse_contract_sid_cid_entry_rejects_wrong_value_length() -> None:
    key = (b"\x00" * 32) + bytes([CONTRACT_SID_CID_TAG]) + (b"\x00" * 64)

    with pytest.raises(ValueError, match="SidCid value must be 8 bytes"):
        parse_contract_sid_cid_entry(key, b"\x00" * 7)