import unittest
from unittest.mock import patch, MagicMock
from gateway_ping_test import main


class TestMainFunction(unittest.TestCase):
    @patch("gateway_ping_test.get_host_to_ping")
    @patch("gateway_ping_test.ping")
    def test_no_internet_connection(self, mock_ping, mock_get_host_to_ping):
        mock_ping.return_value = {"received": 0}
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
