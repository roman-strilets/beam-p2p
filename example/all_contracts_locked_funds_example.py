"""Sum locked Beam assets across all deployed contracts.

Connects to a Beam node, enumerates all deployed contracts, and for each contract,
enumerates its locked assets. Finally, it aggregates the total amount of each
asset locked across the entire chain and prints the results.
"""

from __future__ import annotations

import os
import sys
from collections import defaultdict

# Allow running from any directory without installing the package.
sys.path.append(os.path.join(os.path.dirname(__file__), "..", "src"))

from beam_p2p import (
    BeamConnection,
    NodeQueryClient,
    contract_locked_funds_key_range,
    contract_sid_cid_key_range,
    parse_contract_id,
    parse_contract_locked_funds_entry,
    parse_contract_sid_cid_entry,
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


def collect_locked_funds(
    client: NodeQueryClient,
    *,
    contract_id: bytes,
    limit: int,
) -> tuple[list[tuple[int, int]], bool]:
    entries: list[tuple[int, int]] = []
    key_min, key_max = contract_locked_funds_key_range(contract_id)
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

            decoded_contract_id, asset_id, amount = parse_contract_locked_funds_entry(
                entry.key,
                entry.value,
            )
            if decoded_contract_id != contract_id:
                raise RuntimeError(
                    "node returned a locked-funds entry outside the requested contract"
                )
            entries.append((asset_id, amount))

        if not page.more:
            break

        cursor = page.entries[-1].key
        skip_min = True

    return entries, more_available


def main() -> None:
    # Hardcoded configuration
    node = DEFAULT_NODE
    dependent_context_hex = None  # Replace with a 32-byte hex hash or leave None
    request_timeout = 10.0
    max_contracts = 0  # 0 means no local limit
    max_funds_per_contract = 0  # 0 means no limit per contract
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

        print("\n--- Collecting Deployed Contracts ---")
        contracts, more_contracts = collect_deployed_contracts(
            client,
            limit=max_contracts,
        )
        print(f"Found {len(contracts)} contracts.")

        # Map to store total locked amount per asset ID: {asset_id: total_amount}
        asset_totals = defaultdict(int)
        total_contracts_processed = 0

        print("\n--- Aggregating Locked Funds ---")
        for shader_id, contract_id, height in contracts:
            total_contracts_processed += 1
            if verbose:
                print(
                    f"Processing contract {contract_id.hex()} (shader {shader_id.hex()})"
                )

            funds, _ = collect_locked_funds(
                client,
                contract_id=contract_id,
                limit=max_funds_per_contract,
            )
            for asset_id, amount in funds:
                asset_totals[asset_id] += amount

        print(f"Processed {total_contracts_processed} contracts.")

        print("\n--- Total Locked Assets Across All Contracts ---")
        if not asset_totals:
            print("No locked assets found.")
        else:
            # Sort by asset_id for consistent output
            for asset_id in sorted(asset_totals.keys()):
                amount = asset_totals[asset_id]
                print(f"Asset ID: {asset_id} | Total Locked: {amount}")

        if more_contracts:
            print(
                "\nNote: More deployed contracts were available than fetched (limit reached)."
            )

    finally:
        conn.close()


if __name__ == "__main__":
    main()
