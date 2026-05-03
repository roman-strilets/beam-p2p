import os
import sys

# Add src directory to the python path to allow imports of beam_p2p
# This allows the example to be run from the project root.
sys.path.append(os.path.join(os.path.dirname(__file__), "..", "src"))

from beam_p2p.connection import BeamConnection
from beam_p2p.query_client import BodyFetchPlan, NodeQueryClient


def main():
    """
    A simple example demonstrating how to fetch blocks from a Beam node
    using the NodeQueryClient.
    """
    # Configuration for the Beam node.
    # Update these values to match your running node.
    HOST = "eu-nodes.mainnet.beam.mw"
    PORT = 8100

    print(f"Connecting to Beam node at {HOST}:{PORT}...")

    try:
        # 1. Create a connection object.
        # BeamConnection manages the TCP socket and the encrypted secure channel.
        conn = BeamConnection(host=HOST, port=PORT)

        # 2. Establish the TCP connection.
        conn.connect()

        # 3. Perform the secure-channel and login handshake.
        # NodeQueryClient requires an authenticated connection.
        conn.handshake()
        print("Handshake successful!")

        # 4. Initialize the NodeQueryClient.
        # - request_timeout: Maximum time to wait for a response from the node.
        # - verbose: If True, prints request/response details to stderr.
        client = NodeQueryClient(connection=conn, request_timeout=10.0, verbose=True)

        # 5. Define a fetch plan for the blocks we want to retrieve.
        # We'll fetch a small range of blocks (e.g., heights 1 to 2).
        # The other parameters (flags and horizons) are set to 0 for this simple example.
        start_height = 1
        stop_height = 2
        plan = BodyFetchPlan(
            start_height=start_height,
            stop_height=stop_height,
            flag_perishable=0,
            flag_eternal=0,
            block0=0,
            horizon_lo1=0,
            horizon_hi1=0,
        )

        print(f"\n--- Fetching Blocks from height {start_height} to {stop_height} ---")
        blocks = client.fetch_blocks(plan=plan)

        print(f"Successfully fetched {len(blocks)} blocks:")
        for block in blocks:
            print(f"Block Height: {block.header.height}")
            print(f"Block Hash: {block.header.hash}")
            print(f"Inputs count: {len(block.inputs)}")
            print(f"Outputs count: {len(block.outputs)}")
            print(f"Kernels count: {len(block.kernels)}")
            print("-" * 20)

    except Exception as e:
        print(f"An error occurred: {e}")


if __name__ == "__main__":
    main()
