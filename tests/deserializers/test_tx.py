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

# --- deserialize_input ---


def test_deserialize_input_happy():
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


def test_deserialize_input_underflow():
    # Empty buffer
    with pytest.raises(DeserializationError):
        deserialize_input(BufferReader(b""))

    # Only flags, no point
    with pytest.raises(DeserializationError):
        deserialize_input(BufferReader(bytes([1])))


# --- deserialize_output ---


def test_deserialize_output_individual_flags():
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

        # Map flag -> (data, expected_attribute, expected_value)
        # Note: all outputs start with commitment (32 bytes)
        test_cases = [
            (0x00, bytes([0]) + b"a" * 32, "commitment", EcPoint(x="61" * 32, y=False)),
            (0x01, bytes([1]) + b"a" * 32, "commitment", EcPoint(x="61" * 32, y=True)),
            (0x02, bytes([2]) + b"a" * 32, "coinbase", True),
            (0x04, bytes([4]) + b"a" * 32, "confidential_proof", "conf_proof"),
            (0x08, bytes([8]) + b"a" * 32, "public_proof", "pub_proof"),
            (0x10, bytes([0x10]) + b"a" * 32 + bytes([0x8A]), "incubation", 10),
            (0x20, bytes([0x20]) + b"a" * 32, "asset_proof", "asset_proof"),
            (0x80, bytes([0x80]) + b"a" * 32 + bytes([42]), "extra_flags", 42),
        ]

        for flag, data, attr, expected in test_cases:
            reader = BufferReader(data)
            result = deserialize_output(reader)
            assert getattr(result, attr) == expected


def test_deserialize_output_maximal():
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

        # 0x01 | 0x02 | 0x04 | 0x08 | 0x10 | 0x20 | 0x80 = 0xBF
        data = bytes([0xBF]) + b"a" * 32 + bytes([0x8A]) + bytes([42])
        reader = BufferReader(data)
        result = deserialize_output(reader)

        assert result == TxOutput(
            commitment=EcPoint(x="61" * 32, y=True),
            coinbase=True,
            confidential_proof="conf_proof",
            public_proof="pub_proof",
            incubation=10,
            asset_proof="asset_proof",
            extra_flags=42,
        )


def test_deserialize_output_underflow():
    with (
        patch("beam_p2p.deserializers.tx.deserialize_confidential_range_proof"),
        patch("beam_p2p.deserializers.tx.deserialize_public_range_proof"),
        patch("beam_p2p.deserializers.tx.deserialize_asset_proof"),
    ):
        # Empty
        with pytest.raises(DeserializationError):
            deserialize_output(BufferReader(b""))

        # Flag set, but no point
        with pytest.raises(DeserializationError):
            deserialize_output(BufferReader(bytes([0x01])))

        # Incubation flag set, but no var_uint
        with pytest.raises(DeserializationError):
            deserialize_output(BufferReader(bytes([0x10]) + b"a" * 32))

        # Extra flags set, but no u8
        with pytest.raises(DeserializationError):
            deserialize_output(BufferReader(bytes([0x80]) + b"a" * 32))


# --- deserialize_transaction ---


def test_deserialize_transaction_empty():
    with (
        patch("beam_p2p.deserializers.tx.deserialize_input"),
        patch("beam_p2p.deserializers.tx.deserialize_output"),
        patch("beam_p2p.deserializers.tx.deserialize_kernel"),
    ):
        # 0 in, 0 out, 0 kern, offset 32 bytes
        data = (
            (0).to_bytes(4, "big")
            + (0).to_bytes(4, "big")
            + (0).to_bytes(4, "big")
            + b"o" * 32
        )
        reader = BufferReader(data)
        result = deserialize_transaction(reader)
        assert result.counts == TxCounts(
            inputs=0, outputs=0, kernels=0, kernels_mixed=False
        )
        assert result.offset == "6f" * 32


def test_deserialize_transaction_kernel_boundaries():
    with (
        patch("beam_p2p.deserializers.tx.deserialize_input"),
        patch("beam_p2p.deserializers.tx.deserialize_output"),
        patch("beam_p2p.deserializers.tx.deserialize_kernel") as mock_kern,
    ):
        mock_kern.return_value = "kern"

        # Case 1: Mixed=False, Count=0
        data = (0).to_bytes(4, "big") * 3 + b"o" * 32
        result = deserialize_transaction(BufferReader(data))
        assert result.counts.kernels_mixed is False
        assert result.counts.kernels == 0
        # Note: deserialize_kernel is not called for count 0, so we can't check assume_std here.
        # However, the loop logic is simple. Let's test count 1.

        # Case 2: Mixed=False, Count=1
        data = (
            (0).to_bytes(4, "big")
            + (0).to_bytes(4, "big")
            + (1).to_bytes(4, "big")
            + b"o" * 32
        )
        result = deserialize_transaction(BufferReader(data))
        assert result.counts.kernels_mixed is False
        mock_kern.assert_called_with(ANY, assume_std=True)

        # Case 3: Mixed=True, Count=0
        mixed_zero = 1 << 31
        data = (
            (0).to_bytes(4, "big")
            + (0).to_bytes(4, "big")
            + mixed_zero.to_bytes(4, "big")
            + b"o" * 32
        )
        result = deserialize_transaction(BufferReader(data))
        assert result.counts.kernels_mixed is True
        assert result.counts.kernels == 0

        # Case 4: Mixed=True, Count=1
        mixed_one = (1 << 31) | 1
        data = (
            (0).to_bytes(4, "big")
            + (0).to_bytes(4, "big")
            + mixed_one.to_bytes(4, "big")
            + b"o" * 32
        )
        result = deserialize_transaction(BufferReader(data))
        assert result.counts.kernels_mixed is True
        mock_kern.assert_called_with(ANY, assume_std=False)


def test_deserialize_transaction_underflow():
    # Buffer ends during count reads
    with pytest.raises(DeserializationError):
        deserialize_transaction(BufferReader(b""))

    with pytest.raises(DeserializationError):
        deserialize_transaction(BufferReader((1).to_bytes(4, "big")))

    # Buffer ends before offset
    with (
        patch("beam_p2p.deserializers.tx.deserialize_input"),
        patch("beam_p2p.deserializers.tx.deserialize_output"),
        patch("beam_p2p.deserializers.tx.deserialize_kernel"),
    ):
        # 0, 0, 0, but missing the scalar offset
        data = (0).to_bytes(4, "big") * 3
        with pytest.raises(DeserializationError):
            deserialize_transaction(BufferReader(data))


# --- deserialize_new_transaction_payload ---


@pytest.mark.parametrize(
    "t_pres, c_pres, fluff",
    [
        (True, True, True),
        (True, True, False),
        (True, False, True),
        (True, False, False),
        (False, True, True),
        (False, True, False),
        (False, False, True),
        (False, False, False),
    ],
)
def test_deserialize_new_transaction_payload_matrix(t_pres, c_pres, fluff):
    with patch("beam_p2p.deserializers.tx.deserialize_transaction") as mock_tx:
        mock_tx_obj = MagicMock(spec=Transaction)
        mock_tx.return_value = mock_tx_obj

        # Build data
        data = bytes([1 if t_pres else 0])
        if t_pres:
            data += b"tx_data"
        data += bytes([1 if c_pres else 0])
        if c_pres:
            data += b"c" * 32
        data += bytes([1 if fluff else 0])

        def side_effect(reader):
            if t_pres:
                reader.read_bytes(len(b"tx_data"))
            return mock_tx_obj

        mock_tx.side_effect = side_effect

        result = deserialize_new_transaction_payload(data)
        assert result.transaction_present is t_pres
        assert result.transaction == (mock_tx_obj if t_pres else None)
        assert result.context == ("63" * 32 if c_pres else None)
        assert result.fluff is fluff


def test_deserialize_new_transaction_payload_underflow():
    # Not enough bytes for initial flags
    with pytest.raises(DeserializationError):
        deserialize_new_transaction_payload(b"")

    # t_pres=True but no tx data
    with patch("beam_p2p.deserializers.tx.deserialize_transaction") as mock_tx:
        mock_tx.side_effect = DeserializationError("Underflow")
        data = bytes(
            [1, 0, 0]
        )  # t_pres=True, c_pres=False, fluff=False, but no tx data
        with pytest.raises(DeserializationError):
            deserialize_new_transaction_payload(data)

    # c_pres=True but no hash32
    data = bytes([0, 1, 0])  # t_pres=False, c_pres=True, fluff=False, but no hash32
    with pytest.raises(DeserializationError):
        deserialize_new_transaction_payload(data)

    # missing fluff bit
    data = bytes([0, 0])  # t_pres=False, c_pres=False, missing fluff
    with pytest.raises(DeserializationError):
        deserialize_new_transaction_payload(data)


def test_deserialize_new_transaction_payload_trailing_bytes():
    # Valid payload + extra
    data = bytes([0, 0, 0]) + b"extra"
    with pytest.raises(DeserializationError, match=r"trailing byte\(s\) left"):
        deserialize_new_transaction_payload(data)
