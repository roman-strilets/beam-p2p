"""Beam query-payload deserializers for proof, asset, state, and contract messages."""

from __future__ import annotations

from ..protocol_models import EcPoint
from ..query_models import (
    AssetFull,
    AssetInfo,
    AssetMetadata,
    AssetsListPage,
    BlockPoW,
    ChainWorkProofResponse,
    ContractLogEntry,
    ContractLogsPage,
    ContractVarEntry,
    ContractVarProof,
    ContractVarsPage,
    HeightPos,
    InputProof,
    InputState,
    MerkleProofNode,
    ProofAssetResponse,
    ProofCommonStateResponse,
    ProofKernel2Response,
    ProofKernelResponse,
    ProofShieldedInpResponse,
    ProofShieldedOutpResponse,
    ProofStateResponse,
    ProofUtxoResponse,
    ShieldedListResponse,
    StateSummary,
    SystemStateElement,
    SystemStateFull,
    SystemStateId,
    SystemStateSequencePrefix,
)
from .core import BufferReader, DeserializationError, decode_utf8
from .kernels import deserialize_kernel


AMOUNT_BIG_SIZE = 16
UINTBIG256_SIZE = 32
POW_INDICES_SIZE = 104
MAX_HEIGHT = (1 << 64) - 1


def _ensure_consumed(reader: BufferReader, label: str) -> None:
    if reader.remaining != 0:
        raise DeserializationError(
            f"{reader.remaining} trailing byte(s) left after {label} parse"
        )


def _read_big_uint(reader: BufferReader, size: int) -> int:
    return int.from_bytes(reader.read_bytes(size), "big")


def _read_vector(reader: BufferReader, loader):
    count = reader.read_var_uint()
    return [loader(reader) for _ in range(count)]


def _read_merkle_proof(reader: BufferReader) -> list[MerkleProofNode]:
    return _read_vector(
        reader,
        lambda inner: MerkleProofNode(on_right=inner.read_bool(), hash=inner.read_hash32()),
    )


def _read_hard_proof(reader: BufferReader) -> list[str]:
    return _read_vector(reader, lambda inner: inner.read_hash32())


def _read_height_pos(reader: BufferReader) -> HeightPos:
    return HeightPos(height=reader.read_var_uint(), pos=reader.read_var_uint())


def _read_pow(reader: BufferReader) -> BlockPoW:
    return BlockPoW(
        indices_hex=reader.read_bytes(POW_INDICES_SIZE).hex(),
        packed_difficulty=reader.read_var_uint(),
        nonce_hex=reader.read_bytes(8).hex(),
    )


def _read_system_state_id(reader: BufferReader) -> SystemStateId:
    return SystemStateId(number=reader.read_var_uint(), hash=reader.read_hash32())


def _read_system_state_prefix(reader: BufferReader) -> SystemStateSequencePrefix:
    return SystemStateSequencePrefix(
        number=reader.read_var_uint(),
        previous_hash=reader.read_hash32(),
        chainwork=_read_big_uint(reader, UINTBIG256_SIZE),
    )


def _read_system_state_element(reader: BufferReader) -> SystemStateElement:
    return SystemStateElement(
        kernels_hash=reader.read_hash32(),
        definition_hash=reader.read_hash32(),
        timestamp=reader.read_var_uint(),
        pow=_read_pow(reader),
    )


def _read_system_state_full(reader: BufferReader) -> SystemStateFull:
    prefix = _read_system_state_prefix(reader)
    element = _read_system_state_element(reader)
    return SystemStateFull(
        number=prefix.number,
        previous_hash=prefix.previous_hash,
        chainwork=prefix.chainwork,
        kernels_hash=element.kernels_hash,
        definition_hash=element.definition_hash,
        timestamp=element.timestamp,
        pow=element.pow,
    )


def _read_input_state(reader: BufferReader) -> InputState:
    return InputState(maturity=reader.read_var_uint(), count=reader.read_var_uint())


def _read_input_proof(reader: BufferReader) -> InputProof:
    return InputProof(state=_read_input_state(reader), proof=_read_merkle_proof(reader))


def _read_asset_metadata(reader: BufferReader) -> AssetMetadata:
    raw = reader.read_byte_buffer()
    return AssetMetadata(value_hex=raw.hex(), text=decode_utf8(raw))


def _read_asset_info(reader: BufferReader) -> AssetInfo:
    owner = reader.read_hash32()
    value = _read_big_uint(reader, AMOUNT_BIG_SIZE)
    lock_height = reader.read_var_uint()
    metadata = _read_asset_metadata(reader)

    deposit: int | None = None
    uses_default_deposit = True
    contract_id: str | None = None

    if lock_height == MAX_HEIGHT:
        flags = reader.read_var_uint()
        lock_height = reader.read_var_uint()

        if flags & 1:
            deposit = reader.read_var_uint()
            uses_default_deposit = False

        if flags & 2:
            contract_id = owner

    return AssetInfo(
        owner=owner,
        contract_id=contract_id,
        value=value,
        lock_height=lock_height,
        deposit=deposit,
        uses_default_deposit=uses_default_deposit,
        metadata=metadata,
    )


def _read_asset_full(reader: BufferReader) -> AssetFull:
    return AssetFull(asset_id=reader.read_var_uint(), info=_read_asset_info(reader))


def deserialize_proof_state_payload(payload: bytes) -> ProofStateResponse:
    """Deserialize a ``ProofState`` payload."""
    reader = BufferReader(payload)
    result = ProofStateResponse(proof=_read_hard_proof(reader))
    _ensure_consumed(reader, "ProofState")
    return result


def deserialize_proof_common_state_payload(payload: bytes) -> ProofCommonStateResponse:
    """Deserialize a ``ProofCommonState`` payload."""
    reader = BufferReader(payload)
    result = ProofCommonStateResponse(
        state_id=_read_system_state_id(reader),
        proof=_read_hard_proof(reader),
    )
    _ensure_consumed(reader, "ProofCommonState")
    return result


def deserialize_proof_kernel_payload(payload: bytes) -> ProofKernelResponse:
    """Deserialize a ``ProofKernel`` payload."""
    reader = BufferReader(payload)
    result = ProofKernelResponse(
        inner_proof=_read_merkle_proof(reader),
        state=_read_system_state_full(reader),
        outer_proof=_read_hard_proof(reader),
    )
    _ensure_consumed(reader, "ProofKernel")
    return result


def deserialize_proof_kernel2_payload(payload: bytes) -> ProofKernel2Response:
    """Deserialize a ``ProofKernel2`` payload."""
    reader = BufferReader(payload)
    proof = _read_merkle_proof(reader)
    height = reader.read_var_uint()

    if reader.peek_u8() == 0:
        reader.read_u8()
        kernel = None
    else:
        kernel = deserialize_kernel(reader, assume_std=False)

    result = ProofKernel2Response(proof=proof, height=height, kernel=kernel)
    _ensure_consumed(reader, "ProofKernel2")
    return result


def deserialize_proof_utxo_payload(payload: bytes) -> ProofUtxoResponse:
    """Deserialize a ``ProofUtxo`` payload."""
    reader = BufferReader(payload)
    result = ProofUtxoResponse(proofs=_read_vector(reader, _read_input_proof))
    _ensure_consumed(reader, "ProofUtxo")
    return result


def deserialize_proof_shielded_outp_payload(payload: bytes) -> ProofShieldedOutpResponse:
    """Deserialize a ``ProofShieldedOutp`` payload."""
    reader = BufferReader(payload)
    result = ProofShieldedOutpResponse(
        commitment=reader.read_point(),
        txo_id=reader.read_var_uint(),
        height=reader.read_var_uint(),
        proof=_read_merkle_proof(reader),
    )
    _ensure_consumed(reader, "ProofShieldedOutp")
    return result


def deserialize_proof_shielded_inp_payload(payload: bytes) -> ProofShieldedInpResponse:
    """Deserialize a ``ProofShieldedInp`` payload."""
    reader = BufferReader(payload)
    result = ProofShieldedInpResponse(
        height=reader.read_var_uint(),
        proof=_read_merkle_proof(reader),
    )
    _ensure_consumed(reader, "ProofShieldedInp")
    return result


def deserialize_proof_asset_payload(payload: bytes) -> ProofAssetResponse:
    """Deserialize a ``ProofAsset`` payload."""
    reader = BufferReader(payload)
    result = ProofAssetResponse(info=_read_asset_full(reader), proof=_read_merkle_proof(reader))
    _ensure_consumed(reader, "ProofAsset")
    return result


def deserialize_shielded_list_payload(payload: bytes) -> ShieldedListResponse:
    """Deserialize a ``ShieldedList`` payload."""
    reader = BufferReader(payload)
    items = _read_vector(reader, lambda inner: inner.read_point())
    result = ShieldedListResponse(items=items, state_hash=reader.read_hash32())
    _ensure_consumed(reader, "ShieldedList")
    return result


def deserialize_proof_chain_work_payload(payload: bytes) -> ChainWorkProofResponse:
    """Deserialize a ``ProofChainWork`` payload."""
    reader = BufferReader(payload)
    heading_prefix = _read_system_state_prefix(reader)
    heading_elements = _read_vector(reader, _read_system_state_element)
    arbitrary_states = _read_vector(reader, _read_system_state_full)
    proof = _read_hard_proof(reader)
    root_live = reader.read_hash32()
    lower_bound = _read_big_uint(reader, UINTBIG256_SIZE)

    result = ChainWorkProofResponse(
        heading_prefix=heading_prefix,
        heading_elements=heading_elements,
        arbitrary_states=arbitrary_states,
        proof=proof,
        root_live=root_live,
        lower_bound=lower_bound,
    )
    _ensure_consumed(reader, "ProofChainWork")
    return result


def deserialize_state_summary_payload(payload: bytes) -> StateSummary:
    """Deserialize a ``StateSummary`` payload."""
    reader = BufferReader(payload)
    result = StateSummary(
        txo_lo=reader.read_var_uint(),
        kernels=reader.read_var_uint(),
        txos=reader.read_var_uint(),
        utxos=reader.read_var_uint(),
        shielded_outs=reader.read_var_uint(),
        shielded_ins=reader.read_var_uint(),
        assets_max=reader.read_var_uint(),
        assets_active=reader.read_var_uint(),
    )
    _ensure_consumed(reader, "StateSummary")
    return result


def deserialize_shielded_outputs_at_payload(payload: bytes) -> int:
    """Deserialize a ``ShieldedOutputsAt`` payload."""
    reader = BufferReader(payload)
    result = reader.read_var_uint()
    _ensure_consumed(reader, "ShieldedOutputsAt")
    return result


def deserialize_assets_list_at_payload(payload: bytes) -> AssetsListPage:
    """Deserialize an ``AssetsListAt`` payload."""
    reader = BufferReader(payload)
    assets = _read_vector(reader, _read_asset_full)
    more = reader.read_bool()
    result = AssetsListPage(
        assets=assets,
        more=more,
        next_asset_id=(assets[-1].asset_id + 1) if assets else None,
    )
    _ensure_consumed(reader, "AssetsListAt")
    return result


def _parse_contract_var_entries(raw: bytes) -> list[ContractVarEntry]:
    reader = BufferReader(raw)
    entries: list[ContractVarEntry] = []

    while reader.remaining:
        key_size = reader.read_var_uint()
        value_size = reader.read_var_uint()
        entries.append(
            ContractVarEntry(
                key=reader.read_bytes(key_size),
                value=reader.read_bytes(value_size),
            )
        )

    return entries


def deserialize_contract_vars_payload(payload: bytes) -> ContractVarsPage:
    """Deserialize a ``ContractVars`` payload."""
    reader = BufferReader(payload)
    entries = _parse_contract_var_entries(reader.read_byte_buffer())
    result = ContractVarsPage(entries=entries, more=reader.read_bool())
    _ensure_consumed(reader, "ContractVars")
    return result


def _parse_contract_log_entries(raw: bytes) -> list[ContractLogEntry]:
    reader = BufferReader(raw)
    entries: list[ContractLogEntry] = []
    current = HeightPos(0, 0)

    while reader.remaining:
        delta = _read_height_pos(reader)
        key_size = reader.read_var_uint()
        value_size = reader.read_var_uint()

        height = current.height + delta.height
        base_pos = 0 if delta.height else current.pos
        pos = base_pos + delta.pos

        current = HeightPos(height=height, pos=pos)
        entries.append(
            ContractLogEntry(
                position=current,
                key=reader.read_bytes(key_size),
                value=reader.read_bytes(value_size),
            )
        )

    return entries


def deserialize_contract_logs_payload(payload: bytes) -> ContractLogsPage:
    """Deserialize a ``ContractLogs`` payload."""
    reader = BufferReader(payload)
    entries = _parse_contract_log_entries(reader.read_byte_buffer())
    result = ContractLogsPage(entries=entries, more=reader.read_bool())
    _ensure_consumed(reader, "ContractLogs")
    return result


def deserialize_contract_var_payload(payload: bytes) -> ContractVarProof:
    """Deserialize a ``ContractVar`` payload."""
    reader = BufferReader(payload)
    result = ContractVarProof(value=reader.read_byte_buffer(), proof=_read_merkle_proof(reader))
    _ensure_consumed(reader, "ContractVar")
    return result


def deserialize_contract_log_proof_payload(payload: bytes) -> list[MerkleProofNode]:
    """Deserialize a ``ContractLogProof`` payload."""
    reader = BufferReader(payload)
    result = _read_merkle_proof(reader)
    _ensure_consumed(reader, "ContractLogProof")
    return result


def deserialize_events_payload(payload: bytes) -> bytes:
    """Deserialize an ``Events`` payload."""
    reader = BufferReader(payload)
    result = reader.read_byte_buffer()
    _ensure_consumed(reader, "Events")
    return result