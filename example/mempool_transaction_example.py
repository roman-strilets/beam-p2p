"""Fetch one transaction from the Beam mempool.

Connects to a Beam node, registers as a transaction-spreading peer, waits for
the first HaveTransaction announcement, requests the full payload via
GetTransaction, then prints the transaction id and raw payload size.
"""

import os
import sys

# Allow running from any directory without installing the package.
sys.path.append(os.path.join(os.path.dirname(__file__), "..", "src"))

from beam_p2p import (
    LOGIN_FLAG_SPREADING_TRANSACTIONS,
    BeamConnection,
    MessageType,
    decode_transaction_id,
    encode_transaction_id,
)
from beam_p2p.deserializers.tx import deserialize_new_transaction_payload
from beam_p2p.query_client import NodeQueryClient


def main() -> None:
    HOST = "eu-nodes.mainnet.beam.mw"
    PORT = 8100

    print(f"Connecting to {HOST}:{PORT} ...")

    conn = BeamConnection(host=HOST, port=PORT, verbose=True)
    try:
        conn.connect()
        # Announce transaction-spreading capability so the node forwards
        # HaveTransaction messages to us.
        conn.handshake(LOGIN_FLAG_SPREADING_TRANSACTIONS)
        print("Handshake complete.")

        client = NodeQueryClient(connection=conn, request_timeout=30.0, verbose=True)

        # Wait for the node to announce a mempool transaction.
        print("Waiting for a HaveTransaction announcement ...")
        _, have_payload = client.recv_until(
            expected={MessageType.HAVE_TRANSACTION},
            timeout=60.0,
        )
        tx_id = decode_transaction_id(have_payload)
        print(f"Announced tx id : {tx_id.hex()}")

        # Request the full transaction payload.
        print("Requesting transaction payload ...")
        conn.send(MessageType.GET_TRANSACTION, encode_transaction_id(tx_id))
        _, tx_payload = client.recv_until(expected={MessageType.NEW_TRANSACTION})
        print(f"Received tx id  : {tx_id.hex()}")
        print(f"Payload size    : {len(tx_payload)} bytes")
        print(f"Payload (hex)   : {tx_payload.hex()}")
        print(f"Decoded payload : {deserialize_new_transaction_payload(tx_payload)}")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
