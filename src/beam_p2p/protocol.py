"""Beam wire-protocol constants and message type definitions."""

from enum import IntEnum

Address = tuple[str, int]

PROTO_MAGIC = b"\x42\x6D\x0A"
HEADER_SIZE = 8
MAC_SIZE = 8
MAX_FRAME_SIZE = 10 * 1024 * 1024

DEFAULT_PORT = 10000
DEFAULT_CONNECT_TIMEOUT = 5.0
DEFAULT_PEER_TIMEOUT = 4.0
DEFAULT_REQUEST_TIMEOUT = 10.0
DEFAULT_IDLE_TIMEOUT = 3.0
DEFAULT_RECONNECT_DELAY = 5.0
EXTENSION_VERSION = 11

LOGIN_FLAG_SPREADING_TRANSACTIONS = 0x01
LOGIN_FLAG_SEND_PEERS = 0x04


class MessageType(IntEnum):
    """Beam protocol message type codes."""

    BYE = 0x01
    PING = 0x02
    PONG = 0x03
    SCHANNEL_INIT = 0x04
    SCHANNEL_READY = 0x05
    AUTHENTICATION = 0x06
    PEER_INFO_SELF = 0x07
    PEER_INFO = 0x08
    GET_EXTERNAL_ADDR = 0x09
    EXTERNAL_ADDR = 0x0A
    GET_TIME = 0x0B
    TIME = 0x0C
    DATA_MISSING = 0x0D
    LOGIN = 0x0F
    NEW_TIP = 0x10
    GET_HDR = 0x11
    HDR = 0x12
    GET_HDR_PACK = 0x13
    HDR_PACK = 0x14
    GET_BODY = 0x15
    BODY = 0x16
    GET_PROOF_STATE = 0x17
    PROOF_STATE = 0x18
    GET_PROOF_KERNEL = 0x19
    PROOF_KERNEL = 0x1A
    GET_PROOF_UTXO = 0x1B
    PROOF_UTXO = 0x1C
    GET_PROOF_CHAIN_WORK = 0x1D
    PROOF_CHAIN_WORK = 0x1E
    CONTRACT_VARS_ENUM = 0x1F
    GET_PROOF_SHIELDED_INP = 0x20
    PROOF_SHIELDED_INP = 0x21
    GET_COMMON_STATE = 0x22
    PROOF_COMMON_STATE = 0x23
    GET_PROOF_KERNEL2 = 0x24
    PROOF_KERNEL2 = 0x25
    GET_BODY_PACK = 0x26
    BODY_PACK = 0x27
    GET_PROOF_SHIELDED_OUTP = 0x28
    PROOF_SHIELDED_OUTP = 0x29
    GET_SHIELDED_LIST = 0x2A
    GET_PROOF_KERNEL3 = 0x2B
    GET_EVENTS = 0x2C
    CONTRACT_VARS = 0x2D
    GET_BLOCK_FINALIZATION = 0x2E
    BLOCK_FINALIZATION = 0x2F
    NEW_TRANSACTION0 = 0x30
    HAVE_TRANSACTION = 0x31
    GET_TRANSACTION = 0x32
    ENUM_HDRS = 0x33
    EVENTS = 0x34
    GET_PROOF_ASSET = 0x35
    PROOF_ASSET = 0x36
    EVENTS_SERIF = 0x37
    GET_CONTRACT_VAR = 0x38
    BBS_HAVE_MSG = 0x39
    BBS_GET_MSG = 0x3A
    BBS_SUBSCRIBE = 0x3B
    CONTRACT_VAR = 0x3C
    SHIELDED_LIST = 0x3D
    BBS_RESET_SYNC = 0x3E
    BBS_MSG = 0x3F
    CONTRACT_LOGS_ENUM = 0x40
    CONTRACT_LOGS = 0x41
    GET_CONTRACT_LOG_PROOF = 0x42
    CONTRACT_LOG_PROOF = 0x43
    STATUS = 0x44
    GET_STATE_SUMMARY = 0x45
    STATE_SUMMARY = 0x46
    GET_SHIELDED_OUTPUTS_AT = 0x47
    SHIELDED_OUTPUTS_AT = 0x48
    NEW_TRANSACTION = 0x49
    SET_DEPENDENT_CONTEXT = 0x4A
    DEPENDENT_CONTEXT_CHANGED = 0x4B
    GET_ASSETS_LIST_AT = 0x4C
    ASSETS_LIST_AT = 0x4D
    PBFT_ROUND_START = 0x51
    PBFT_PROPOSAL = 0x52
    PBFT_VOTE = 0x53
    PBFT_STAMP = 0x54
    PBFT_SIG_REQUEST = 0x55
    PBFT_SIG = 0x56
    PBFT_PEER_ASSESSMENT = 0x57


MESSAGE_NAMES = {
    MessageType.BYE: "Bye",
    MessageType.PING: "Ping",
    MessageType.PONG: "Pong",
    MessageType.SCHANNEL_INIT: "SChannelInitiate",
    MessageType.SCHANNEL_READY: "SChannelReady",
    MessageType.AUTHENTICATION: "Authentication",
    MessageType.PEER_INFO_SELF: "PeerInfoSelf",
    MessageType.PEER_INFO: "PeerInfo",
    MessageType.GET_EXTERNAL_ADDR: "GetExternalAddr",
    MessageType.EXTERNAL_ADDR: "ExternalAddr",
    MessageType.GET_TIME: "GetTime",
    MessageType.TIME: "Time",
    MessageType.DATA_MISSING: "DataMissing",
    MessageType.LOGIN: "Login",
    MessageType.NEW_TIP: "NewTip",
    MessageType.GET_HDR: "GetHdr",
    MessageType.HDR: "Hdr",
    MessageType.GET_HDR_PACK: "GetHdrPack",
    MessageType.HDR_PACK: "HdrPack",
    MessageType.GET_BODY: "GetBody",
    MessageType.BODY: "Body",
    MessageType.GET_PROOF_STATE: "GetProofState",
    MessageType.PROOF_STATE: "ProofState",
    MessageType.GET_PROOF_KERNEL: "GetProofKernel",
    MessageType.PROOF_KERNEL: "ProofKernel",
    MessageType.GET_PROOF_UTXO: "GetProofUtxo",
    MessageType.PROOF_UTXO: "ProofUtxo",
    MessageType.GET_PROOF_CHAIN_WORK: "GetProofChainWork",
    MessageType.PROOF_CHAIN_WORK: "ProofChainWork",
    MessageType.CONTRACT_VARS_ENUM: "ContractVarsEnum",
    MessageType.GET_PROOF_SHIELDED_INP: "GetProofShieldedInp",
    MessageType.PROOF_SHIELDED_INP: "ProofShieldedInp",
    MessageType.GET_COMMON_STATE: "GetCommonState",
    MessageType.PROOF_COMMON_STATE: "ProofCommonState",
    MessageType.GET_PROOF_KERNEL2: "GetProofKernel2",
    MessageType.PROOF_KERNEL2: "ProofKernel2",
    MessageType.GET_BODY_PACK: "GetBodyPack",
    MessageType.BODY_PACK: "BodyPack",
    MessageType.GET_PROOF_SHIELDED_OUTP: "GetProofShieldedOutp",
    MessageType.PROOF_SHIELDED_OUTP: "ProofShieldedOutp",
    MessageType.GET_SHIELDED_LIST: "GetShieldedList",
    MessageType.GET_PROOF_KERNEL3: "GetProofKernel3",
    MessageType.GET_EVENTS: "GetEvents",
    MessageType.CONTRACT_VARS: "ContractVars",
    MessageType.GET_BLOCK_FINALIZATION: "GetBlockFinalization",
    MessageType.BLOCK_FINALIZATION: "BlockFinalization",
    MessageType.NEW_TRANSACTION0: "NewTransaction0",
    MessageType.HAVE_TRANSACTION: "HaveTransaction",
    MessageType.GET_TRANSACTION: "GetTransaction",
    MessageType.ENUM_HDRS: "EnumHdrs",
    MessageType.EVENTS: "Events",
    MessageType.GET_PROOF_ASSET: "GetProofAsset",
    MessageType.PROOF_ASSET: "ProofAsset",
    MessageType.EVENTS_SERIF: "EventsSerif",
    MessageType.GET_CONTRACT_VAR: "GetContractVar",
    MessageType.BBS_HAVE_MSG: "BbsHaveMsg",
    MessageType.BBS_GET_MSG: "BbsGetMsg",
    MessageType.BBS_SUBSCRIBE: "BbsSubscribe",
    MessageType.CONTRACT_VAR: "ContractVar",
    MessageType.SHIELDED_LIST: "ShieldedList",
    MessageType.BBS_RESET_SYNC: "BbsResetSync",
    MessageType.BBS_MSG: "BbsMsg",
    MessageType.CONTRACT_LOGS_ENUM: "ContractLogsEnum",
    MessageType.CONTRACT_LOGS: "ContractLogs",
    MessageType.GET_CONTRACT_LOG_PROOF: "GetContractLogProof",
    MessageType.CONTRACT_LOG_PROOF: "ContractLogProof",
    MessageType.STATUS: "Status",
    MessageType.GET_STATE_SUMMARY: "GetStateSummary",
    MessageType.STATE_SUMMARY: "StateSummary",
    MessageType.GET_SHIELDED_OUTPUTS_AT: "GetShieldedOutputsAt",
    MessageType.SHIELDED_OUTPUTS_AT: "ShieldedOutputsAt",
    MessageType.NEW_TRANSACTION: "NewTransaction",
    MessageType.SET_DEPENDENT_CONTEXT: "SetDependentContext",
    MessageType.DEPENDENT_CONTEXT_CHANGED: "DependentContextChanged",
    MessageType.GET_ASSETS_LIST_AT: "GetAssetsListAt",
    MessageType.ASSETS_LIST_AT: "AssetsListAt",
    MessageType.PBFT_ROUND_START: "PbftRoundStart",
    MessageType.PBFT_PROPOSAL: "PbftProposal",
    MessageType.PBFT_VOTE: "PbftVote",
    MessageType.PBFT_STAMP: "PbftStamp",
    MessageType.PBFT_SIG_REQUEST: "PbftSigRequest",
    MessageType.PBFT_SIG: "PbftSig",
    MessageType.PBFT_PEER_ASSESSMENT: "PbftPeerAssessment",
}


def message_name(message_type: int | MessageType) -> str:
    """Return a human-readable name for a message type."""
    try:
        normalized = MessageType(message_type)
    except ValueError:
        return f"0x{int(message_type):02X}"
    return MESSAGE_NAMES[normalized]