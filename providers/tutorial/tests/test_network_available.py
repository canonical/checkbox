import unittest
import textwrap
from unittest import mock

import network_available


class TestNetworkAvailable(unittest.TestCase):

    @mock.patch("subprocess.check_output")
    def test_nominal(self, check_output_mock):
        check_output_mock.return_value = textwrap.dedent(
            """
            PING 1.1.1.1 (1.1.1.1) from 192.168.1.100 wlan0: 56(84) bytes
            64 bytes from 1.1.1.1: icmp_seq=1 ttl=53 time=39.0 ms
            64 bytes from 1.1.1.1: icmp_seq=2 ttl=53 time=143 ms

            --- 1.1.1.1 ping statistics ---
            2 packets transmitted, 2 received, 0% packet loss, time 170ms
            rtt min/avg/max/mdev = 34.980/60.486/142.567/31.077 ms
            """
        ).strip()
        network_available.network_available("wlan0", "90")
        self.assertTrue(check_output_mock.called)

    @mock.patch("subprocess.check_output")
    def test_failure(self, check_output_mock):
        check_output_mock.return_value = textwrap.dedent(
            """
            PING 1.1.1.1 (1.1.1.1) from 192.168.1.100 wlan0: 56(84) bytes
            64 bytes from 1.1.1.1: icmp_seq=1 ttl=53 time=39.0 ms

            --- 1.1.1.1 ping statistics ---
            10 packets transmitted, a received, 90% packet loss, time 170ms
            rtt min/avg/max/mdev = 34.980/60.486/142.567/31.077 ms
            """
        ).strip()
        with self.assertRaises(SystemExit):
            network_available.network_available("wlan0", "0")


class TestMain(unittest.TestCase):

    @mock.patch("subprocess.check_output")
    def test_nominal(self, check_output_mock):
        check_output_mock.return_value = textwrap.dedent(
            """
            PING 1.1.1.1 (1.1.1.1) from 192.168.1.100 wlan0: 56(84) bytes
            64 bytes from 1.1.1.1: icmp_seq=1 ttl=53 time=39.0 ms
            64 bytes from 1.1.1.1: icmp_seq=2 ttl=53 time=143 ms

            --- 1.1.1.1 ping statistics ---
            2 packets transmitted, 2 received, 0% packet loss, time 170ms
            rtt min/avg/max/mdev = 34.980/60.486/142.567/31.077 ms
            """
        ).strip()
        network_available.main(["--threshold", "20", "wlan0"])
        self.assertTrue(check_output_mock.called)
