"""Dump raw data for one deployed Beam contract.

Connects to a Beam node, optionally pins a dependent context, fetches the
contract's stored shader blob, then enumerates raw contract vars and logs for
that contract scope. Output stays generic and hex-oriented on purpose: this
example does not attempt shader-specific schema decoding.
"""

from __future__ import annotations

import os
import sys

# Allow running from any directory without installing the package.
sys.path.append(os.path.join(os.path.dirname(__file__), "..", "src"))

from beam_p2p import (
    BeamConnection,
    NodeQueryClient,
    contract_shader_key,
    contract_storage_key_range,
    parse_contract_id,
    parse_endpoint,
)

DEFAULT_NODE = "eu-nodes.mainnet.beam.mw:8100"


def parse_hash32(value: str, *, label: str) -> bytes:
    try:
        return parse_contract_id(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(str(exc).replace("contract ID", label)) from exc


def format_hex(data: bytes, *, max_bytes: int) -> str:
    if max_bytes == 0 or len(data) <= max_bytes:
        return data.hex()

    rendered = data[:max_bytes].hex()
    hidden = len(data) - max_bytes
    return f"{rendered}... (+{hidden} byte(s))"


def collect_contract_vars(
    client: NodeQueryClient,
    *,
    key_min: bytes,
    key_max: bytes,
    limit: int,
) -> tuple[list, bool]:
    entries = []
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

        remaining = None if limit == 0 else limit - len(entries)
        if remaining is not None and remaining <= 0:
            more_available = True
            break

        batch = page.entries if remaining is None else page.entries[:remaining]
        entries.extend(batch)

        if remaining is not None and len(batch) < len(page.entries):
            more_available = True
            break

        if not page.more:
            break

        cursor = page.entries[-1].key
        skip_min = True

    return entries, more_available


def collect_contract_logs(
    client: NodeQueryClient,
    *,
    key_min: bytes,
    key_max: bytes,
    limit: int,
) -> tuple[list, bool]:
    page = client.enum_contract_logs(key_min=key_min, key_max=key_max)
    entries = page.entries if limit == 0 else page.entries[:limit]
    more_available = page.more or (limit != 0 and len(page.entries) > limit)
    return entries, more_available


def print_contract_var_entries(entries: list, *, max_hex_bytes: int) -> None:
    if not entries:
        print("No contract vars found in this contract range.")
        return

    for index, entry in enumerate(entries, start=1):
        print(
            f"[{index}] key   ({len(entry.key)}B): {format_hex(entry.key, max_bytes=max_hex_bytes)}"
        )
        print(
            f"    value ({len(entry.value)}B): {format_hex(entry.value, max_bytes=max_hex_bytes)}"
        )


def print_contract_log_entries(entries: list, *, max_hex_bytes: int) -> None:
    if not entries:
        print("No contract logs found in this contract range.")
        return

    for index, entry in enumerate(entries, start=1):
        position = entry.position
        print(f"[{index}] pos {position.height}:{position.pos}")
        print(
            f"    key   ({len(entry.key)}B): {format_hex(entry.key, max_bytes=max_hex_bytes)}"
        )
        print(
            f"    value ({len(entry.value)}B): {format_hex(entry.value, max_bytes=max_hex_bytes)}"
        )


def main() -> None:
    # Hardcoded configuration
    node = DEFAULT_NODE
    contract_id_hex = "3f3d32e38cb27ac7b5b67343f81cf2f8bc53217eb995cc6c5d78ddc5e7b0642b"  # Replace with real contract ID
    dependent_context_hex = None  # Replace with 32-byte hex hash or leave None
    request_timeout = 10.0
    max_vars = 100
    max_logs = 100
    max_hex_bytes = 128
    skip_shader = False
    skip_vars = False
    skip_logs = False
    verbose = False

    contract_id = parse_contract_id(contract_id_hex)
    dependent_context = (
        parse_hash32(dependent_context_hex, label="dependent context")
        if dependent_context_hex
        else None
    )
    key_min, key_max = contract_storage_key_range(contract_id)
    host, port = parse_endpoint(node, default_port=8100)

    print(f"Connecting to Beam node at {host}:{port} ...")
    print(f"Contract ID      : {contract_id.hex()}")
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

        if not skip_shader:
            print("\n--- Shader Blob ---")
            proof = client.get_contract_var(contract_shader_key(contract_id))
            if proof.value:
                print(f"Bytes       : {len(proof.value)}")
                print(f"Proof nodes : {len(proof.proof)}")
                print(
                    f"Hex         : {format_hex(proof.value, max_bytes=max_hex_bytes)}"
                )
            else:
                print("No stored shader blob found for the exact contract key.")

        if not skip_vars:
            print("\n--- Contract Vars ---")
            var_entries, vars_more = collect_contract_vars(
                client,
                key_min=key_min,
                key_max=key_max,
                limit=max_vars,
            )
            print_contract_var_entries(var_entries, max_hex_bytes=max_hex_bytes)
            if vars_more:
                print("More contract vars are available; increase max_vars if needed.")

        if not skip_logs:
            print("\n--- Contract Logs ---")
            log_entries, logs_more = collect_contract_logs(
                client,
                key_min=key_min,
                key_max=key_max,
                limit=max_logs,
            )
            print_contract_log_entries(log_entries, max_hex_bytes=max_hex_bytes)
            if logs_more:
                print(
                    "More contract logs are available, but this example only prints the first "
                    "page for key-scoped log queries. Narrow the query or inspect logs in chunks "
                    "if you need the remainder."
                )
    finally:
        conn.close()


if __name__ == "__main__":
    main()
