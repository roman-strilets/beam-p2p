"""Example of getting the current block height and difficulty from a Beam node.

This script connects to a Beam node and waits for a ``NewTip`` message, which the
node sends to announce the current tip of the blockchain. From this message, we
can extract the block height and the mining difficulty.
"""

from beam_p2p import (
    DEFAULT_PORT,
    BeamConnection,
    MessageType,
    NodeQueryClient,
    parse_endpoint,
)
from beam_p2p.deserializers.block import deserialize_new_tip_payload

# Default Beam mainnet node
DEFAULT_NODE = "eu-nodes.mainnet.beam.mw:8100"


def main():
    node_endpoint = DEFAULT_NODE
    host, port = parse_endpoint(node_endpoint, DEFAULT_PORT)
    request_timeout = 10.0
    verbose = False

    print(f"Connecting to Beam node at {host}:{port} ...")

    conn = BeamConnection(host=host, port=port, verbose=verbose)
    try:
        conn.connect()
        conn.handshake()
        print("Connected successfully.")

        client = NodeQueryClient(
            connection=conn,
            request_timeout=request_timeout,
            verbose=verbose,
        )

        print("Waiting for the node to announce the current tip (NewTip message)...")

        # We wait for the node to push a NEW_TIP message.
        # In a real scenario, nodes periodically push this to keep peers synced.
        msg_type, payload = client.recv_until(
            expected={MessageType.NEW_TIP}, timeout=30.0
        )

        if msg_type == MessageType.NEW_TIP:
            # deserialize_new_tip_payload converts the binary payload into a BlockHeader object.
            # It requires the peer's fork hashes to correctly identify the chain.
            header = deserialize_new_tip_payload(
                payload, client.connection.peer_fork_hashes
            )

            print("\n--- Current Tip Information ---")
            print(f"Height:     {header.height}")
            print(f"Difficulty: {header.difficulty:.2f}")
            print(f"Hash:       {header.hash}")
            print(f"Timestamp:  {header.timestamp}")
            print("-" * 28)
        else:
            print("Timed out or received unexpected response while waiting for NewTip.")

    except Exception as e:
        print(f"An error occurred: {e}")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
