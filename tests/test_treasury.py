from beam_p2p.codec import encode_byte_buffer, encode_uint
from beam_p2p.treasury import (
    deserialize_treasury_data,
    deserialize_treasury_payload,
    treasury_amount_at_height,
)


def _treasury_output(*, incubation: int | None = None, coinbase: bool = True) -> bytes:
    flags = 0
    if coinbase:
        flags |= 0x02
    if incubation is not None:
        flags |= 0x10
    payload = bytearray((flags,))
    payload.extend(b"\x11" * 32)
    if incubation is not None:
        payload.extend(encode_uint(incubation))
    return bytes(payload)


def _treasury_group(*, outputs: list[bytes], value_groth: int, asset_id: int = 0) -> bytes:
    payload = bytearray()
    payload.extend((0).to_bytes(4, "big"))
    payload.extend(len(outputs).to_bytes(4, "big"))
    for output in outputs:
        payload.extend(output)
    payload.extend((0).to_bytes(4, "big"))
    payload.extend(b"\x00" * 32)
    if asset_id:
        payload.extend(b"\xff" * 16)
        payload.extend(value_groth.to_bytes(16, "big"))
        payload.extend(asset_id.to_bytes(4, "big"))
    else:
        payload.extend(value_groth.to_bytes(16, "big"))
    return bytes(payload)


def _treasury_payload(*, custom_message: str, groups: list[bytes]) -> bytes:
    return (
        encode_byte_buffer(custom_message.encode("utf-8"))
        + encode_uint(len(groups))
        + b"".join(groups)
    )


def test_deserialize_treasury_data_reads_group_values_and_release_heights() -> None:
    payload = _treasury_payload(
        custom_message="beam",
        groups=[
            _treasury_group(
                outputs=[_treasury_output(incubation=45)],
                value_groth=123,
            )
        ],
    )

    data = deserialize_treasury_data(payload)
    outputs = deserialize_treasury_payload(payload)

    assert data.custom_message == "beam"
    assert len(data.groups) == 1
    assert data.groups[0].value_groth == 123
    assert data.groups[0].asset_id == 0
    assert data.groups[0].release_height == 45
    assert len(data.groups[0].outputs) == 1
    assert len(outputs) == 1
    assert outputs[0].incubation == 45


def test_deserialize_treasury_data_supports_asset_marker_and_contract_allocation() -> None:
    payload = _treasury_payload(
        custom_message="assets",
        groups=[
            _treasury_group(outputs=[], value_groth=456, asset_id=7),
        ],
    )

    data = deserialize_treasury_data(payload)

    assert len(data.groups) == 1
    assert data.groups[0].value_groth == 456
    assert data.groups[0].asset_id == 7
    assert data.groups[0].release_height == 0
    assert data.groups[0].outputs == ()


def test_treasury_amount_at_height_filters_by_asset_and_release_height() -> None:
    payload = _treasury_payload(
        custom_message="mix",
        groups=[
            _treasury_group(outputs=[_treasury_output(incubation=10)], value_groth=100),
            _treasury_group(outputs=[_treasury_output(incubation=20)], value_groth=200),
            _treasury_group(outputs=[_treasury_output(incubation=15)], value_groth=300, asset_id=7),
        ],
    )

    data = deserialize_treasury_data(payload)

    assert treasury_amount_at_height(data, 9) == 0
    assert treasury_amount_at_height(data, 10) == 100
    assert treasury_amount_at_height(data, 19) == 100
    assert treasury_amount_at_height(data, 20) == 300
    assert treasury_amount_at_height(data, 20, asset_id=7) == 300
