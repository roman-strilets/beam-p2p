"""List Beam blockchain assets from a node.

Connects to a Beam node, queries the on-chain asset list at the current tip or
at a specific height, and prints each asset's basic fields. This enumerates the
stored asset records returned by ``GetAssetsListAt``; it does not synthesize
the native BEAM asset (``asset_id=0``).
"""

from __future__ import annotations

import os
import sys

# Allow running from any directory without installing the package.
sys.path.append(os.path.join(os.path.dirname(__file__), "..", "src"))

from beam_p2p import AssetFull, BeamConnection, NodeQueryClient, parse_endpoint

DEFAULT_NODE = "eu-nodes.mainnet.beam.mw:8100"
TIP_HEIGHT = (1 << 64) - 1


def collect_assets(
    client: NodeQueryClient,
    *,
    height: int,
    limit: int,
) -> tuple[list[AssetFull], bool]:
    page = client.get_assets_list_at(height=height, aid0=0, auto_paginate=True)
    assets = page.assets

    if limit != 0 and len(assets) > limit:
        return assets[:limit], True

    return assets, False


def format_metadata(asset: AssetFull) -> str:
    if asset.info.metadata.text is not None:
        return f"metadata_text={asset.info.metadata.text!r}"

    if asset.info.metadata.value_hex:
        return f"metadata_hex={asset.info.metadata.value_hex}"

    return "metadata=<empty>"


def print_assets(assets: list[AssetFull]) -> None:
    if not assets:
        print("No asset records found for this height.")
        return

    for index, asset in enumerate(assets, start=1):
        deposit = (
            "default"
            if asset.info.uses_default_deposit
            else str(asset.info.deposit)
        )
        fields = [
            f"[{index}]",
            f"asset_id={asset.asset_id}",
            f"value={asset.info.value}",
            f"lock_height={asset.info.lock_height}",
            f"owner={asset.info.owner}",
            f"deposit={deposit}",
            format_metadata(asset),
        ]

        if asset.info.contract_id is not None:
            fields.append(f"contract_id={asset.info.contract_id}")

        print(" ".join(fields))


def main() -> None:
    # Hardcoded configuration
    node = DEFAULT_NODE
    query_height = TIP_HEIGHT  # Replace with a specific height for a snapshot.
    request_timeout = 10.0
    max_assets = 0  # 0 means print every fetched asset.
    verbose = False

    host, port = parse_endpoint(node, default_port=8100)
    context_label = "tip state" if query_height == TIP_HEIGHT else str(query_height)

    print(f"Connecting to Beam node at {host}:{port} ...")
    print(f"Asset snapshot   : {context_label}")
    print("Note             : asset_id=0 (native BEAM) is not part of this listing.")

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

        assets, truncated = collect_assets(
            client,
            height=query_height,
            limit=max_assets,
        )

        print("\n--- Blockchain Assets ---")
        print_assets(assets)
        print(f"\nReturned {len(assets)} asset record(s).")

        if truncated:
            print("More assets were fetched; increase max_assets to print the remainder.")
    finally:
        conn.close()


if __name__ == "__main__":
    main()