"""List currently deployed Beam contracts from the live SidCid index.

Connects to a Beam node, optionally pins a dependent context, enumerates the
synthetic ``(sid, cid) -> create_height`` index, and prints each deployed
contract's shader ID, contract ID, and deployment height.
"""

from __future__ import annotations

import os
import sys

# Allow running from any directory without installing the package.
sys.path.append(os.path.join(os.path.dirname(__file__), "..", "src"))

from beam_p2p import (
    BeamConnection,
    NodeQueryClient,
    contract_sid_cid_key_range,
    parse_contract_sid_cid_entry,
    parse_contract_id,
    parse_endpoint,
)

DEFAULT_NODE = "eu-nodes.mainnet.beam.mw:8100"


def parse_hash32(value: str, *, label: str) -> bytes:
    try:
        return parse_contract_id(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(str(exc).replace("contract ID", label)) from exc


def collect_deployed_contracts(
    client: NodeQueryClient,
    *,
    limit: int,
) -> tuple[list[tuple[bytes, bytes, int]], bool]:
    entries: list[tuple[bytes, bytes, int]] = []
    key_min, key_max = contract_sid_cid_key_range()
    cursor = key_min
    skip_min = False
    more_available = False

    while True:
        page = client.enum_contract_vars(
            key_min=cursor,
            key_max=key_max,
            skip_min=skip_min,
        )
        if not page.entries:
            more_available = page.more
            break

        for entry in page.entries:
            if limit != 0 and len(entries) >= limit:
                return entries, True
            entries.append(parse_contract_sid_cid_entry(entry.key, entry.value))

        if not page.more:
            break

        cursor = page.entries[-1].key
        skip_min = True

    return entries, more_available


def print_deployed_contracts(entries: list[tuple[bytes, bytes, int]]) -> None:
    if not entries:
        print("No deployed contracts found in this context.")
        return

    for index, (shader_id, contract_id, height) in enumerate(entries, start=1):
        print(
            f"[{index}] cid={contract_id.hex()} sid={shader_id.hex()} height={height}"
        )


def main() -> None:
    # Hardcoded configuration
    node = DEFAULT_NODE
    dependent_context_hex = None  # Replace with 32-byte hex hash or leave None
    request_timeout = 10.0
    max_contracts = 0  # 0 means no local limit
    verbose = False

    dependent_context = (
        parse_hash32(dependent_context_hex, label="dependent context")
        if dependent_context_hex
        else None
    )
    host, port = parse_endpoint(node, default_port=8100)

    print(f"Connecting to Beam node at {host}:{port} ...")
    if dependent_context is None:
        print("Context          : tip state")
    else:
        print(f"Context          : {dependent_context.hex()}")

    conn = BeamConnection(host=host, port=port, verbose=verbose)
    try:
        conn.connect()
        conn.handshake()
        print("Handshake complete.")

        client = NodeQueryClient(
            connection=conn,
            request_timeout=request_timeout,
            verbose=verbose,
        )

        if dependent_context is not None:
            client.set_dependent_context(dependent_context)

        print("\n--- Deployed Contracts ---")
        entries, more_available = collect_deployed_contracts(
            client,
            limit=max_contracts,
        )
        print_deployed_contracts(entries)

        if more_available:
            print("More deployed contracts are available; increase max_contracts if needed.")
    finally:
        conn.close()


if __name__ == "__main__":
    main()