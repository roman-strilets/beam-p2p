from beam_p2p.protocol import MessageType, message_name


def test_extended_message_type_codes_match_beam_core() -> None:
    expected_codes = {
        "GET_HDR": 0x11,
        "HDR": 0x12,
        "GET_HDR_PACK": 0x13,
        "GET_BODY": 0x15,
        "GET_PROOF_STATE": 0x17,
        "PROOF_STATE": 0x18,
        "GET_PROOF_KERNEL": 0x19,
        "PROOF_KERNEL": 0x1A,
        "GET_PROOF_UTXO": 0x1B,
        "PROOF_UTXO": 0x1C,
        "GET_PROOF_CHAIN_WORK": 0x1D,
        "PROOF_CHAIN_WORK": 0x1E,
        "CONTRACT_VARS_ENUM": 0x1F,
        "GET_PROOF_SHIELDED_INP": 0x20,
        "PROOF_SHIELDED_INP": 0x21,
        "GET_COMMON_STATE": 0x22,
        "PROOF_COMMON_STATE": 0x23,
        "GET_PROOF_KERNEL2": 0x24,
        "PROOF_KERNEL2": 0x25,
        "GET_PROOF_SHIELDED_OUTP": 0x28,
        "PROOF_SHIELDED_OUTP": 0x29,
        "GET_SHIELDED_LIST": 0x2A,
        "GET_PROOF_KERNEL3": 0x2B,
        "GET_EVENTS": 0x2C,
        "CONTRACT_VARS": 0x2D,
        "GET_BLOCK_FINALIZATION": 0x2E,
        "BLOCK_FINALIZATION": 0x2F,
        "NEW_TRANSACTION0": 0x30,
        "EVENTS": 0x34,
        "GET_PROOF_ASSET": 0x35,
        "PROOF_ASSET": 0x36,
        "EVENTS_SERIF": 0x37,
        "GET_CONTRACT_VAR": 0x38,
        "BBS_HAVE_MSG": 0x39,
        "BBS_GET_MSG": 0x3A,
        "BBS_SUBSCRIBE": 0x3B,
        "CONTRACT_VAR": 0x3C,
        "SHIELDED_LIST": 0x3D,
        "BBS_RESET_SYNC": 0x3E,
        "BBS_MSG": 0x3F,
        "CONTRACT_LOGS_ENUM": 0x40,
        "CONTRACT_LOGS": 0x41,
        "GET_CONTRACT_LOG_PROOF": 0x42,
        "CONTRACT_LOG_PROOF": 0x43,
        "GET_STATE_SUMMARY": 0x45,
        "STATE_SUMMARY": 0x46,
        "GET_SHIELDED_OUTPUTS_AT": 0x47,
        "SHIELDED_OUTPUTS_AT": 0x48,
        "SET_DEPENDENT_CONTEXT": 0x4A,
        "DEPENDENT_CONTEXT_CHANGED": 0x4B,
        "GET_ASSETS_LIST_AT": 0x4C,
        "ASSETS_LIST_AT": 0x4D,
        "PBFT_ROUND_START": 0x51,
        "PBFT_PROPOSAL": 0x52,
        "PBFT_VOTE": 0x53,
        "PBFT_STAMP": 0x54,
        "PBFT_SIG_REQUEST": 0x55,
        "PBFT_SIG": 0x56,
        "PBFT_PEER_ASSESSMENT": 0x57,
    }

    for name, code in expected_codes.items():
        assert getattr(MessageType, name).value == code


def test_extended_message_names_are_human_readable() -> None:
    assert message_name(MessageType.GET_PROOF_KERNEL3) == "GetProofKernel3"
    assert message_name(MessageType.CONTRACT_LOGS_ENUM) == "ContractLogsEnum"
    assert message_name(MessageType.GET_ASSETS_LIST_AT) == "GetAssetsListAt"
    assert message_name(MessageType.PBFT_STAMP) == "PbftStamp"