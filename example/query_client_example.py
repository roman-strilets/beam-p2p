import os
import sys

# Add src directory to the python path to allow imports of beam_p2p
# This allows the example to be run from the project root.
sys.path.append(os.path.join(os.path.dirname(__file__), "..", "src"))

from beam_p2p.connection import BeamConnection
from beam_p2p.query_client import NodeQueryClient


def main():
    """
    A simple example demonstrating how to connect to a Beam node and
    perform queries using the NodeQueryClient.
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

        # 4. Initialize the NodeQueryClient using the established connection.
        # - request_timeout: Maximum time to wait for a response from the node.
        # - verbose: If True, prints request/response details to stderr.
        client = NodeQueryClient(connection=conn, request_timeout=10.0, verbose=True)

        # Example: Fetch the node's on-chain state summary.
        print("\n--- Fetching State Summary ---")
        summary = client.get_state_summary()
        print(f"State Summary: {summary}")

        # Example: Request a range of block headers.
        print("\n--- Requesting Block Headers ---")
        start_height = 1
        stop_height = 5
        headers = client.request_headers(
            start_height=start_height, stop_height=stop_height
        )
        print(f"Fetched {len(headers)} headers for range {start_height}-{stop_height}:")
        for h in headers:
            print(f"Height {h.height}: {h.hash}")

    except Exception as e:
        print(f"An error occurred: {e}")


if __name__ == "__main__":
    main()
