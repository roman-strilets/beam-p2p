"""Typed models for Beam proof, state, asset, and contract query responses."""

from __future__ import annotations

from dataclasses import dataclass

from .protocol_models import EcPoint, Kernel


@dataclass(frozen=True)
class HeightPos:
    """Beam ``HeightPos`` value."""

    height: int
    pos: int


@dataclass(frozen=True)
class MerkleProofNode:
    """One Beam Merkle proof sibling node."""

    on_right: bool
    hash: str


@dataclass(frozen=True)
class BlockPoW:
    """Beam block proof-of-work payload."""

    indices_hex: str
    packed_difficulty: int
    nonce_hex: str


@dataclass(frozen=True)
class SystemStateId:
    """Beam ``Block::SystemState::ID`` value."""

    number: int
    hash: str


@dataclass(frozen=True)
class SystemStateSequencePrefix:
    """Beam block-state prefix shared by proof and chainwork payloads."""

    number: int
    previous_hash: str
    chainwork: int


@dataclass(frozen=True)
class SystemStateElement:
    """Beam block-state element payload."""

    kernels_hash: str
    definition_hash: str
    timestamp: int
    pow: BlockPoW


@dataclass(frozen=True)
class SystemStateFull:
    """Full Beam block-state description."""

    number: int
    previous_hash: str
    chainwork: int
    kernels_hash: str
    definition_hash: str
    timestamp: int
    pow: BlockPoW


@dataclass(frozen=True)
class InputState:
    """Beam UTXO state recorded in an input proof."""

    maturity: int
    count: int


@dataclass(frozen=True)
class InputProof:
    """Beam UTXO inclusion proof."""

    state: InputState
    proof: list[MerkleProofNode]


@dataclass(frozen=True)
class AssetMetadata:
    """Opaque Beam asset metadata blob."""

    value_hex: str
    text: str | None


@dataclass(frozen=True)
class AssetInfo:
    """Beam asset listing payload."""

    owner: str
    contract_id: str | None
    value: int
    lock_height: int
    deposit: int | None
    uses_default_deposit: bool
    metadata: AssetMetadata


@dataclass(frozen=True)
class AssetFull:
    """Beam asset listing entry."""

    asset_id: int
    info: AssetInfo


@dataclass(frozen=True)
class ProofStateResponse:
    """Response to ``GetProofState``."""

    proof: list[str]


@dataclass(frozen=True)
class ProofCommonStateResponse:
    """Response to ``GetCommonState``."""

    state_id: SystemStateId
    proof: list[str]


@dataclass(frozen=True)
class ProofKernelResponse:
    """Legacy long kernel proof response."""

    inner_proof: list[MerkleProofNode]
    state: SystemStateFull
    outer_proof: list[str]


@dataclass(frozen=True)
class ProofKernel2Response:
    """Response to ``GetProofKernel2`` and ``GetProofKernel3``."""

    proof: list[MerkleProofNode]
    height: int
    kernel: Kernel | None


@dataclass(frozen=True)
class ProofUtxoResponse:
    """Response to ``GetProofUtxo``."""

    proofs: list[InputProof]


@dataclass(frozen=True)
class ProofShieldedOutpResponse:
    """Response to ``GetProofShieldedOutp``."""

    commitment: EcPoint
    txo_id: int
    height: int
    proof: list[MerkleProofNode]


@dataclass(frozen=True)
class ProofShieldedInpResponse:
    """Response to ``GetProofShieldedInp``."""

    height: int
    proof: list[MerkleProofNode]


@dataclass(frozen=True)
class ProofAssetResponse:
    """Response to ``GetProofAsset``."""

    info: AssetFull
    proof: list[MerkleProofNode]


@dataclass(frozen=True)
class ShieldedListResponse:
    """Response to ``GetShieldedList``."""

    items: list[EcPoint]
    state_hash: str


@dataclass(frozen=True)
class StateSummary:
    """Response to ``GetStateSummary``."""

    txo_lo: int
    kernels: int
    txos: int
    utxos: int
    shielded_outs: int
    shielded_ins: int
    assets_max: int
    assets_active: int


@dataclass(frozen=True)
class AssetsListPage:
    """Response page from ``GetAssetsListAt``."""

    assets: list[AssetFull]
    more: bool
    next_asset_id: int | None


@dataclass(frozen=True)
class ContractVarEntry:
    """One key/value entry returned by ``ContractVarsEnum``."""

    key: bytes
    value: bytes


@dataclass(frozen=True)
class ContractVarsPage:
    """Response page from ``ContractVarsEnum``."""

    entries: list[ContractVarEntry]
    more: bool


@dataclass(frozen=True)
class ContractLogEntry:
    """One contract log entry returned by ``ContractLogsEnum``."""

    position: HeightPos
    key: bytes
    value: bytes


@dataclass(frozen=True)
class ContractLogsPage:
    """Response page from ``ContractLogsEnum``."""

    entries: list[ContractLogEntry]
    more: bool


@dataclass(frozen=True)
class ContractVarProof:
    """Response to ``GetContractVar``."""

    value: bytes
    proof: list[MerkleProofNode]


@dataclass(frozen=True)
class ChainWorkProofResponse:
    """Response to ``GetProofChainWork``."""

    heading_prefix: SystemStateSequencePrefix
    heading_elements: list[SystemStateElement]
    arbitrary_states: list[SystemStateFull]
    proof: list[str]
    root_live: str
    lower_bound: int