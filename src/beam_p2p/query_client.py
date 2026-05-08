"""Synchronous Beam query client for proof, state, asset, and contract requests."""

from __future__ import annotations

import sys
from collections.abc import Sequence
from dataclasses import dataclass

from .codec import (
    encode_contract_logs_enum_payload,
    encode_contract_vars_enum_payload,
    encode_get_assets_list_at_payload,
    encode_get_body_payload,
    encode_get_body_pack_payload,
    encode_get_common_state_payload,
    encode_get_contract_log_proof_payload,
    encode_get_contract_var_payload,
    encode_get_events_payload,
    encode_get_proof_asset_payload,
    encode_get_proof_chain_work_payload,
    encode_get_proof_kernel2_payload,
    encode_get_proof_kernel3_payload,
    encode_get_proof_kernel_payload,
    encode_get_proof_shielded_inp_payload,
    encode_get_proof_shielded_outp_payload,
    encode_get_proof_state_payload,
    encode_get_proof_utxo_payload,
    encode_get_shielded_list_payload,
    encode_get_shielded_outputs_at_payload,
    encode_height_range,
    encode_optional_hash,
)
from .connection import BeamConnection
from .deserializers import (
    BufferReader,
    DeserializationError,
    deserialize_assets_list_at_payload,
    deserialize_body_pack_payloads,
    deserialize_body_payload,
    deserialize_new_tip_payload,
    deserialize_contract_log_proof_payload,
    deserialize_contract_logs_payload,
    deserialize_contract_var_payload,
    deserialize_contract_vars_payload,
    deserialize_events_payload,
    deserialize_header_pack_payloads,
    deserialize_proof_asset_payload,
    deserialize_proof_chain_work_payload,
    deserialize_proof_common_state_payload,
    deserialize_proof_kernel2_payload,
    deserialize_proof_kernel_payload,
    deserialize_proof_shielded_inp_payload,
    deserialize_proof_shielded_outp_payload,
    deserialize_proof_state_payload,
    deserialize_proof_utxo_payload,
    deserialize_shielded_list_payload,
    deserialize_shielded_outputs_at_payload,
    deserialize_state_summary_payload,
)
from .protocol import MessageType, message_name
from .protocol_models import BlockHeader, DecodedBlock, EcPoint
from .query_models import (
    AssetsListPage,
    ChainWorkProofResponse,
    ContractLogsPage,
    ContractVarProof,
    ContractVarsPage,
    HeightPos,
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
    SystemStateId,
)
from .utils import format_address

ZERO_HASH = bytes(32)


@dataclass(frozen=True)
class BodyFetchPlan:
    """Describe one staged body-fetch phase."""

    start_height: int
    stop_height: int
    flag_perishable: int
    flag_eternal: int
    block0: int
    horizon_lo1: int
    horizon_hi1: int


BODY_FLAG_FULL = 0
BODY_FLAG_NONE = 1
BODY_FLAG_RECOVERY1 = 2


class NodeQueryClient:
    """Issue synchronous Beam node requests over an existing connection."""

    def __init__(
        self,
        connection: BeamConnection,
        *,
        request_timeout: float,
        verbose: bool,
    ) -> None:
        """
        Initialize the NodeQueryClient.

        :param connection: The connection to the Beam node.
        :param request_timeout: The timeout for requests in seconds.
        :param verbose: Whether to enable verbose logging.
        """
        self.connection = connection
        host = getattr(connection, "host", "<unknown>")
        port = getattr(connection, "port", 0)
        self.endpoint = format_address((str(host), int(port)))
        self.request_timeout = request_timeout
        self.verbose = verbose
        self.dependent_contexts: list[str] = []
        self.dependent_prefix_depth: int = 0

    def _log(self, message: str) -> None:
        """
        Log a message if verbose mode is enabled.

        :param message: The message to log.
        """
        if self.verbose:
            print(message, file=sys.stderr)

    def _coerce_point(
        self,
        point: EcPoint | tuple[bytes | bytearray | str, bool],
    ) -> tuple[bytes | bytearray | str, bool]:
        """
        Coerce a point into a (x, y_flag) tuple.

        :param point: The point to coerce.
        """
        if isinstance(point, EcPoint):
            return point.x, point.y
        return point

    def _coerce_height_pos(self, pos: HeightPos | tuple[int, int]) -> tuple[int, int]:
        """
        Coerce a height position into a (height, pos) tuple.

        :param pos: The position to coerce.
        """
        if isinstance(pos, HeightPos):
            return pos.height, pos.pos
        return pos

    def _coerce_state_id(
        self,
        state_id: SystemStateId | tuple[int, bytes | bytearray | str],
    ) -> tuple[int, bytes | bytearray | str]:
        """
        Coerce a state ID into a (number, hash) tuple.

        :param state_id: The state ID to coerce.
        """
        if isinstance(state_id, SystemStateId):
            return state_id.number, state_id.hash
        return state_id

    def _decode_dependent_context_changed(self, payload: bytes) -> None:
        """
        Decode a DependentContextChanged message payload.

        :param payload: The raw payload to decode.
        """
        reader = BufferReader(payload)
        count = reader.read_var_uint()
        self.dependent_contexts = [reader.read_hash32() for _ in range(count)]
        self.dependent_prefix_depth = reader.read_var_uint()
        if reader.remaining != 0:
            raise DeserializationError(
                f"{reader.remaining} trailing byte(s) left after DependentContextChanged parse"
            )

    def recv_until(
        self,
        *,
        expected: set[MessageType],
        timeout: float | None = None,
    ) -> tuple[MessageType, bytes]:
        """
        Receive messages until one of the expected message types arrives.

        :param expected: A set of message types to wait for.
        :param timeout: Optional override for the request timeout.
        """
        effective_timeout = self.request_timeout if timeout is None else timeout

        while True:
            message_type, payload = self.connection.recv_message(effective_timeout)

            if message_type in expected:
                return message_type, payload

            match message_type:
                case MessageType.PEER_INFO | MessageType.PEER_INFO_SELF:
                    self._log(
                        f"[*] {self.endpoint} ignored {message_name(message_type)} ({len(payload)}B)"
                    )
                    continue
                case MessageType.GET_TIME:
                    self.connection.send_time()
                    continue
                case MessageType.PING:
                    self.connection.send(MessageType.PONG)
                    continue
                case MessageType.BYE:
                    raise RuntimeError("node sent Bye before request completed")
                case MessageType.DATA_MISSING:
                    raise RuntimeError("node reported the requested data is missing")
                case MessageType.DEPENDENT_CONTEXT_CHANGED:
                    self._decode_dependent_context_changed(payload)
                    continue
                case (
                    MessageType.AUTHENTICATION
                    | MessageType.LOGIN
                    | MessageType.NEW_TIP
                    | MessageType.STATUS
                    | MessageType.TIME
                    | MessageType.EVENTS_SERIF
                ):
                    self._log(
                        f"[*] {self.endpoint} <- {message_name(message_type)} ({len(payload)}B)"
                    )
                    continue
                case _:
                    self._log(
                        f"[*] {self.endpoint} ignored {message_name(message_type)} ({len(payload)}B)"
                    )

    def wait_for_tip(self, *, timeout: float | None = None) -> BlockHeader:
        """Wait for the next ``NewTip`` message and return the decoded header."""

        _, payload = self.recv_until(
            expected={MessageType.NEW_TIP},
            timeout=timeout,
        )
        return deserialize_new_tip_payload(
            payload,
            self.connection.peer_fork_hashes,
        )

    def _request(
        self, request_type: MessageType, expected_type: MessageType, payload: bytes
    ) -> bytes:
        """
        Send a request and wait for the expected response.

        :param request_type: The type of the request message.
        :param expected_type: The expected response message type.
        :param payload: The payload to send with the request.
        """
        self.connection.send(request_type, payload)
        message_type, response_payload = self.recv_until(expected={expected_type})
        if message_type != expected_type:
            raise RuntimeError(
                f"expected {message_name(expected_type)}, got {message_name(message_type)}"
            )
        return response_payload

    def set_dependent_context(
        self, context_hash: bytes | bytearray | str | None
    ) -> None:
        """
        Set the dependent context used by subsequent contract and event queries.

        :param context_hash: The hash of the context to set, or None to clear it.
        """
        self.connection.send(
            MessageType.SET_DEPENDENT_CONTEXT,
            encode_optional_hash(context_hash),
        )

    def request_headers(
        self, *, start_height: int, stop_height: int
    ) -> list[BlockHeader]:
        """
        Request a contiguous block-header range.

        :param start_height: The starting height of the range.
        :param stop_height: The ending height of the range.
        """
        if start_height > stop_height:
            raise ValueError(
                f"start_height {start_height} must be <= stop_height {stop_height}"
            )

        self.connection.send(
            MessageType.ENUM_HDRS,
            encode_height_range(start_height, stop_height),
        )
        self._log(f"[*] {self.endpoint} requested headers {start_height}-{stop_height}")

        message_type, payload = self.recv_until(expected={MessageType.HDR_PACK})
        if message_type != MessageType.HDR_PACK:
            raise RuntimeError(f"expected HdrPack, got {message_name(message_type)}")

        headers = deserialize_header_pack_payloads(
            payload, self.connection.peer_fork_hashes
        )
        if not headers:
            raise RuntimeError(
                f"requested header range {start_height}-{stop_height}, node returned no headers"
            )
        if headers[0].height != start_height:
            raise RuntimeError(
                f"requested header range {start_height}-{stop_height}, got first header "
                f"for {headers[0].height}"
            )
        for previous_header, header in zip(headers, headers[1:]):
            if header.height != previous_header.height + 1:
                raise RuntimeError(
                    f"requested header range {start_height}-{stop_height}, got non-contiguous "
                    f"headers {previous_header.height} then {header.height}"
                )
        if headers[-1].height > stop_height:
            raise RuntimeError(
                f"requested header range {start_height}-{stop_height}, got header for "
                f"{headers[-1].height}"
            )
        return headers

    def request_body_range_payload(
        self,
        *,
        headers: Sequence[BlockHeader],
        plan: BodyFetchPlan,
    ) -> tuple[MessageType, bytes]:
        """
        Request a contiguous block-body range and return the raw frame.

        :param headers: The sequence of block headers for the requested range.
        :param plan: The body fetch plan describing the request parameters.
        """
        if not headers:
            raise ValueError("headers must not be empty")

        base_header = headers[0]
        top_header = headers[-1]
        payload = encode_get_body_pack_payload(
            top_height=top_header.height,
            top_hash=bytes.fromhex(top_header.hash),
            flag_perishable=plan.flag_perishable,
            flag_eternal=plan.flag_eternal,
            count_extra=top_header.height - base_header.height,
            block0=plan.block0,
            horizon_lo1=plan.horizon_lo1,
            horizon_hi1=plan.horizon_hi1,
        )
        self.connection.send(MessageType.GET_BODY_PACK, payload)
        self._log(
            "[*] "
            f"{self.endpoint} requested bodies {base_header.height}-{top_header.height} "
            f"(p={plan.flag_perishable}, e={plan.flag_eternal}, block0={plan.block0}, "
            f"lo={plan.horizon_lo1}, hi={plan.horizon_hi1})"
        )

        message_type, response_payload = self.recv_until(
            expected={MessageType.BODY, MessageType.BODY_PACK}
        )
        if message_type in {MessageType.BODY, MessageType.BODY_PACK}:
            return message_type, response_payload
        raise RuntimeError(
            f"unexpected message while waiting for block range: {message_name(message_type)}"
        )

    def fetch_blocks(self, plan: BodyFetchPlan) -> list[DecodedBlock]:
        """
        Fetch and deserialize a contiguous block range.

        :param plan: The body fetch plan describing the range and flags.
        """
        headers = self.request_headers(
            start_height=plan.start_height, stop_height=plan.stop_height
        )
        message_type, payload = self.request_body_range_payload(
            headers=headers, plan=plan
        )
        if message_type == MessageType.BODY:
            return [deserialize_body_payload(payload, headers[0])]
        blocks = deserialize_body_pack_payloads(payload, headers)
        if len(blocks) != len(headers):
            raise RuntimeError(
                "requested block range "
                f"{plan.start_height}-{plan.stop_height}, node returned {len(blocks)} "
                f"body payload(s) for {len(headers)} header(s)"
            )
        return blocks

    def get_state_summary(self) -> StateSummary:
        """
        Fetch the node's on-chain state summary counters.
        """
        return deserialize_state_summary_payload(
            self._request(MessageType.GET_STATE_SUMMARY, MessageType.STATE_SUMMARY, b"")
        )

    def get_treasury_payload(self) -> bytes:
        """
        Fetch the Beam treasury eternal payload via the special zero-ID body request.
        """
        payload = self._request(
            MessageType.GET_BODY,
            MessageType.BODY,
            encode_get_body_payload(0, ZERO_HASH),
        )
        reader = BufferReader(payload)
        reader.read_byte_buffer()
        eternal = reader.read_byte_buffer()
        if reader.remaining != 0:
            raise DeserializationError(
                f"{reader.remaining} trailing byte(s) left after treasury Body parse"
            )
        return eternal

    def get_shielded_outputs_at(self, *, height: int) -> int:
        """
        Fetch the cumulative number of shielded outputs at a given height.

        :param height: The block height to query.
        """
        return deserialize_shielded_outputs_at_payload(
            self._request(
                MessageType.GET_SHIELDED_OUTPUTS_AT,
                MessageType.SHIELDED_OUTPUTS_AT,
                encode_get_shielded_outputs_at_payload(height),
            )
        )

    def get_assets_list_at(
        self,
        *,
        height: int,
        aid0: int = 0,
        auto_paginate: bool = True,
    ) -> AssetsListPage:
        """
        Fetch asset listings at a given height, optionally following Beam pagination.

        :param height: The block height to query.
        :param aid0: The starting asset ID for the listing.
        :param auto_paginate: Whether to automatically fetch all pages of assets.
        """
        current_aid = aid0
        page = deserialize_assets_list_at_payload(
            self._request(
                MessageType.GET_ASSETS_LIST_AT,
                MessageType.ASSETS_LIST_AT,
                encode_get_assets_list_at_payload(height=height, aid0=current_aid),
            )
        )

        if not auto_paginate or not page.more:
            return page

        assets = list(page.assets)
        current_aid = page.next_asset_id if page.next_asset_id is not None else current_aid

        while page.more:
            if page.next_asset_id is None:
                raise RuntimeError(
                    "node returned AssetsListAt more flag without any assets"
                )

            page = deserialize_assets_list_at_payload(
                self._request(
                    MessageType.GET_ASSETS_LIST_AT,
                    MessageType.ASSETS_LIST_AT,
                    encode_get_assets_list_at_payload(height=height, aid0=current_aid),
                )
            )
            assets.extend(page.assets)

            if page.next_asset_id is not None:
                current_aid = page.next_asset_id

        return AssetsListPage(assets=assets, more=False, next_asset_id=current_aid)

    def get_proof_asset(
        self,
        *,
        asset_id: int = 0,
        owner: bytes | bytearray | str = ZERO_HASH,
    ) -> ProofAssetResponse:
        """
        Fetch an asset proof by asset id or owner.

        :param asset_id: The asset ID to query.
        :param owner: The owner of the asset.
        """
        return deserialize_proof_asset_payload(
            self._request(
                MessageType.GET_PROOF_ASSET,
                MessageType.PROOF_ASSET,
                encode_get_proof_asset_payload(asset_id=asset_id, owner=owner),
            )
        )

    def get_shielded_list(self, *, id0: int, count: int) -> ShieldedListResponse:
        """
        Fetch a page of shielded output serials.

        :param id0: The starting index for the list.
        :param count: The number of entries to fetch.
        """
        return deserialize_shielded_list_payload(
            self._request(
                MessageType.GET_SHIELDED_LIST,
                MessageType.SHIELDED_LIST,
                encode_get_shielded_list_payload(id0=id0, count=count),
            )
        )

    def get_proof_shielded_outp(
        self,
        point: EcPoint | tuple[bytes | bytearray | str, bool],
    ) -> ProofShieldedOutpResponse:
        """
        Fetch a shielded-output proof by serial public key.

        :param point: The serial public key point.
        """
        x, y = self._coerce_point(point)
        return deserialize_proof_shielded_outp_payload(
            self._request(
                MessageType.GET_PROOF_SHIELDED_OUTP,
                MessageType.PROOF_SHIELDED_OUTP,
                encode_get_proof_shielded_outp_payload(serial_pub_x=x, y_flag=y),
            )
        )

    def get_proof_shielded_inp(
        self,
        point: EcPoint | tuple[bytes | bytearray | str, bool],
    ) -> ProofShieldedInpResponse:
        """
        Fetch a shielded-input proof by spend public key.

        :param point: The spend public key point.
        """
        x, y = self._coerce_point(point)
        return deserialize_proof_shielded_inp_payload(
            self._request(
                MessageType.GET_PROOF_SHIELDED_INP,
                MessageType.PROOF_SHIELDED_INP,
                encode_get_proof_shielded_inp_payload(spend_pk_x=x, y_flag=y),
            )
        )

    def get_proof_utxo(
        self,
        point: EcPoint | tuple[bytes | bytearray | str, bool],
        *,
        maturity_min: int = 0,
    ) -> ProofUtxoResponse:
        """
        Fetch a UTXO proof by commitment.

        :param point: The commitment point.
        :param maturity_min: The minimum maturity height.
        """
        x, y = self._coerce_point(point)
        return deserialize_proof_utxo_payload(
            self._request(
                MessageType.GET_PROOF_UTXO,
                MessageType.PROOF_UTXO,
                encode_get_proof_utxo_payload(
                    commitment_x=x,
                    y_flag=y,
                    maturity_min=maturity_min,
                ),
            )
        )

    def get_proof_kernel(
        self, kernel_id: bytes | bytearray | str
    ) -> ProofKernelResponse:
        """
        Fetch the legacy long proof for a kernel id.

        :param kernel_id: The kernel ID to query.
        """
        return deserialize_proof_kernel_payload(
            self._request(
                MessageType.GET_PROOF_KERNEL,
                MessageType.PROOF_KERNEL,
                encode_get_proof_kernel_payload(kernel_id),
            )
        )

    def get_proof_kernel2(
        self,
        kernel_id: bytes | bytearray | str,
        *,
        fetch: bool = True,
    ) -> ProofKernel2Response:
        """
        Fetch a kernel proof with optional embedded kernel data.

        :param kernel_id: The kernel ID to query.
        :param fetch: Whether to fetch and include the kernel data.
        """
        return deserialize_proof_kernel2_payload(
            self._request(
                MessageType.GET_PROOF_KERNEL2,
                MessageType.PROOF_KERNEL2,
                encode_get_proof_kernel2_payload(kernel_id, fetch=fetch),
            )
        )

    def get_proof_kernel3(
        self,
        pos: HeightPos | tuple[int, int],
        *,
        with_proof: bool = True,
    ) -> ProofKernel2Response:
        """
        Fetch a kernel proof by block position.

        :param pos: The position of the kernel to query.
        :param with_proof: Whether to include the proof in the response.
        """
        height, index = self._coerce_height_pos(pos)
        return deserialize_proof_kernel2_payload(
            self._request(
                MessageType.GET_PROOF_KERNEL3,
                MessageType.PROOF_KERNEL2,
                encode_get_proof_kernel3_payload(
                    height=height,
                    pos=index,
                    with_proof=with_proof,
                ),
            )
        )

    def get_proof_state(self, number: int) -> ProofStateResponse:
        """
        Fetch a hard proof for a block-state number.

        :param number: The block-state number to query.
        """
        return deserialize_proof_state_payload(
            self._request(
                MessageType.GET_PROOF_STATE,
                MessageType.PROOF_STATE,
                encode_get_proof_state_payload(number),
            )
        )

    def get_common_state(
        self,
        ids: list[SystemStateId | tuple[int, bytes | bytearray | str]],
    ) -> ProofCommonStateResponse:
        """
        Fetch a common-state proof across multiple candidate states.

        :param ids: A list of state IDs to find a common proof for.
        """
        return deserialize_proof_common_state_payload(
            self._request(
                MessageType.GET_COMMON_STATE,
                MessageType.PROOF_COMMON_STATE,
                encode_get_common_state_payload(
                    [self._coerce_state_id(state_id) for state_id in ids]
                ),
            )
        )

    def get_proof_chain_work(
        self,
        *,
        lower_bound: int | bytes | bytearray | str = 0,
    ) -> ChainWorkProofResponse:
        """
        Fetch a chainwork proof with an optional lower-bound filter.

        :param lower_bound: The lower bound for the chainwork proof.
        """
        return deserialize_proof_chain_work_payload(
            self._request(
                MessageType.GET_PROOF_CHAIN_WORK,
                MessageType.PROOF_CHAIN_WORK,
                encode_get_proof_chain_work_payload(lower_bound),
            )
        )

    def enum_contract_vars(
        self,
        *,
        key_min: bytes = b"",
        key_max: bytes = b"",
        skip_min: bool = False,
    ) -> ContractVarsPage:
        """
        Enumerate contract key/value pairs in the active dependent context.

        :param key_min: The minimum key to start enumeration.
        :param key_max: The maximum key to end enumeration.
        :param skip_min: Whether to skip the minimum key itself.
        """
        return deserialize_contract_vars_payload(
            self._request(
                MessageType.CONTRACT_VARS_ENUM,
                MessageType.CONTRACT_VARS,
                encode_contract_vars_enum_payload(
                    key_min=key_min,
                    key_max=key_max,
                    skip_min=skip_min,
                ),
            )
        )

    def enum_contract_logs(
        self,
        *,
        key_min: bytes = b"",
        key_max: bytes = b"",
        pos_min: HeightPos | tuple[int, int] = (0, 0),
        pos_max: HeightPos | tuple[int, int] = (0, 0),
    ) -> ContractLogsPage:
        """
        Enumerate contract logs in the active dependent context.

        :param key_min: The minimum key to start enumeration.
        :param key_max: The maximum key to end enumeration.
        :param pos_min: The minimum position to start enumeration.
        :param pos_max: The maximum position to end enumeration.
        """
        min_height, min_pos = self._coerce_height_pos(pos_min)
        max_height, max_pos = self._coerce_height_pos(pos_max)
        return deserialize_contract_logs_payload(
            self._request(
                MessageType.CONTRACT_LOGS_ENUM,
                MessageType.CONTRACT_LOGS,
                encode_contract_logs_enum_payload(
                    key_min=key_min,
                    key_max=key_max,
                    pos_min=(min_height, min_pos),
                    pos_max=(max_height, max_pos),
                ),
            )
        )

    def get_contract_var(self, key: bytes) -> ContractVarProof:
        """
        Fetch one contract key/value proof in the active dependent context.

        :param key: The key of the contract variable to fetch.
        """
        return deserialize_contract_var_payload(
            self._request(
                MessageType.GET_CONTRACT_VAR,
                MessageType.CONTRACT_VAR,
                encode_get_contract_var_payload(key),
            )
        )

    def get_contract_log_proof(
        self,
        pos: HeightPos | tuple[int, int],
    ) -> list:
        """
        Fetch a Merkle proof for one contract log entry position.

        :param pos: The position of the contract log entry.
        """
        height, index = self._coerce_height_pos(pos)
        return deserialize_contract_log_proof_payload(
            self._request(
                MessageType.GET_CONTRACT_LOG_PROOF,
                MessageType.CONTRACT_LOG_PROOF,
                encode_get_contract_log_proof_payload(height=height, pos=index),
            )
        )

    def get_events(self, *, height_min: int) -> bytes:
        """
        Fetch serialized event data from the node.

        :param height_min: The minimum height to start fetching events from.
        """
        return deserialize_events_payload(
            self._request(
                MessageType.GET_EVENTS,
                MessageType.EVENTS,
                encode_get_events_payload(height_min),
            )
        )
