"""List locked Beam assets for one deployed contract.

Connects to a Beam node, optionally pins a dependent context, enumerates the
contract's stored ``LockedAmount`` records, and prints each locked asset ID and
amount. This mirrors the explorer-side ``funds_locked`` view and stays generic:
it does not attempt shader-specific state decoding.
"""

from __future__ import annotations

import os
import sys

# Allow running from any directory without installing the package.
sys.path.append(os.path.join(os.path.dirname(__file__), "..", "src"))

from beam_p2p import (
    BeamConnection,
    NodeQueryClient,
    contract_locked_funds_key_range,
    parse_contract_id,
    parse_contract_locked_funds_entry,
    parse_endpoint,
)

DEFAULT_NODE = "eu-nodes.mainnet.beam.mw:8100"


def parse_hash32(value: str, *, label: str) -> bytes:
    try:
        return parse_contract_id(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(str(exc).replace("contract ID", label)) from exc


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


def print_locked_funds(entries: list[tuple[int, int]]) -> None:
    if not entries:
        print("No locked asset records found for this contract in this context.")
        return

    for index, (asset_id, amount) in enumerate(entries, start=1):
        print(f"[{index}] asset_id={asset_id} amount={amount}")


def main() -> None:
    # Hardcoded configuration
    node = DEFAULT_NODE
    contract_id_hex = "b8944fd3f6a62697a89b2a55acd1cb2e3893dadece99569706efa1da847dd440"  # Replace with a real contract ID if needed.
    dependent_context_hex = None  # Replace with a 32-byte hex hash or leave None.
    request_timeout = 10.0
    max_entries = 0  # 0 means print every fetched locked-funds entry.
    verbose = False

    contract_id = parse_contract_id(contract_id_hex)
    dependent_context = (
        parse_hash32(dependent_context_hex, label="dependent context")
        if dependent_context_hex
        else None
    )
    host, port = parse_endpoint(node, default_port=8100)

    print(f"Connecting to Beam node at {host}:{port} ...")
    print(f"Contract ID      : {contract_id.hex()}")
    if dependent_context is None:
        print("Context          : tip state")
    else:
        print(f"Context          : {dependent_context.hex()}")
    print("Note             : asset_id=0 is the native BEAM asset.")

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

        print("\n--- Contract Locked Funds ---")
        entries, more_available = collect_locked_funds(
            client,
            contract_id=contract_id,
            limit=max_entries,
        )
        print_locked_funds(entries)
        print(f"\nReturned {len(entries)} locked-funds record(s).")

        if more_available:
            print(
                "More locked-funds records are available; increase max_entries if needed."
            )
    finally:
        conn.close()


if __name__ == "__main__":
    main()