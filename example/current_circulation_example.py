"""Print Beam's current circulation from a live node connection.

The values come from blockchain data:

- tip height and timestamp from the node's ``NewTip`` message
- treasury circulation from the on-chain treasury blob
- mined circulation from Beam's consensus emission rules at that tip
"""

from __future__ import annotations

from datetime import UTC, datetime

from beam_p2p import BEAM_GROTH, BeamConnection, NodeQueryClient, fetch_blockchain_circulation


DEFAULT_NODE = "eu-nodes.mainnet.beam.mw"
DEFAULT_PORT = 8100


def format_amount(amount_groth: int) -> str:
    whole, fractional = divmod(amount_groth, BEAM_GROTH)
    return f"{whole}.{fractional:08d} BEAM"


def format_timestamp(timestamp: int) -> str:
    return datetime.fromtimestamp(timestamp, UTC).isoformat().replace("+00:00", "Z")


def main() -> None:
    print(f"Connecting to Beam node at {DEFAULT_NODE}:{DEFAULT_PORT} ...")
    conn = BeamConnection(host=DEFAULT_NODE, port=DEFAULT_PORT)
    conn.connect()
    conn.handshake()

    try:
        client = NodeQueryClient(connection=conn, request_timeout=20.0, verbose=False)
        circulation = fetch_blockchain_circulation(client, tip_timeout=5.0)

        print("\n--- Beam Circulation ---")
        print(f"Tip height                   : {circulation.height}")
        print(f"Tip timestamp                : {format_timestamp(circulation.timestamp)}")
        print(
            f"Coins in circulation mined   : {format_amount(circulation.mined_circulation_groth)}"
        )
        print(
            "Coins in circulation treasury: "
            f"{format_amount(circulation.treasury_circulation_groth)}"
        )
        print(
            f"Total coins in circulation   : {format_amount(circulation.total_circulation_groth)}"
        )
        print(f"Total emission               : {format_amount(circulation.total_emission_groth)}")
    finally:
        conn.close()


if __name__ == "__main__":
    main()