#!/usr/bin/python3

import unittest
from datetime import timedelta, datetime
import tcp_multi_connections
from tcp_multi_connections import StatusEnum
from unittest.mock import patch, Mock, MagicMock


class TestTcpMulitConnections(unittest.TestCase):
    """
    Test TCP mulit-Connections test script
    """

    def test_format_output_pass(self):
        """
        Test if port test pass.
        """
        dict_status = {
            0: {"time": timedelta(seconds=5), "status": True},
            1: {"time": timedelta(seconds=10), "status": True},
            2: {"time": timedelta(seconds=3), "status": True},
        }
        result = tcp_multi_connections.format_output(
            port=123, message="", dict_status=dict_status
        )

        self.assertEqual(result["port"], 123)
        self.assertEqual(result["status"], StatusEnum.SUCCESS)
        self.assertEqual(result["message"], "Received payload correct!")
        self.assertEqual(result["fail"], None)
        self.assertEqual(result["port_period"], timedelta(seconds=18))
        self.assertEqual(result["avg_period"], timedelta(seconds=6))
        self.assertEqual(result["max_period"], timedelta(seconds=10))
        self.assertEqual(result["min_period"], timedelta(seconds=3))

    def test_format_output_fail(self):
        """
        Test if port test fail.
        """
        dict_status = {
            0: {"time": timedelta(seconds=5), "status": True},
            1: {"time": timedelta(seconds=10), "status": False},
            2: {"time": timedelta(seconds=3), "status": True},
        }
        result = tcp_multi_connections.format_output(
            port=123, message="", dict_status=dict_status
        )

        self.assertEqual(result["port"], 123)
        self.assertEqual(result["status"], StatusEnum.FAIL)
        self.assertEqual(result["message"], "Received payload incorrect!")
        self.assertEqual(
            result["fail"], [{"time": timedelta(seconds=10), "status": False}]
        )
        self.assertEqual(result["port_period"], timedelta(seconds=18))
        self.assertEqual(result["avg_period"], timedelta(seconds=6))
        self.assertEqual(result["max_period"], timedelta(seconds=10))
        self.assertEqual(result["min_period"], timedelta(seconds=3))

    def test_generate_result_error(self):
        """
        Test if port test with error.
        """
        result = tcp_multi_connections.format_output(
            port=123, message="Connection error!"
        )

        self.assertEqual(result["port"], 123)
        self.assertEqual(result["status"], StatusEnum.ERROR)
        self.assertEqual(result["message"], "Connection error!")
        self.assertEqual(result["fail"], None)
        self.assertEqual(result["port_period"], None)
        self.assertEqual(result["avg_period"], None)
        self.assertEqual(result["max_period"], None)
        self.assertEqual(result["min_period"], None)

    def test_send_payload_connection_refused(self):
        """
        Test connections refused.
        """
        payload = "test"
        host = "0.0.0.0"
        port = "1234"
        start_time = datetime.now() + timedelta(seconds=1)
        results = []
        result = tcp_multi_connections.send_payload(
            host, port, payload, start_time, results
        )
        log = "Connection refused"
        self.assertIn(log, result[0]["message"])

    @patch("socket.create_connection")
    def test_send_payload_success(
        self,
        mock_create_connection,
    ):
        """
        Test send_paylaod success and receive expect payload.
        """
        payload = "test"
        host = "0.0.0.0"
        port = "1234"
        start_time = datetime.now() + timedelta(seconds=1)
        results = []
        mock_socket = Mock(recv=Mock(return_value=payload.encode()))
        mock_create_connection.return_value.__enter__.return_value = (
            mock_socket
        )

        result = tcp_multi_connections.send_payload(
            host, port, payload, start_time, results
        )
        self.assertEqual(result[0]["status"], StatusEnum.SUCCESS)
        self.assertEqual(result[0]["port"], "1234")

    @patch("socket.create_connection")
    def test_send_payload_fail(
        self,
        mock_create_connection,
    ):
        """
        Test send_paylaod success and receive unexpect payload.
        """
        payload = "test"
        host = "0.0.0.0"
        port = "1234"
        start_time = datetime.now() + timedelta(seconds=1)
        results = []
        mock_socket = Mock(recv=Mock(return_value="unexpect".encode()))
        mock_create_connection.return_value.__enter__.return_value = (
            mock_socket
        )

        result = tcp_multi_connections.send_payload(
            host, port, payload, start_time, results
        )
        self.assertEqual(result[0]["status"], StatusEnum.FAIL)
        self.assertEqual(result[0]["port"], "1234")


if __name__ == "__main__":
    unittest.main()
