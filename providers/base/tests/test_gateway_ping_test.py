import unittest
from unittest.mock import patch
from gateway_ping_test import main, parse_args


class TestMainFunction(unittest.TestCase):
    @patch("gateway_ping_test.get_host_to_ping")
    @patch("gateway_ping_test.ping")
    def test_no_internet_connection_no_cause(
        self, mock_ping, mock_get_host_to_ping
    ):
        mock_get_host_to_ping.return_value = None
        mock_ping.return_value = None
        result = main(["1.1.1.1"])
        self.assertEqual(result, 1)

    @patch("gateway_ping_test.get_host_to_ping")
    @patch("gateway_ping_test.ping")
    def test_no_internet_connection_cause(
        self, mock_ping, mock_get_host_to_ping
    ):
        mock_ping.return_value = {"received": 0, "cause": "Test cause"}
        result = main(["1.1.1.1"])
        self.assertEqual(result, 1)

    @patch("gateway_ping_test.get_host_to_ping")
    @patch("gateway_ping_test.ping")
    def test_packet_loss_within_threshold(
        self, mock_ping, mock_get_host_to_ping
    ):
        mock_ping.return_value = {
            "transmitted": 100,
            "received": 95,
            "pct_loss": 5,
        }
        result = main(["1.1.1.1", "-t", "10"])
        self.assertEqual(result, 0)

    @patch("gateway_ping_test.get_host_to_ping")
    @patch("gateway_ping_test.ping")
    def test_packet_loss_exceeding_threshold(
        self, mock_ping, mock_get_host_to_ping
    ):
        mock_ping.return_value = {
            "transmitted": 100,
            "received": 80,
            "pct_loss": 20,
        }
        result = main(["1.1.1.1", "-t", "10"])
        self.assertEqual(result, 1)

    @patch("gateway_ping_test.get_host_to_ping")
    @patch("gateway_ping_test.ping")
    def test_full_connectivity(self, mock_ping, mock_get_host_to_ping):
        mock_ping.return_value = {
            "transmitted": 100,
            "received": 100,
            "pct_loss": 0,
        }
        result = main(["1.1.1.1"])
        self.assertEqual(result, 0)

    @patch("gateway_ping_test.get_host_to_ping")
    @patch("gateway_ping_test.ping")
    def test_verbose_output(self, mock_ping, mock_get_host_to_ping):
        mock_ping.return_value = {
            "transmitted": 100,
            "received": 100,
            "pct_loss": 0,
        }
        result = main(["1.1.1.1", "-v"])
        self.assertEqual(result, 0)

    @patch("gateway_ping_test.get_host_to_ping")
    @patch("gateway_ping_test.ping")
    def test_invalid_arguments_count_deadline(
        self, mock_ping, mock_get_host_to_ping
    ):
        with self.assertRaises(SystemExit):
            main(["-c", "10", "-d", "8"])

    def test_adjust_count_based_on_non_default_deadline(self):
        # Assuming default_delay is 4
        args = parse_args(["-d", "1", "-v"])
        self.assertEqual(
            args.count,
            1,
            "Count should be adjusted based on the non-default deadline",
        )
