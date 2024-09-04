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
import subprocess
from unittest.mock import patch, mock_open, Mock, call
from contextlib import redirect_stdout, redirect_stderr
from io import StringIO
from pathlib import Path
from subprocess import CalledProcessError
from argparse import Namespace

import network


class IPerfPerfomanceTestTests(unittest.TestCase):

    def test_find_numa_reports_node(self):
        with patch("builtins.open", mock_open(read_data="1")) as mo:
            returned = network.IPerfPerformanceTest.find_numa(None, "device")
            self.assertEqual(returned, 1)

    def test_find_numa_minus_one_from_sysfs(self):
        with patch("builtins.open", mock_open(read_data="-1")) as mo:
            returned = network.IPerfPerformanceTest.find_numa(None, "device")
            self.assertEqual(returned, -1)

    def test_find_numa_numa_node_not_found(self):
        with patch("builtins.open", mock_open()) as mo:
            mo.side_effect = FileNotFoundError
            returned = network.IPerfPerformanceTest.find_numa(None, "device")
            self.assertEqual(returned, -1)


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
        mock_intf.assert_called_with(path_list[-1])
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

    @patch("logging.error")
    @patch("network.make_target_list")
    @patch("network.get_test_parameters")
    def test_interface_test_with_example_target_list(
        self, mock_get_test_params, mock_mk_targets, mock_logging
    ):
        mock_mk_targets.return_value = ["192.168.1.1"]
        mock_get_test_params.return_value = {
            "test_target_iperf": "example.com"
        }
        args = Namespace(test_type="iperf", interface="eth0")

        with self.assertRaises(SystemExit) as context:
            network.interface_test(args)
        self.assertEqual(context.exception.code, 1)
        self.assertEqual(mock_logging.call_count, 7)


class InterfaceClassTest(unittest.TestCase):

    @patch("network.Interface.__init__", Mock(return_value=None))
    def setUp(self):
        self.obj_intf = network.Interface("eth0")

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
