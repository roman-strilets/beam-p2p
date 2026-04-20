"""Kernel deserializers shared by transaction and block decoding."""

from __future__ import annotations

from ..protocol_models import (
    AssetCreateKernel,
    AssetDestroyKernel,
    AssetEmitKernel,
    ContractCreateKernel,
    ContractInvokeKernel,
    EvmInvokeKernel,
    EcPoint,
    Kernel,
    KernelSignature,
    RelativeLock,
    ShieldedInputKernel,
    ShieldedOutputKernel,
    ShieldedSignature,
    ShieldedTxo,
    StdKernel,
)
from .core import BufferReader, DeserializationError, KernelSubtype, decode_utf8, get_kernel_subtype_name
from .proofs import (
    deserialize_asset_proof,
    deserialize_confidential_range_proof,
    deserialize_lelantus_proof,
)


def deserialize_kernel(reader: BufferReader, assume_std: bool) -> Kernel:
    """Deserialize one kernel and dispatch by subtype."""
    subtype_id = 1 if assume_std else reader.read_u8()

    try:
        subtype = KernelSubtype(subtype_id)
    except ValueError as exc:
        raise DeserializationError(f"unsupported kernel subtype: {subtype_id}") from exc

    subtype_name = get_kernel_subtype_name(subtype)

    if subtype == KernelSubtype.STD:
        return deserialize_std_kernel(reader, subtype_name)
    if subtype == KernelSubtype.ASSET_EMIT:
        return deserialize_asset_emit_kernel(reader, subtype_name)
    if subtype == KernelSubtype.SHIELDED_OUTPUT:
        return deserialize_shielded_output_kernel(reader, subtype_name)
    if subtype == KernelSubtype.SHIELDED_INPUT:
        return deserialize_shielded_input_kernel(reader, subtype_name)
    if subtype == KernelSubtype.ASSET_CREATE:
        return deserialize_asset_create_kernel(reader, subtype_name)
    if subtype == KernelSubtype.ASSET_DESTROY:
        return deserialize_asset_destroy_kernel(reader, subtype_name)
    if subtype == KernelSubtype.CONTRACT_CREATE:
        return deserialize_contract_create_kernel(reader, subtype_name)
    if subtype == KernelSubtype.CONTRACT_INVOKE:
        return deserialize_contract_invoke_kernel(reader, subtype_name)
    if subtype == KernelSubtype.EVM_INVOKE:
        return deserialize_evm_invoke_kernel(reader, subtype_name)

    raise DeserializationError(f"kernel subtype not implemented: {subtype_id}")


def deserialize_std_kernel(reader: BufferReader, subtype_name: str) -> StdKernel:
    flags = reader.read_u8()
    commitment = reader.read_point_x(bool(flags & 1))
    signature = KernelSignature(
        nonce_pub=reader.read_point_x(bool(flags & 0x10)),
        k=reader.read_scalar(),
    )
    fee, min_height, max_height = deserialize_fee_height(reader, flags)
    hash_lock = reader.read_hash32() if flags & 0x20 else None
    nested_kernels = deserialize_nested_kernels(reader, flags)
    can_embed = False
    relative_lock = None
    if flags & 0x80:
        flags2 = reader.read_u8()
        can_embed = bool(flags2 & 4)
        if flags2 & 2:
            relative_lock = RelativeLock(
                kernel_id=reader.read_hash32(),
                lock_height=reader.read_var_uint(),
            )
    return StdKernel(
        subtype=subtype_name,
        commitment=commitment,
        signature=signature,
        fee=fee,
        min_height=min_height,
        max_height=max_height,
        nested_kernels=nested_kernels,
        can_embed=can_embed,
        hash_lock=hash_lock,
        relative_lock=relative_lock,
    )


def deserialize_asset_emit_kernel(reader: BufferReader, subtype_name: str) -> AssetEmitKernel:
    base = deserialize_asset_control_base(reader, subtype_name)
    return AssetEmitKernel(**base, asset_id=reader.read_var_uint(), value=reader.read_var_int())


def deserialize_asset_create_kernel(
    reader: BufferReader,
    subtype_name: str,
) -> AssetCreateKernel:
    base = deserialize_asset_control_base(reader, subtype_name)
    metadata = reader.read_byte_buffer()
    return AssetCreateKernel(
        **base,
        metadata_hex=metadata.hex(),
        metadata_text=decode_utf8(metadata),
    )


def deserialize_asset_destroy_kernel(
    reader: BufferReader,
    subtype_name: str,
) -> AssetDestroyKernel:
    base = deserialize_asset_control_base(reader, subtype_name)
    return AssetDestroyKernel(
        **base,
        asset_id=reader.read_var_uint(),
        deposit=reader.read_var_uint(),
    )


def deserialize_shielded_output_kernel(
    reader: BufferReader,
    subtype_name: str,
) -> ShieldedOutputKernel:
    flags = reader.read_var_uint()
    shielded_output = deserialize_shielded_txo(reader)
    fee, min_height, max_height = deserialize_fee_height(reader, flags)
    nested_kernels = deserialize_nested_kernels(reader, flags)
    return ShieldedOutputKernel(
        subtype=subtype_name,
        shielded_output=shielded_output,
        fee=fee,
        min_height=min_height,
        max_height=max_height,
        nested_kernels=nested_kernels,
        can_embed=bool(flags & 0x80),
    )


def deserialize_shielded_input_kernel(
    reader: BufferReader,
    subtype_name: str,
) -> ShieldedInputKernel:
    flags = reader.read_var_uint()
    window_end = reader.read_var_uint()
    spend_proof = deserialize_lelantus_proof(reader)
    fee, min_height, max_height = deserialize_fee_height(reader, flags)
    nested_kernels = deserialize_nested_kernels(reader, flags)
    return ShieldedInputKernel(
        subtype=subtype_name,
        window_end=window_end,
        spend_proof=spend_proof,
        fee=fee,
        min_height=min_height,
        max_height=max_height,
        nested_kernels=nested_kernels,
        can_embed=bool(flags & 0x80),
        asset_proof=deserialize_asset_proof(reader) if flags & 1 else None,
    )


def deserialize_contract_create_kernel(
    reader: BufferReader,
    subtype_name: str,
) -> ContractCreateKernel:
    base = deserialize_contract_control_base(reader, subtype_name)
    return ContractCreateKernel(**base, data_hex=reader.read_byte_buffer().hex())


def deserialize_contract_invoke_kernel(
    reader: BufferReader,
    subtype_name: str,
) -> ContractInvokeKernel:
    base = deserialize_contract_control_base(reader, subtype_name)
    return ContractInvokeKernel(
        **base,
        contract_id=reader.read_hash32(),
        method=reader.read_var_uint(),
    )


def deserialize_evm_invoke_kernel(
    reader: BufferReader,
    subtype_name: str,
) -> EvmInvokeKernel:
    base = deserialize_contract_control_base(reader, subtype_name)
    return EvmInvokeKernel(
        **base,
        from_address=reader.read_fixed_hex(20),
        to=reader.read_fixed_hex(20),
        nonce=reader.read_var_uint(),
        call_value=reader.read_fixed_hex(32),
        subsidy=reader.read_var_int(),
    )


def deserialize_asset_control_base(reader: BufferReader, subtype_name: str) -> dict:
    flags = reader.read_var_uint()
    commitment = reader.read_point_x(bool(flags & 1))
    signature = KernelSignature(
        nonce_pub=reader.read_point_x(bool(flags & 0x10)),
        k=reader.read_scalar(),
    )
    owner = reader.read_hash32()
    fee, min_height, max_height = deserialize_fee_height(reader, flags)
    nested_kernels = deserialize_nested_kernels(reader, flags)
    return {
        "subtype": subtype_name,
        "commitment": commitment,
        "signature": signature,
        "owner": owner,
        "fee": fee,
        "min_height": min_height,
        "max_height": max_height,
        "nested_kernels": nested_kernels,
        "can_embed": bool(flags & 0x20),
    }


def deserialize_contract_control_base(reader: BufferReader, subtype_name: str) -> dict:
    flags = reader.read_var_uint()
    commitment = reader.read_point_x(bool(flags & 1))
    signature = KernelSignature(
        nonce_pub=reader.read_point_x(bool(flags & 0x10)),
        k=reader.read_scalar(),
    )
    args = reader.read_byte_buffer()
    fee, min_height, max_height = deserialize_fee_height(reader, flags)
    nested_kernels = deserialize_nested_kernels(reader, flags)
    return {
        "subtype": subtype_name,
        "commitment": commitment,
        "signature": signature,
        "dependent": bool(flags & 0x80),
        "can_embed": bool(flags & 0x20),
        "args_hex": args.hex(),
        "fee": fee,
        "min_height": min_height,
        "max_height": max_height,
        "nested_kernels": nested_kernels,
    }


def deserialize_fee_height(reader: BufferReader, flags: int) -> tuple[int, int, int | None]:
    fee = reader.read_var_uint() if flags & 2 else 0
    min_height = reader.read_var_uint() if flags & 4 else 0
    max_height = min_height + reader.read_var_uint() if flags & 8 else None
    return fee, min_height, max_height


def deserialize_nested_kernels(reader: BufferReader, flags: int) -> list[Kernel]:
    if not (flags & 0x40):
        return []

    count = reader.read_var_uint()
    mixed = count == 0
    if mixed:
        count = reader.read_var_uint()

    return [deserialize_kernel(reader, assume_std=not mixed) for _ in range(count)]


def deserialize_shielded_txo(reader: BufferReader) -> ShieldedTxo:
    flags = reader.read_var_uint()
    commitment_x = reader.read_fixed_hex(32)
    range_proof = deserialize_confidential_range_proof(reader)
    serial_pub_x = reader.read_fixed_hex(32)
    nonce_pub_point = reader.read_point()
    return ShieldedTxo(
        commitment=EcPoint(commitment_x, bool(flags & 1)),
        range_proof=range_proof,
        serial_pub=EcPoint(serial_pub_x, bool(flags & 2)),
        signature=ShieldedSignature(
            nonce_pub=EcPoint(nonce_pub_point.x, bool(flags & 4)),
            k=[reader.read_scalar(), reader.read_scalar()],
        ),
        asset_proof=deserialize_asset_proof(reader) if flags & 8 else None,
    )