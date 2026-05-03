from unittest.mock import ANY, MagicMock, patch

import pytest

from beam_p2p.deserializers.core import BufferReader, DeserializationError
from beam_p2p.deserializers.tx import (
    deserialize_input,
    deserialize_new_transaction_payload,
    deserialize_output,
    deserialize_transaction,
)
from beam_p2p.protocol_models import (
    EcPoint,
    NewTransactionPayload,
    Transaction,
    TxCounts,
    TxInput,
    TxOutput,
)


def test_deserialize_input():
    # Case 1: Flag 1 set -> y_flag = True
    data = bytes([1]) + b"a" * 32
    reader = BufferReader(data)
    result = deserialize_input(reader)
    assert result == TxInput(commitment=EcPoint(x="61" * 32, y=True))

    # Case 2: Flag 1 not set -> y_flag = False
    data = bytes([0]) + b"a" * 32
    reader = BufferReader(data)
    result = deserialize_input(reader)
    assert result == TxInput(commitment=EcPoint(x="61" * 32, y=False))


def test_deserialize_output():
    # We mock the complex proof deserializers
    with (
        patch(
            "beam_p2p.deserializers.tx.deserialize_confidential_range_proof"
        ) as mock_conf,
        patch("beam_p2p.deserializers.tx.deserialize_public_range_proof") as mock_pub,
        patch("beam_p2p.deserializers.tx.deserialize_asset_proof") as mock_asset,
    ):
        mock_conf.return_value = "conf_proof"
        mock_pub.return_value = "pub_proof"
        mock_asset.return_value = "asset_proof"

        # Case 1: Minimal output (commitment only, no flags)
        data = bytes([0]) + b"a" * 32
        reader = BufferReader(data)
        result = deserialize_output(reader)
        assert result == TxOutput(
            commitment=EcPoint(x="61" * 32, y=False),
            coinbase=False,
            confidential_proof=None,
            public_proof=None,
            incubation=None,
            asset_proof=None,
            extra_flags=None,
        )

        # Case 2: Coinbase and point-y (flags 1 | 2 = 3)
        data = bytes([3]) + b"a" * 32
        reader = BufferReader(data)
        result = deserialize_output(reader)
        assert result == TxOutput(
            commitment=EcPoint(x="61" * 32, y=True),
            coinbase=True,
            confidential_proof=None,
            public_proof=None,
            incubation=None,
            asset_proof=None,
            extra_flags=None,
        )

        # Case 3: Complex output with proofs and incubation (flags 1 | 4 | 8 | 0x10 | 0x20)
        # 1 | 4 | 8 | 16 | 32 = 61
        # For incubation, we need a var_uint. 10 encoded with high-bit set = 0x8A.
        data = bytes([61]) + b"a" * 32 + bytes([0x8A])
        reader = BufferReader(data)
        result = deserialize_output(reader)
        assert result == TxOutput(
            commitment=EcPoint(x="61" * 32, y=True),
            coinbase=False,
            confidential_proof="conf_proof",
            public_proof="pub_proof",
            incubation=10,
            asset_proof="asset_proof",
            extra_flags=None,
        )

        # Case 4: With extra flags (flag 0x80)
        # flags = 0x80 | 1 = 129
        data = bytes([129]) + b"a" * 32 + bytes([42])
        reader = BufferReader(data)
        result = deserialize_output(reader)
        assert result == TxOutput(
            commitment=EcPoint(x="61" * 32, y=True),
            coinbase=False,
            confidential_proof=None,
            public_proof=None,
            incubation=None,
            asset_proof=None,
            extra_flags=42,
        )


def test_deserialize_transaction():
    with (
        patch("beam_p2p.deserializers.tx.deserialize_input") as mock_in,
        patch("beam_p2p.deserializers.tx.deserialize_output") as mock_out,
        patch("beam_p2p.deserializers.tx.deserialize_kernel") as mock_kern,
    ):
        mock_in.side_effect = [
            TxInput(EcPoint("x1", True)),
            TxInput(EcPoint("x2", True)),
        ]
        mock_out.side_effect = [
            TxOutput(EcPoint("ox1", True), False),
            TxOutput(EcPoint("ox2", True), False),
        ]
        mock_kern.side_effect = ["kern1", "kern2"]

        # 2 inputs, 2 outputs, 2 kernels (not mixed), offset = 32 bytes
        # input_count: 2 (4 bytes big)
        # output_count: 2 (4 bytes big)
        # kernel_count_raw: 2 (4 bytes big)
        # offset: 32 bytes
        # Note: mocks don't consume reader bytes, so no per-item data between counts
        data = (
            (2).to_bytes(4, "big")
            + (2).to_bytes(4, "big")
            + (2).to_bytes(4, "big")
            + b"o" * 32
        )
        reader = BufferReader(data)
        result = deserialize_transaction(reader)

        assert result.counts == TxCounts(
            inputs=2, outputs=2, kernels=2, kernels_mixed=False
        )
        assert result.inputs == [
            TxInput(EcPoint("x1", True)),
            TxInput(EcPoint("x2", True)),
        ]
        assert result.outputs == [
            TxOutput(EcPoint("ox1", True), False),
            TxOutput(EcPoint("ox2", True), False),
        ]
        assert result.kernels == ["kern1", "kern2"]
        assert result.offset == "6f" * 32  # "o" * 32 in hex

        # Verify deserialize_kernel was called with assume_std=True (since not mixed)
        mock_kern.assert_called_with(ANY, assume_std=True)


def test_deserialize_transaction_mixed_kernels():
    with (
        patch("beam_p2p.deserializers.tx.deserialize_input") as mock_in,
        patch("beam_p2p.deserializers.tx.deserialize_output") as mock_out,
        patch("beam_p2p.deserializers.tx.deserialize_kernel") as mock_kern,
    ):
        mock_in.return_value = TxInput(EcPoint("x", True))
        mock_out.return_value = TxOutput(EcPoint("x", True), False)
        mock_kern.return_value = "kern"

        # 1 input, 1 output, 1 kernel (mixed)
        # kernel_count_raw = 1 | (1 << 31)
        kernel_count_raw = 1 | (1 << 31)
        # Note: mocks don't consume reader bytes, so no per-item data between counts
        data = (
            (1).to_bytes(4, "big")
            + (1).to_bytes(4, "big")
            + kernel_count_raw.to_bytes(4, "big")
            + b"o" * 32
        )
        reader = BufferReader(data)
        result = deserialize_transaction(reader)

        assert result.counts == TxCounts(
            inputs=1, outputs=1, kernels=1, kernels_mixed=True
        )
        # Verify deserialize_kernel was called with assume_std=False (since mixed)
        mock_kern.assert_called_with(ANY, assume_std=False)


def test_deserialize_new_transaction_payload():
    # We mock deserialize_transaction to avoid constructing a full transaction buffer
    with patch("beam_p2p.deserializers.tx.deserialize_transaction") as mock_tx:
        mock_tx_obj = MagicMock(spec=Transaction)
        mock_tx.return_value = mock_tx_obj

        # Case 1: Transaction present, context present, fluff True
        # trans_pres: True (1), context_pres: True (1), fluff: True (1)
        # context: 32 bytes
        data = bytes([1]) + b"tx_data" + bytes([1]) + b"c" * 32 + bytes([1])

        def side_effect(reader):
            reader.read_bytes(len(b"tx_data"))
            return mock_tx_obj

        mock_tx.side_effect = side_effect

        result = deserialize_new_transaction_payload(data)
        assert result.transaction_present is True
        assert result.transaction == mock_tx_obj
        assert result.context == "63" * 32  # "c" * 32 in hex
        assert result.fluff is True

        # Case 2: Transaction absent, context absent, fluff False
        # trans_pres: False (0), context_pres: False (0), fluff: False (0)
        data2 = bytes([0, 0, 0])
        result2 = deserialize_new_transaction_payload(data2)
        assert result2.transaction_present is False
        assert result2.transaction is None
        assert result2.context is None
        assert result2.fluff is False


def test_deserialize_new_transaction_payload_trailing_bytes():
    # Case: Trailing bytes should raise DeserializationError
    data = bytes([0, 0, 0]) + b"trailing"
    with pytest.raises(DeserializationError, match=r"trailing byte\(s\) left"):
        deserialize_new_transaction_payload(data)
