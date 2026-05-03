import os
import sys

# Add src directory to the python path to allow imports of beam_p2p
# This allows the example to be run from the project root.
sys.path.append(os.path.join(os.path.dirname(__file__), "..", "src"))

from beam_p2p.connection import BeamConnection
from beam_p2p.protocol import LOGIN_FLAG_SEND_PEERS
from beam_p2p.utils import format_address


def main():
    """
    A simple example demonstrating how to retrieve a list of peers from a Beam node.
    """
    # Configuration for the Beam node.
    # Update these values to match your running node.
    HOST = "eu-nodes.mainnet.beam.mw"
    PORT = 8100

    print(f"Connecting to Beam node at {HOST}:{PORT} to fetch peers...")

    try:
        # 1. Create a connection object.
        # BeamConnection manages the TCP socket and the encrypted secure channel.
        conn = BeamConnection(host=HOST, port=PORT)

        # 2. Establish the TCP connection.
        conn.connect()

        # 3. Perform the secure-channel and login handshake.
        # We explicitly request the node to send peer information using LOGIN_FLAG_SEND_PEERS.
        conn.handshake(login_flags=LOGIN_FLAG_SEND_PEERS)
        print("Handshake successful!")

        # 4. Collect peer advertisements.
        # After a successful handshake with LOGIN_FLAG_SEND_PEERS, the node will send
        # PEER_INFO messages. We collect them until the specified timeout expires.
        timeout = 5.0
        print(f"Collecting peers for {timeout} seconds...")
        peers = conn.collect_peers(timeout=timeout)

        print(f"\nSuccessfully collected {len(peers)} peers:")
        for address, peer_id in peers.items():
            # peer_id is bytes, address is a tuple (host, port)
            print(f"Peer ID: {peer_id.hex()} | Address: {format_address(address)}")

    except Exception as e:
        print(f"An error occurred: {e}")


if __name__ == "__main__":
    main()
