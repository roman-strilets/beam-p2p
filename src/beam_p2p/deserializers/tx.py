"""Transaction, input, and output deserializers."""

from __future__ import annotations

from ..protocol_models import NewTransactionPayload, Transaction, TxCounts, TxInput, TxOutput
from .core import BufferReader, DeserializationError
from .kernels import deserialize_kernel
from .proofs import (
    deserialize_asset_proof,
    deserialize_confidential_range_proof,
    deserialize_public_range_proof,
)


def deserialize_new_transaction_payload(payload: bytes) -> NewTransactionPayload:
    """Deserialize a ``NewTransaction`` payload."""
    reader = BufferReader(payload)

    transaction_present = reader.read_bool()
    transaction = deserialize_transaction(reader) if transaction_present else None

    context_present = reader.read_bool()
    context = reader.read_hash32() if context_present else None
    fluff = reader.read_bool()

    if reader.remaining != 0:
        raise DeserializationError(
            f"{reader.remaining} trailing byte(s) left after NewTransaction parse"
        )

    return NewTransactionPayload(
        transaction_present=transaction_present,
        transaction=transaction,
        context=context,
        fluff=fluff,
    )


def deserialize_transaction(reader: BufferReader) -> Transaction:
    """Deserialize a full transaction payload."""
    input_count = reader.read_big_uint(4)
    inputs = [deserialize_input(reader) for _ in range(input_count)]

    output_count = reader.read_big_uint(4)
    outputs = [deserialize_output(reader) for _ in range(output_count)]

    kernel_count_raw = reader.read_big_uint(4)
    kernels_mixed = bool(kernel_count_raw & (1 << 31))
    kernel_count = kernel_count_raw & 0x7FFFFFFF
    kernels = [
        deserialize_kernel(reader, assume_std=not kernels_mixed)
        for _ in range(kernel_count)
    ]

    return Transaction(
        inputs=inputs,
        outputs=outputs,
        kernels=kernels,
        counts=TxCounts(
            inputs=input_count,
            outputs=output_count,
            kernels=kernel_count,
            kernels_mixed=kernels_mixed,
        ),
        offset=reader.read_scalar(),
    )


def deserialize_input(reader: BufferReader) -> TxInput:
    """Deserialize one transaction input."""
    flags = reader.read_u8()
    return TxInput(commitment=reader.read_point_x(bool(flags & 1)))


def deserialize_output(reader: BufferReader) -> TxOutput:
    """Deserialize one transaction output."""
    flags = reader.read_u8()
    return TxOutput(
        commitment=reader.read_point_x(bool(flags & 1)),
        coinbase=bool(flags & 2),
        confidential_proof=deserialize_confidential_range_proof(reader) if flags & 4 else None,
        public_proof=deserialize_public_range_proof(reader) if flags & 8 else None,
        incubation=reader.read_var_uint() if flags & 0x10 else None,
        asset_proof=deserialize_asset_proof(reader) if flags & 0x20 else None,
        extra_flags=reader.read_u8() if flags & 0x80 else None,
    )
