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
    HDR_PACK = 0x14
    BODY = 0x16
    GET_BODY_PACK = 0x26
    BODY_PACK = 0x27
    HAVE_TRANSACTION = 0x31
    GET_TRANSACTION = 0x32
    ENUM_HDRS = 0x33
    STATUS = 0x44
    NEW_TRANSACTION = 0x49


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
    MessageType.HDR_PACK: "HdrPack",
    MessageType.BODY: "Body",
    MessageType.GET_BODY_PACK: "GetBodyPack",
    MessageType.BODY_PACK: "BodyPack",
    MessageType.HAVE_TRANSACTION: "HaveTransaction",
    MessageType.GET_TRANSACTION: "GetTransaction",
    MessageType.ENUM_HDRS: "EnumHdrs",
    MessageType.STATUS: "Status",
    MessageType.NEW_TRANSACTION: "NewTransaction",
}


def message_name(message_type: int | MessageType) -> str:
    """Return a human-readable name for a message type."""
    try:
        normalized = MessageType(message_type)
    except ValueError:
        return f"0x{int(message_type):02X}"
    return MESSAGE_NAMES[normalized]