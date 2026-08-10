#!/usr/bin/env python3
# Copyright 2024 Canonical Ltd.
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License version 3,
# as published by the Free Software Foundation.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import unittest
import socket
import subprocess
import threading
from unittest.mock import patch, mock_open, Mock, call
from contextlib import redirect_stdout, redirect_stderr
from io import StringIO
from pathlib import Path
from subprocess import CalledProcessError
from argparse import Namespace

import network


class IPerfPerfomanceTestTests(unittest.TestCase):
    def test_extract_core_list_single(self):
        """Tests parsing a NUMA node CPUs list with a single CPU."""
        line = "NUMA node0 CPU(s): 0"
        core_list = network.IPerfPerformanceTest.extract_core_list(None, line)
        self.assertListEqual(core_list, [0])

    def test_extract_core_list_range(self):
        """Tests parsing a NUMA node CPUs list."""
        line = "NUMA node0 CPU(s): 0-2"
        core_list = network.IPerfPerformanceTest.extract_core_list(None, line)
        self.assertListEqual(core_list, [0, 1, 2])

    def test_extract_core_list_empty(self):
        """Tests that parsing an empty NUMA node CPUs does not crash."""
        line = "NUMA node0 CPU(s):"
        core_list = network.IPerfPerformanceTest.extract_core_list(None, line)
        self.assertListEqual(core_list, [])

    def test_find_numa_reports_node(self):
        with patch("pathlib.Path.open", mock_open(read_data="1")):
            returned = network.IPerfPerformanceTest.find_numa(None, "device")
            self.assertEqual(returned, 1)

    def test_find_numa_minus_one_from_sysfs(self):
        with patch("pathlib.Path.open", mock_open(read_data="-1")) as mo:
            returned = network.IPerfPerformanceTest.find_numa(None, "device")
            self.assertEqual(returned, -1)

    def test_find_numa_numa_node_not_found(self):
        with patch("pathlib.Path.open", mock_open()) as mo:
            mo.side_effect = FileNotFoundError
            returned = network.IPerfPerformanceTest.find_numa(None, "device")
            self.assertEqual(returned, -1)

    def make_iperf_test(self, **overrides):
        """Build a real IPerfPerformanceTest with Interface() mocked out
        (Interface opens a raw socket, which we don't want in unit tests)."""
        kwargs = dict(
            interface="eth0",
            target="192.168.1.1",
            fail_threshold=40,
            cpu_load_fail_threshold=100,
            iperf3=True,
            num_threads=2,
            reverse=False,
        )
        kwargs.update(overrides)
        with patch("network.Interface"):
            return network.IPerfPerformanceTest(**kwargs)

    def test_init_sets_attributes(self):
        test = self.make_iperf_test(num_threads=5, target="10.0.0.1")
        self.assertEqual(test.target, "10.0.0.1")
        self.assertEqual(test.num_threads, 5)
        self.assertListEqual(test._results, [])

    def test_run_one_thread_success(self):
        test = self.make_iperf_test()
        with patch("network.check_output", return_value="100 Mbits/sec"):
            test.run_one_thread("iperf3 -c host", 5201)
        self.assertEqual(test._results, ["100 Mbits/sec"])

    def test_run_one_thread_timeout_keeps_partial_output(self):
        test = self.make_iperf_test()
        exc = CalledProcessError(124, "cmd")
        exc.output = "partial output"
        with patch("network.check_output", side_effect=exc):
            test.run_one_thread("iperf3 -c host", 5201)
        self.assertEqual(test._results, ["partial output"])

    def test_run_one_thread_unable_to_connect(self):
        test = self.make_iperf_test()
        exc = CalledProcessError(1, "cmd")
        exc.output = "unable to connect to server"
        with patch("network.check_output", side_effect=exc):
            result = test.run_one_thread("iperf3 -c host", 5201)
        self.assertEqual(result, 1)
        self.assertListEqual(test._results, [])

    @patch("logging.warning")
    def test_run_one_thread_unable_to_connect_high_speed_port(self, mock_warn):
        test = self.make_iperf_test()
        exc = CalledProcessError(1, "cmd")
        exc.output = "unable to connect to server"
        with patch("network.check_output", side_effect=exc):
            result = test.run_one_thread("iperf3 -c host", 5202)
        self.assertEqual(result, 1)
        self.assertTrue(mock_warn.called)

    def test_run_one_thread_unknown_error(self):
        test = self.make_iperf_test()
        exc = CalledProcessError(1, "cmd")
        exc.output = "some other failure"
        with patch("network.check_output", side_effect=exc):
            result = test.run_one_thread("iperf3 -c host", 5201)
        self.assertEqual(result, 1)

    def test_run_one_thread_is_thread_safe(self):
        """Runs many threads concurrently and checks that no results are
        lost due to a race condition on self._results."""
        test = self.make_iperf_test()
        num_threads = 25
        with patch("network.check_output", return_value="10 Mbits/sec"):
            threads = [
                threading.Thread(
                    target=test.run_one_thread,
                    args=("iperf3 -c host", 5200 + i),
                )
                for i in range(num_threads)
            ]
            for th in threads:
                th.start()
            for th in threads:
                th.join()
        self.assertEqual(len(test._results), num_threads)

    def test_summarize_speeds_with_data(self):
        test = self.make_iperf_test()
        test._results = [
            "[ 1] 0.0-1.0 sec  10 MBytes  80 Mbits/sec\n"
            "[SUM] 0.0-1.0 sec 10 MBytes 80 Mbits/sec sender"
        ]
        throughput = test.summarize_speeds()
        self.assertEqual(throughput, 80.0)

    def test_summarize_speeds_no_matches(self):
        test = self.make_iperf_test()
        test._results = ["no useful data here"]
        self.assertEqual(test.summarize_speeds(), 0)

    def test_summarize_cpu_with_data(self):
        test = self.make_iperf_test()
        test._results = [
            "CPU Utilization: local/sender 45.3% (1.2%u/44.1%s), "
            "remote/receiver 12.0% (...)"
        ]
        self.assertEqual(test.summarize_cpu(), 45.3)

    def test_summarize_cpu_no_data(self):
        test = self.make_iperf_test()
        test._results = ["no cpu info here"]
        self.assertEqual(test.summarize_cpu(), 0.0)

    def test_find_cores_found(self):
        test = self.make_iperf_test()
        lscpu_output = "NUMA node0 CPU(s):    0-3\nNUMA node1 CPU(s):    4-7\n"
        with patch("network.check_output", return_value=lscpu_output):
            cores = test.find_cores(1)
        self.assertEqual(cores, [4, 5, 6, 7])

    def test_find_cores_not_found(self):
        test = self.make_iperf_test()
        with patch("network.check_output", return_value=""):
            cores = test.find_cores(5)
        self.assertEqual(cores, [])

    def test_run_wireless_zero_max_speed_passes(self):
        """When max_speed is 0 (e.g. WiFi), a ZeroDivisionError while
        computing percent is caught and the test is considered passed."""
        test = self.make_iperf_test(num_threads=1, iperf3=False)
        test.iface.max_speed = 0
        with patch("network.check_output", return_value="1000 Mbits/sec"):
            result = test.run()
        self.assertEqual(result, 0)

    def test_run_iperf3_multithread_passes(self):
        test = self.make_iperf_test(
            num_threads=3, iperf3=True, fail_threshold=1
        )
        test.iface.max_speed = 1000
        # Per-interval lines (used by summarize_speeds) plus a "sender"
        # summary line, which is stripped out before parsing speeds.
        output = (
            "[ 5]   0.00-1.00 sec  118 MBytes   990 Mbits/sec\n"
            "[ 5]   1.00-2.00 sec  117 MBytes   983 Mbits/sec\n"
            "[ 5]   0.00-10.00 sec 1.15 GBytes  987 Mbits/sec  sender\n"
            "CPU Utilization: local/sender 10.0% (1.2%u/8.8%s)"
        )
        with patch.object(test, "find_numa", return_value=0), patch.object(
            test, "find_cores", return_value=[0, 1]
        ), patch("network.check_output", return_value=output):
            result = test.run()
        self.assertIsNone(result)

    def test_run_below_fail_threshold_returns_30(self):
        test = self.make_iperf_test(
            num_threads=1, iperf3=False, fail_threshold=90
        )
        test.iface.max_speed = 1000
        with patch("network.check_output", return_value="1 Mbits/sec"):
            result = test.run()
        self.assertEqual(result, 30)

    def test_run_cpu_over_threshold_returns_30(self):
        test = self.make_iperf_test(
            num_threads=1,
            iperf3=True,
            cpu_load_fail_threshold=10,
            fail_threshold=0,
        )
        test.iface.max_speed = 1000
        output = (
            "1000 Mbits/sec sender\n"
            "CPU Utilization: local/sender 99.0% (...)"
        )
        with patch.object(test, "find_numa", return_value=-1), patch(
            "network.check_output", return_value=output
        ):
            result = test.run()
        self.assertEqual(result, 30)

    def test_run_with_run_time_uses_reverse_flag(self):
        test = self.make_iperf_test(
            num_threads=1, iperf3=False, fail_threshold=0
        )
        test.iface.max_speed = 1000
        test.run_time = 10
        test.reverse = True
        with patch(
            "network.check_output", return_value="1000 Mbits/sec"
        ) as mock_run:
            result = test.run()
        self.assertIsNone(result)
        called_cmd = mock_run.call_args[0][0]
        self.assertIn("-R", called_cmd)

    def test_optimize_num_threads(self):
        test = self.make_iperf_test(num_threads=4)
        orig_run_time = test.run_time
        orig_scan_timeout = test.scan_timeout
        with patch.object(
            test, "run", return_value=None
        ) as mock_run, patch.object(
            test, "summarize_speeds", side_effect=[10, 20, 15, 5]
        ):
            test.optimize_num_threads()
        self.assertEqual(mock_run.call_count, 4)
        # Multiple 1 (index 1) had the highest reported throughput (20)
        self.assertEqual(test.num_threads, 4)
        self.assertEqual(test.run_time, orig_run_time)
        self.assertEqual(test.scan_timeout, orig_scan_timeout)


class StressPerformanceTestTests(unittest.TestCase):
    @patch("subprocess.Popen")
    def test_run_success_no_issues(self, mock_popen):
        iperf_mock = Mock(returncode=0)
        iperf_mock.communicate.return_value = (None, None)
        ping_mock = Mock()
        ping_mock.communicate.return_value = (
            b"64 bytes: icmp_seq=1 ttl=64 time=10 ms\n",
            b"",
        )
        mock_popen.side_effect = [iperf_mock, ping_mock]

        test = network.StressPerformanceTest("eth0", "192.168.1.1", False)
        with redirect_stdout(StringIO()):
            result = test.run()
        self.assertEqual(result, 0)
        self.assertEqual(ping_mock.terminate.call_count, 1)

    @patch("subprocess.Popen")
    def test_run_iperf3_command_used(self, mock_popen):
        iperf_mock = Mock(returncode=0)
        iperf_mock.communicate.return_value = (None, None)
        ping_mock = Mock()
        ping_mock.communicate.return_value = (b"", b"")
        mock_popen.side_effect = [iperf_mock, ping_mock]

        test = network.StressPerformanceTest("eth0", "192.168.1.1", True)
        with redirect_stdout(StringIO()):
            test.run()
        iperf_cmd = mock_popen.call_args_list[0][0][0]
        self.assertIn("iperf3", iperf_cmd)

    @patch("subprocess.Popen")
    def test_run_iperf_fail_returns_nonzero(self, mock_popen):
        iperf_mock = Mock(returncode=5)
        iperf_mock.communicate.return_value = (None, None)
        ping_mock = Mock()
        ping_mock.communicate.return_value = (b"", b"")
        mock_popen.side_effect = [iperf_mock, ping_mock]

        test = network.StressPerformanceTest("eth0", "192.168.1.1", False)
        with redirect_stdout(StringIO()):
            result = test.run()
        self.assertEqual(result, 5)

    @patch("subprocess.Popen")
    def test_run_ping_delay_detected(self, mock_popen):
        iperf_mock = Mock(returncode=0)
        iperf_mock.communicate.return_value = (None, None)
        ping_mock = Mock()
        ping_mock.communicate.return_value = (b"time=5000\n", b"")
        mock_popen.side_effect = [iperf_mock, ping_mock]

        test = network.StressPerformanceTest("eth0", "192.168.1.1", False)
        with redirect_stdout(StringIO()):
            result = test.run()
        self.assertEqual(result, 1)

    @patch("subprocess.Popen")
    def test_run_ping_unreachable(self, mock_popen):
        iperf_mock = Mock(returncode=0)
        iperf_mock.communicate.return_value = (None, None)
        ping_mock = Mock()
        ping_mock.communicate.return_value = (
            b"Destination Host Unreachable\n",
            b"",
        )
        mock_popen.side_effect = [iperf_mock, ping_mock]

        test = network.StressPerformanceTest("eth0", "192.168.1.1", False)
        with redirect_stdout(StringIO()):
            result = test.run()
        self.assertEqual(result, 1)


class NetworkTests(unittest.TestCase):
    @patch("network.Interface")
    @patch("pathlib.Path.glob")
    def test_get_network_ifaces(self, mock_glob, mock_intf):
        path_list = [Path("eth0"), Path("eth1"), Path("eth2")]
        mock_glob.return_value = path_list
        mock_intf.side_effect = [
            Mock(status="up", phys_switch_id=None, iflink="2", ifindex="2"),
            Mock(status="up", phys_switch_id=None, iflink="3", ifindex="3"),
            Mock(status="down", phys_switch_id=None, iflink="4", ifindex="4"),
        ]

        expected_result = {
            "eth0": {
                "status": "up",
                "phys_switch_id": None,
                "iflink": "2",
                "ifindex": "2",
            },
            "eth1": {
                "status": "up",
                "phys_switch_id": None,
                "iflink": "3",
                "ifindex": "3",
            },
            "eth2": {
                "status": "down",
                "phys_switch_id": None,
                "iflink": "4",
                "ifindex": "4",
            },
        }

        with redirect_stdout(StringIO()):
            result = network.get_network_ifaces()

        self.assertDictEqual(result, expected_result)
        mock_glob.assert_called_with("*")
        mock_intf.assert_called_with(str(path_list[-1]))
        self.assertEqual(mock_intf.call_count, 3)

    @patch("network.check_call")
    def test_turn_down_network_success(self, mock_call):

        mock_call.return_value = 0
        with redirect_stdout(StringIO()):
            self.assertTrue(network.turn_down_network("test_if"))

        mock_call.assert_called_with(
            ["ip", "link", "set", "dev", "test_if", "down"]
        )

    @patch("network.check_call")
    def test_turn_down_network_fail(self, mock_call):

        mock_call.side_effect = CalledProcessError(1, "command failed")

        with redirect_stdout(StringIO()):
            self.assertFalse(network.turn_down_network("test_if"))

        mock_call.assert_called_with(
            ["ip", "link", "set", "dev", "test_if", "down"]
        )

    @patch("network.wait_for_iface_up")
    @patch("network.check_call")
    def test_turn_up_network_success(self, mock_call, mock_iface_up):

        mock_call.return_value = 0
        mock_iface_up.return_value = True
        with redirect_stdout(StringIO()):
            self.assertTrue(network.turn_up_network("test_if", 30))

        mock_call.assert_called_with(
            ["ip", "link", "set", "dev", "test_if", "up"]
        )

    @patch("network.wait_for_iface_up")
    @patch("network.check_call")
    def test_turn_up_network_fail(self, mock_call, mock_iface_up):

        mock_call.side_effect = CalledProcessError(1, "command failed")
        mock_iface_up.return_value = True
        with redirect_stdout(StringIO()):
            self.assertFalse(network.turn_up_network("test_if", 30))

        mock_call.assert_called_with(
            ["ip", "link", "set", "dev", "test_if", "up"]
        )

    @patch("network.wait_for_iface_up")
    @patch("network.check_call")
    def test_turn_up_network_iface_up_timeout(self, mock_call, mock_iface_up):

        mock_call.return_value = 0
        mock_iface_up.return_value = False
        with redirect_stdout(StringIO()):
            self.assertFalse(network.turn_up_network("test_if", 30))

        mock_call.assert_called_with(
            ["ip", "link", "set", "dev", "test_if", "up"]
        )

    @patch("logging.error")
    @patch("network.Interface")
    def test_check_is_underspeed(self, mock_intf, mock_logging):
        mock_intf.return_value = Mock(
            status="up", link_speed=100, max_speed=1000
        )

        self.assertTrue(network.check_underspeed("test_if"))
        mock_intf.assert_called_with("test_if")
        self.assertEqual(mock_logging.call_count, 4)

    @patch("network.Interface")
    def test_check_is_not_underspeed(self, mock_intf):
        mock_intf.return_value = Mock(
            status="up", link_speed=1000, max_speed=1000
        )

        with redirect_stderr(StringIO()):
            self.assertFalse(network.check_underspeed("test_if"))

        mock_intf.assert_called_with("test_if")

    @patch("time.sleep")
    @patch("network.Interface")
    def test_wait_for_iface_up_success(self, mock_intf, mock_sleep):
        mock_intf.return_value = Mock(status="up")

        with redirect_stderr(StringIO()):
            self.assertTrue(network.wait_for_iface_up("test_if", 2))

        mock_intf.assert_called_with("test_if")
        mock_sleep.assert_not_called()

    @patch("time.sleep")
    @patch("network.Interface")
    def test_wait_for_iface_up_fail(self, mock_intf, mock_sleep):
        mock_intf.return_value = Mock(
            status="down", link_speed=100, max_speed=1000
        )

        with redirect_stderr(StringIO()):
            self.assertFalse(network.wait_for_iface_up("test_if", 0.1))

        mock_intf.assert_called_with("test_if")
        mock_sleep.assert_called_with(5)

    @patch("network.check_underspeed")
    @patch("network.turn_down_network")
    @patch("network.turn_up_network")
    def test_setup_network_ifaces_success(
        self, mock_net_up, mock_net_down, mock_speed
    ):
        network_info = {
            "eth0": {
                "status": "down",
                "phys_switch_id": None,
                "iflink": "2",
                "ifindex": "2",
            },
            "lan1": {
                "status": "down",
                "phys_switch_id": "00000000",
                "iflink": "2",
                "ifindex": "3",
            },
            "lan2": {
                "status": "up",
                "phys_switch_id": "00000000",
                "iflink": "2",
                "ifindex": "4",
            },
        }
        mock_net_up.return_value = True
        mock_net_down.return_value = True
        mock_speed.return_value = False

        network.setup_network_ifaces(network_info, "lan1", False, True, 10)
        mock_net_up.assert_called_with("eth0", 10)
        self.assertEqual(mock_net_up.call_count, 2)
        mock_net_down.assert_called_with("lan2")
        mock_speed.assert_called_with("lan1")

    @patch("network.turn_up_network")
    def test_setup_network_ifaces_targetif_not_up(self, mock_net_up):
        network_info = {
            "eth0": {
                "status": "down",
                "phys_switch_id": None,
                "iflink": "3",
                "ifindex": "3",
            }
        }
        mock_net_up.return_value = False

        with self.assertRaises(SystemExit):
            network.setup_network_ifaces(network_info, "eth0", False, True, 10)

        mock_net_up.assert_called_with("eth0", 10)

    @patch("network.check_underspeed")
    def test_setup_network_ifaces_targetif_low_speed(self, mock_underspeed):
        network_info = {
            "eth0": {
                "status": "up",
                "phys_switch_id": None,
                "iflink": "3",
                "ifindex": "3",
            }
        }
        mock_underspeed.return_value = True

        with self.assertRaises(SystemExit):
            network.setup_network_ifaces(network_info, "eth0", False, True, 10)

        mock_underspeed.assert_called_with("eth0")

    def test_setup_network_ifaces_conduit_network_not_found(self):
        network_info = {
            "eth0": {
                "status": "up",
                "phys_switch_id": None,
                "iflink": "2",
                "ifindex": "2",
            },
            "lan1": {
                "status": "up",
                "phys_switch_id": "00000000",
                "iflink": "3",
                "ifindex": "4",
            },
        }

        with self.assertRaises(SystemExit) as context:
            network.setup_network_ifaces(network_info, "lan1", True, True, 10)

        self.assertEqual(
            str(context.exception), "Conduit network interface not found"
        )

    @patch("network.turn_up_network")
    def test_setup_network_ifaces_conduit_network_not_up(self, mock_net_up):
        network_info = {
            "eth0": {
                "status": "down",
                "phys_switch_id": None,
                "iflink": "2",
                "ifindex": "2",
            },
            "lan1": {
                "status": "up",
                "phys_switch_id": "00000000",
                "iflink": "2",
                "ifindex": "3",
            },
        }
        mock_net_up.return_value = False

        with self.assertRaises(SystemExit) as context:
            network.setup_network_ifaces(network_info, "lan1", True, True, 10)

        # print(context.exception)
        self.assertEqual(
            str(context.exception), "Failed to bring up eth0 conduit interface"
        )
        mock_net_up.assert_called_with("eth0", 10)

    @patch("network.turn_down_network")
    def test_setup_network_ifaces_shutdown_other_netif_failed(
        self, mock_net_down
    ):
        network_info = {
            "eth0": {
                "status": "up",
                "phys_switch_id": None,
                "iflink": "2",
                "ifindex": "2",
            },
            "eth1": {
                "status": "up",
                "phys_switch_id": None,
                "iflink": "3",
                "ifindex": "3",
            },
        }
        mock_net_down.return_value = False

        with self.assertRaises(SystemExit) as context:
            network.setup_network_ifaces(network_info, "eth0", True, True, 10)

        # print(context.exception)
        self.assertEqual(
            str(context.exception), "Failed to shutdown eth1 interface"
        )
        mock_net_down.assert_called_with("eth1")

    @patch("network.turn_up_network")
    @patch("network.turn_down_network")
    def test_restore_network_ifaces_success(self, mock_net_down, mock_net_up):
        origin_network_info = {
            "eth0": {
                "status": "down",
                "phys_switch_id": None,
                "iflink": "2",
                "ifindex": "3",
            },
            "eth1": {
                "status": "up",
                "phys_switch_id": None,
                "iflink": "2",
                "ifindex": "3",
            },
        }
        cur_network_info = {
            "eth0": {
                "status": "up",
                "phys_switch_id": None,
                "iflink": "2",
                "ifindex": "3",
            },
            "eth1": {
                "status": "down",
                "phys_switch_id": None,
                "iflink": "2",
                "ifindex": "3",
            },
        }
        mock_net_down.return_value = True
        mock_net_up.return_value = True

        self.assertTrue(
            network.restore_network_ifaces(
                cur_network_info, origin_network_info, 5
            )
        )

    @patch("network.turn_down_network")
    def test_restore_network_ifaces_turn_down_failed(self, mock_net_down):
        origin_network_info = {
            "eth1": {
                "status": "down",
                "phys_switch_id": None,
                "iflink": "2",
                "ifindex": "3",
            },
        }
        cur_network_info = {
            "eth1": {
                "status": "up",
                "phys_switch_id": None,
                "iflink": "2",
                "ifindex": "3",
            }
        }
        mock_net_down.return_value = False

        self.assertFalse(
            network.restore_network_ifaces(
                cur_network_info, origin_network_info, 5
            )
        )

    @patch("network.turn_up_network")
    @patch("network.turn_down_network")
    def test_restore_network_ifaces_turn_up_failed(
        self, mock_net_down, mock_net_up
    ):
        origin_network_info = {
            "eth1": {
                "status": "up",
                "phys_switch_id": None,
                "iflink": "2",
                "ifindex": "3",
            },
        }
        cur_network_info = {
            "eth1": {
                "status": "down",
                "phys_switch_id": None,
                "iflink": "2",
                "ifindex": "3",
            },
        }
        mock_net_down.return_value = False

        self.assertTrue(
            network.restore_network_ifaces(
                cur_network_info, origin_network_info, 5
            )
        )

    @patch("network.restore_network_ifaces")
    @patch("network.setup_network_ifaces")
    @patch("network.sp_run")
    @patch("network.check_call")
    @patch("network.get_network_ifaces")
    @patch("tempfile.TemporaryFile")
    def test_interface_test_initilize_run_completed(
        self,
        mock_temp_file,
        mock_net_ifs,
        mock_check_call,
        mock_sp_run,
        mock_net_setup,
        mock_net_restore,
    ):

        mock_temp_file.return_value = "fake-file"
        mock_net_ifs.return_value = {}

        with network.interface_test_initialize("eth0", False, False, 10):
            pass

        mock_check_call.assert_called_with(
            ["ip", "route", "save", "table", "all"], stdout="fake-file"
        )
        mock_sp_run.assert_called_with(
            ["ip", "route", "restore"],
            stdin="fake-file",
            stderr=subprocess.DEVNULL,
        )
        self.assertEqual(mock_temp_file.call_count, 1)
        self.assertEqual(mock_net_ifs.call_count, 2)
        mock_net_setup.assert_called_with({}, "eth0", False, True, 10)
        mock_net_restore.assert_called_with({}, {}, 10)

    @patch("network.restore_network_ifaces")
    @patch("network.sp_run")
    @patch("network.check_call")
    @patch("network.get_network_ifaces")
    @patch("tempfile.TemporaryFile")
    def test_interface_test_initilize_backup_route_failed(
        self,
        mock_temp_file,
        mock_net_ifs,
        mock_check_call,
        mock_sp_run,
        mock_net_restore,
    ):
        mock_check_call.side_effect = CalledProcessError(1, "command failed")
        mock_temp_file.return_value = "fake-file"
        mock_net_ifs.return_value = {}

        with self.assertRaises(CalledProcessError):
            with network.interface_test_initialize("eth0", False, False, 10):
                pass

        mock_check_call.assert_called_with(
            ["ip", "route", "save", "table", "all"], stdout="fake-file"
        )
        mock_sp_run.assert_called_with(
            ["ip", "route", "restore"],
            stdin="fake-file",
            stderr=subprocess.DEVNULL,
        )
        self.assertEqual(mock_temp_file.call_count, 1)
        self.assertEqual(mock_net_ifs.call_count, 2)
        mock_net_restore.assert_called_with({}, {}, 10)

    @patch("network.suppress")
    @patch("network.restore_network_ifaces")
    @patch("network.setup_network_ifaces")
    @patch("network.sp_run")
    @patch("network.check_call")
    @patch("network.get_network_ifaces")
    @patch("tempfile.TemporaryFile")
    def test_interface_test_initilize_restore_network_failed(
        self,
        mock_temp_file,
        mock_net_ifs,
        mock_check_call,
        mock_sp_run,
        mock_net_setup,
        mock_net_restore,
        mock_suppress,
    ):

        mock_temp_file.return_value = "fake-file"
        mock_net_ifs.return_value = {}
        mock_net_restore.return_value = False

        with self.assertRaises(CalledProcessError) as context:
            with network.interface_test_initialize("eth0", False, False, 10):
                pass

        mock_check_call.assert_called_with(
            ["ip", "route", "save", "table", "all"], stdout="fake-file"
        )
        mock_sp_run.assert_called_with(
            ["ip", "route", "restore"],
            stdin="fake-file",
            stderr=subprocess.DEVNULL,
        )
        mock_suppress.assert_called_with(subprocess.CalledProcessError)
        self.assertEqual(mock_temp_file.call_count, 1)
        self.assertEqual(mock_net_ifs.call_count, 2)
        mock_net_setup.assert_called_with({}, "eth0", False, True, 10)
        mock_net_restore.assert_called_with({}, {}, 10)
        self.assertIn(
            (
                "Command 'restore network failed' "
                "returned non-zero exit status 3"
            ),
            str(context.exception),
        )

    @patch("time.sleep")
    @patch("network.run_test")
    @patch("network.interface_test_initialize")
    @patch("network.make_target_list")
    @patch("network.get_test_parameters")
    def test_interface_test_run_completed(
        self,
        mock_get_test_params,
        mock_mk_targets,
        mock_net_init,
        mock_run,
        mock_sleep,
    ):
        args = Namespace(
            test_type="iperf",
            interface="eth0",
            scan_timeout=4,
            underspeed_ok=True,
            dont_toggle_ifaces=True,
            iface_timeout=1,
        )
        mock_mk_targets.side_effect = [["192.168.1.1"], ["192.168.1.1"]]
        mock_run.side_effect = [1, 0]
        mock_get_test_params.return_value = {"test_target_iperf": "127.0.0.1"}

        with redirect_stderr(StringIO()):
            result = network.interface_test(args)
        mock_net_init.assert_called_with("eth0", True, True, 1)
        mock_mk_targets.assert_called_with("eth0", "127.0.0.1", False)
        mock_sleep.assert_called_with(30)
        self.assertEqual(mock_run.call_count, 2)
        self.assertEqual(mock_sleep.call_count, 1)
        self.assertEqual(mock_mk_targets.call_count, 2)
        self.assertEqual(result, 0)

    def test_interface_test_no_test_type(self):
        args = Namespace()
        self.assertIsNone(network.interface_test(args))

    @patch("logging.error")
    @patch("network.make_target_list")
    @patch("network.get_test_parameters")
    def test_interface_test_no_target_list(
        self, mock_get_test_params, mock_mk_targets, mock_logging
    ):
        mock_mk_targets.return_value = []
        args = Namespace(test_type="iperf", interface="eth0")

        with self.assertRaises(SystemExit) as context:
            network.interface_test(args)
        self.assertEqual(context.exception.code, 1)
        self.assertEqual(mock_logging.call_count, 7)

    @patch("network.get_test_parameters")
    def test_interface_test_type_neither_iperf_nor_stress(
        self, mock_get_test_params
    ):
        mock_get_test_params.return_value = {"test_target_iperf": ""}
        args = Namespace(test_type="bogus", interface="eth0")

        with self.assertRaises(SystemExit):
            network.interface_test(args)

    def test_get_test_parameters_from_args(self):
        args = Namespace(target="10.0.0.5")
        params = network.get_test_parameters(args, {})
        self.assertEqual(params["test_target_iperf"], "10.0.0.5")

    def test_get_test_parameters_from_environ(self):
        args = Namespace(target=None)
        with patch.dict(
            "os.environ", {"TEST_TARGET_IPERF": "10.0.0.9"}, clear=True
        ):
            params = network.get_test_parameters(args, {})
        self.assertEqual(params["test_target_iperf"], "10.0.0.9")

    def test_get_test_parameters_args_take_precedence(self):
        args = Namespace(target="10.0.0.5")
        environ = {"TEST_TARGET_IPERF": "10.0.0.9"}
        params = network.get_test_parameters(args, environ)
        self.assertEqual(params["test_target_iperf"], "10.0.0.5")

    @patch("network.sp_run")
    def test_can_ping_success_on_first_try(self, mock_sp_run):
        mock_sp_run.return_value = 0
        self.assertTrue(network.can_ping("eth0", "192.168.1.1"))
        self.assertEqual(mock_sp_run.call_count, 1)

    @patch("time.sleep")
    @patch("network.sp_run")
    def test_can_ping_succeeds_after_retry(self, mock_sp_run, mock_sleep):
        mock_sp_run.side_effect = [
            CalledProcessError(1, "ping"),
            0,
        ]
        self.assertTrue(network.can_ping("eth0", "192.168.1.1"))
        self.assertEqual(mock_sp_run.call_count, 2)
        mock_sleep.assert_called_with(5)

    @patch("time.sleep")
    @patch("network.sp_run")
    def test_can_ping_exhausts_retries(self, mock_sp_run, mock_sleep):
        mock_sp_run.side_effect = CalledProcessError(1, "ping")
        self.assertFalse(network.can_ping("eth0", "192.168.1.1"))
        self.assertEqual(mock_sp_run.call_count, 48)

    @patch("network.IPerfPerformanceTest")
    @patch("network.can_ping")
    def test_run_test_iperf(self, mock_can_ping, mock_iperf_cls):
        mock_can_ping.return_value = True
        mock_benchmark = Mock(num_threads=1)
        mock_benchmark.run.return_value = 0
        mock_iperf_cls.return_value = mock_benchmark
        args = Namespace(
            interface="eth0",
            test_type="iperf",
            fail_threshold=40,
            cpu_load_fail_threshold=100,
            iperf3=False,
            num_threads=1,
            reverse=False,
            datasize=None,
            runtime=None,
            num_runs=1,
        )

        result = network.run_test(args, "192.168.1.1")

        self.assertEqual(result, 0)
        self.assertEqual(mock_benchmark.run.call_count, 1)

    @patch("network.StressPerformanceTest")
    @patch("network.can_ping")
    def test_run_test_stress(self, mock_can_ping, mock_stress_cls):
        mock_can_ping.return_value = True
        mock_benchmark = Mock()
        mock_benchmark.run.return_value = 0
        mock_stress_cls.return_value = mock_benchmark
        args = Namespace(interface="eth0", test_type="stress", iperf3=False)

        result = network.run_test(args, "192.168.1.1")

        self.assertEqual(result, 0)
        self.assertEqual(mock_benchmark.run.call_count, 1)

    @patch("network.can_ping")
    def test_run_test_unknown_type(self, mock_can_ping):
        mock_can_ping.return_value = True
        args = Namespace(interface="eth0", test_type="bogus")

        result = network.run_test(args, "192.168.1.1")

        self.assertEqual(result, 10)

    @patch("network.can_ping")
    def test_run_test_cannot_ping_returns_1(self, mock_can_ping):
        mock_can_ping.return_value = False
        args = Namespace(interface="eth0", test_type="iperf")

        result = network.run_test(args, "192.168.1.1")

        self.assertEqual(result, 1)

    @patch("network.Interface")
    def test_make_target_list_filters_out_of_subnet(self, mock_intf):
        mock_intf.return_value = Mock(
            ipaddress="192.168.1.10", netmask="255.255.255.0"
        )
        with redirect_stderr(StringIO()):
            result = network.make_target_list(
                "eth0", "10.0.0.5,192.168.1.20", True
            )
        self.assertEqual(result, ["192.168.1.20"])

    @patch("network.Interface")
    def test_make_target_list_invalid_address_removed(self, mock_intf):
        mock_intf.return_value = Mock(
            ipaddress="192.168.1.10", netmask="255.255.255.0"
        )
        with patch(
            "socket.gethostbyname", side_effect=OSError
        ), redirect_stderr(StringIO()):
            result = network.make_target_list("eth0", "not-an-ip", True)
        self.assertEqual(result, [])

    @patch("network.Interface")
    def test_make_target_list_address_value_error_exits(self, mock_intf):
        mock_intf.return_value = Mock(ipaddress=None, netmask=None)
        with self.assertRaises(SystemExit):
            network.make_target_list("eth0", "192.168.1.20", True)

    @patch("network.Interface")
    def test_make_target_list_empty_string_removed(self, mock_intf):
        mock_intf.return_value = Mock(
            ipaddress="192.168.1.10", netmask="255.255.255.0"
        )
        with patch("socket.gethostbyname", return_value="0.0.0.0"):
            result = network.make_target_list("eth0", "", True)
        self.assertEqual(result, [])

    @patch("network.Interface")
    def test_get_network_ifaces_skips_virtual_interfaces(self, mock_intf):
        path_list = [
            Path("lo"),
            Path("virbr0"),
            Path("lxdbr0"),
            Path("eth0"),
        ]
        mock_intf.return_value = Mock(
            status="up", phys_switch_id=None, iflink="2", ifindex="2"
        )
        with patch("pathlib.Path.glob", return_value=path_list):
            result = network.get_network_ifaces()
        self.assertEqual(list(result.keys()), ["eth0"])

    def test_interface_info_prints_requested_attributes(self):
        args = Namespace(interface="eth0", max_speed=True, netmask=False)
        with patch("network.Interface") as mock_intf:
            mock_intf.return_value = Mock(max_speed=1000)
            with redirect_stderr(StringIO()) as captured:
                network.interface_info(args)
        self.assertIn("max_speed: 1000", captured.getvalue())

    def test_interface_info_all_flag(self):
        args = Namespace(interface="eth0", all=True)
        with patch("network.Interface") as mock_intf:
            mock_intf.return_value = Mock(interface="eth0")
            with redirect_stderr(StringIO()) as captured:
                network.interface_info(args)
        self.assertIn("interface: eth0", captured.getvalue())

    @patch("network.Interface")
    @patch("network.can_ping")
    def test_run_test_iperf_computes_num_threads(
        self, mock_can_ping, mock_intf
    ):
        mock_can_ping.return_value = True
        mock_intf.return_value = Mock(link_speed=50000, max_speed=100000)
        args = Namespace(
            interface="eth0",
            test_type="iperf",
            fail_threshold=40,
            cpu_load_fail_threshold=100,
            iperf3=False,
            num_threads=-1,
            reverse=False,
            datasize="2",
            runtime=30,
            num_runs=1,
        )

        with patch("network.IPerfPerformanceTest.run", return_value=0), patch(
            "network.IPerfPerformanceTest.optimize_num_threads"
        ) as mock_opt:
            result = network.run_test(args, "192.168.1.1")

        self.assertEqual(result, 0)
        self.assertEqual(mock_opt.call_count, 1)

    @patch("network.can_ping")
    @patch("network.interface_test_initialize")
    @patch("network.make_target_list")
    @patch("network.get_test_parameters")
    def test_interface_test_calledprocesserror_returns_3(
        self,
        mock_get_test_params,
        mock_mk_targets,
        mock_net_init,
        mock_can_ping,
    ):
        mock_mk_targets.return_value = ["192.168.1.1"]
        mock_get_test_params.return_value = {"test_target_iperf": "x"}
        mock_net_init.side_effect = CalledProcessError(1, "cmd")
        args = Namespace(
            test_type="iperf",
            interface="eth0",
            scan_timeout=4,
            underspeed_ok=True,
            dont_toggle_ifaces=True,
            iface_timeout=1,
        )

        result = network.interface_test(args)

        self.assertEqual(result, 3)

    def test_interface_info_attribute_error_ignored(self):
        args = Namespace(interface="eth0", nonexistent_attr=True)
        with patch("network.Interface") as mock_intf:
            mock_intf.return_value = Mock(spec=[])
            with redirect_stderr(StringIO()):
                # Should not raise, AttributeError is caught internally.
                network.interface_info(args)


class InterfaceClassTest(unittest.TestCase):

    @patch("network.Interface.__init__", Mock(return_value=None))
    def setUp(self):
        self.obj_intf = network.Interface("eth0")
        self.obj_intf.interface = "eth0"
        self.obj_intf.dev_path = Path("/sys/class/net/eth0")

    @patch("network.Interface._read_data")
    def test_ifindex(self, mock_read):
        mock_read.return_value = "test"

        self.assertEqual(self.obj_intf.ifindex, "test")

    @patch("network.Interface._read_data")
    def test_iflink(self, mock_read):
        mock_read.return_value = "test"

        self.assertEqual(self.obj_intf.iflink, "test")

    @patch("network.Interface._read_data")
    def test_phys_switch_id(self, mock_read):
        mock_read.return_value = "test"

        self.assertEqual(self.obj_intf.phys_switch_id, "test")

    @patch("network.Interface._read_data")
    def test_macaddress(self, mock_read):
        mock_read.return_value = "aa:bb:cc:dd:ee:ff"

        self.assertEqual(self.obj_intf.macaddress, "aa:bb:cc:dd:ee:ff")

    @patch("network.Interface._read_data")
    def test_duplex_mode(self, mock_read):
        mock_read.return_value = "full"

        self.assertEqual(self.obj_intf.duplex_mode, "full")

    @patch("network.Interface._read_data")
    def test_status(self, mock_read):
        mock_read.return_value = "up"

        self.assertEqual(self.obj_intf.status, "up")

    @patch("network.Interface._read_data")
    def test_device_name(self, mock_read):
        mock_read.return_value = "eth0-label"

        self.assertEqual(self.obj_intf.device_name, "eth0-label")

    @patch("pathlib.Path.exists")
    @patch("socket.socket.__init__")
    def test_init_success(self, mock_socket_init, mock_exists):
        mock_socket_init.return_value = None
        mock_exists.return_value = True

        intf = network.Interface("eth0")

        self.assertEqual(intf.interface, "eth0")

    @patch("pathlib.Path.exists")
    @patch("socket.socket.__init__")
    def test_init_missing_interface_raises(
        self, mock_socket_init, mock_exists
    ):
        mock_socket_init.return_value = None
        mock_exists.return_value = False

        with self.assertRaises(FileNotFoundError):
            network.Interface("eth0")

    @patch("pathlib.Path.read_text")
    def test_read_data_success(self, mock_read_text):
        mock_read_text.return_value = "up\n"

        self.assertEqual(self.obj_intf._read_data("operstate"), "up")

    @patch("logging.warning")
    @patch("pathlib.Path.read_text")
    def test_read_data_oserror_returns_none(self, mock_read_text, mock_warn):
        mock_read_text.side_effect = OSError

        self.assertIsNone(self.obj_intf._read_data("operstate"))
        self.assertEqual(mock_warn.call_count, 1)

    @patch("network.fcntl.ioctl")
    def test_ipaddress_success(self, mock_ioctl):
        mock_ioctl.return_value = (
            b"\x00" * 20 + socket.inet_aton("192.168.1.5") + b"\x00" * 4
        )

        self.assertEqual(self.obj_intf.ipaddress, "192.168.1.5")

    @patch("logging.error")
    @patch("network.fcntl.ioctl")
    def test_ipaddress_ioerror_returns_none(self, mock_ioctl, mock_error):
        mock_ioctl.side_effect = IOError

        self.assertIsNone(self.obj_intf.ipaddress)

    @patch("network.fcntl.ioctl")
    def test_netmask_success(self, mock_ioctl):
        mock_ioctl.return_value = (
            b"\x00" * 20 + socket.inet_aton("255.255.255.0") + b"\x00" * 4
        )

        self.assertEqual(self.obj_intf.netmask, "255.255.255.0")

    @patch("logging.error")
    @patch("network.fcntl.ioctl")
    def test_netmask_ioerror_returns_none(self, mock_ioctl, mock_error):
        mock_ioctl.side_effect = IOError

        self.assertIsNone(self.obj_intf.netmask)

    @patch("network.Interface._read_data")
    def test_link_speed_valid(self, mock_read):
        mock_read.return_value = "1000"

        self.assertEqual(self.obj_intf.link_speed, 1000)

    @patch("network.Interface._read_data")
    def test_link_speed_none_raises_value_error(self, mock_read):
        mock_read.return_value = None

        with self.assertRaises(ValueError):
            self.obj_intf.link_speed

    @patch("network.check_output")
    def test_max_speed_from_ethtool(self, mock_check_output):
        mock_check_output.return_value = (
            "Settings for eth0: Supported link modes: "
            "100baseT/Full 1000baseT/Full Speed: 1000Mb/s"
        )

        self.assertEqual(self.obj_intf.max_speed, 1000)

    @patch("logging.error")
    @patch("network.check_output")
    def test_max_speed_ethtool_calledprocesserror(
        self, mock_check_output, mock_error
    ):
        mock_check_output.side_effect = CalledProcessError(
            1, "ethtool", output="boom"
        )

        self.assertEqual(self.obj_intf.max_speed, 0)

    @patch("logging.warning")
    @patch("network.check_output")
    def test_max_speed_falls_back_to_miitool(
        self, mock_check_output, mock_warn
    ):
        mock_check_output.side_effect = [
            FileNotFoundError,
            "eth0: negotiated 100baseTx-FD flow-control\n"
            "  capabilities: 100baseTx-FD 10baseT-HD\n",
        ]

        self.assertEqual(self.obj_intf.max_speed, 100)

    @patch("logging.warning")
    @patch("network.check_output")
    def test_max_speed_miitool_also_not_found(
        self, mock_check_output, mock_warn
    ):
        mock_check_output.side_effect = [FileNotFoundError, FileNotFoundError]

        self.assertEqual(self.obj_intf.max_speed, 0)

    @patch("logging.error")
    @patch("logging.warning")
    @patch("network.check_output")
    def test_max_speed_miitool_calledprocesserror(
        self, mock_check_output, mock_warn, mock_error
    ):
        mock_check_output.side_effect = [
            FileNotFoundError,
            CalledProcessError(1, "mii-tool", output="boom"),
        ]

        self.assertEqual(self.obj_intf.max_speed, 0)


if __name__ == "__main__":
    unittest.main()
