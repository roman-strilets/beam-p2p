Shared Python library for the Beam peer-to-peer wire protocol.

The package consolidates the duplicated transport, codec, protocol-model,
and deserializer code previously spread across beam-crawler, tx-monitor,
and beam-node-sync.

Current public surface:

- `NodeQueryClient` for staged header/body sync plus Beam core proof,
	state, asset, shielded, event, and contract queries exposed by the
	node protocol.
- Typed query response models and deserializers for YAS-encoded Beam
	payloads, including asset listings, Merkle proofs, contract enumeration,
	and state summaries.
