#!/usr/bin/env python3
# Copyright 2023 Canonical Ltd.
# Written by:
#   Hanhsuan Lee <hanhsuan.lee@canonical.com>
#
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
from unittest.mock import patch, MagicMock

from prime_offload_tester import *


class RunCmdTests(unittest.TestCase):
    """
    This function should execute command and raise SystemExit if fail.
    """

    @patch("subprocess.check_output")
    def test_run_command_succ(self, mock_check):
        po = PrimeOffloader()
        mock_check.return_value = "test"
        self.assertEqual(po._run_command(["echo", "test"]), "test")
        mock_check.assert_called_with(
            ["echo", "test"],
            shell=False,
            universal_newlines=True,
        )

    @patch("subprocess.check_output")
    def test_run_command_fail(self, mock_check):
        po = PrimeOffloader()
        mock_check.side_effect = FileNotFoundError
        with self.assertRaises(SystemExit):
            po._run_command(["echo", "test"])
        mock_check.assert_called_with(
            ["echo", "test"],
            shell=False,
            universal_newlines=True,
        )


class FindCardIdTests(unittest.TestCase):
    """
    This function should extract card id from debug file system by pci name
    (pci bus information)
    """

    @patch("prime_offload_tester.PrimeOffloader._run_command")
    def test_pci_name_format_check(self, mock_cmd):
        po = PrimeOffloader()
        # correct format
        mock_cmd.return_value = "/sys/kernel/debug/dri/0/name"
        self.assertEqual(po.find_card_id("0000:00:00.0"), "0")
        mock_cmd.assert_called_with(
            [
                "grep",
                "-lr",
                "--include=name",
                "0000:00:00.0",
                "/sys/kernel/debug/dri",
            ]
        )

    @patch("prime_offload_tester.PrimeOffloader._run_command")
    def test_pci_name_hex_format_check(self, mock_cmd):
        po = PrimeOffloader()
        # should work with hex vaule
        mock_cmd.return_value = "/sys/kernel/debug/dri/0/name"
        self.assertEqual(po.find_card_id("0000:c6:F0.0"), "0")

    @patch("prime_offload_tester.PrimeOffloader._run_command")
    def test_pci_name_non_hex_format_check(self, mock_cmd):
        po = PrimeOffloader()
        # error format - with alphabet
        mock_cmd.return_value = "/sys/kernel/debug/dri/0/name"
        with self.assertRaises(SystemExit):
            po.find_card_id("000r:00:00.0")

    @patch("prime_offload_tester.PrimeOffloader._run_command")
    def test_pci_name_digital_error_format_check(self, mock_cmd):
        po = PrimeOffloader()
        # error format - digital position error
        mock_cmd.return_value = "/sys/kernel/debug/dri/0/name"
        with self.assertRaises(SystemExit):
            po.find_card_id("0000:00:000.0")

    @patch("prime_offload_tester.PrimeOffloader._run_command")
    def test_empty_string_id_not_found(self, mock_cmd):
        po = PrimeOffloader()
        # empty string
        mock_cmd.return_value = ""
        with self.assertRaises(SystemExit):
            po.find_card_id("0000:00:00.0")
        mock_cmd.assert_called_with(
            [
                "grep",
                "-lr",
                "--include=name",
                "0000:00:00.0",
                "/sys/kernel/debug/dri",
            ]
        )

    @patch("prime_offload_tester.PrimeOffloader._run_command")
    def test_indexerror_id_not_found(self, mock_cmd):
        po = PrimeOffloader()
        # IndexError
        mock_cmd.side_effect = IndexError
        with self.assertRaises(SystemExit):
            po.find_card_id("0000:00:00.0")
        mock_cmd.assert_called_with(
            [
                "grep",
                "-lr",
                "--include=name",
                "0000:00:00.0",
                "/sys/kernel/debug/dri",
            ]
        )


class FindCardNameTests(unittest.TestCase):
    """
    This function should extract card name from lshw by pci name
    (pci bus information)
    """

    lshw_output = """
                 [
                  {
                    "id" : "display",
                    "class" : "display",
                    "claimed" : true,
                    "handle" : "PCI:0000:00:02.0",
                    "description" : "VGA compatible controller",
                    "product" : "TigerLake-LP GT2 [Iris Xe Graphics]",
                    "vendor" : "Intel Corporation",
                    "physid" : "2",
                    "businfo" : "pci@0000:00:02.0",
                    "logicalname" : "/dev/fb0",
                    "version" : "01",
                    "width" : 64,
                    "clock" : 33000000,
                    "configuration" : {
                      "depth" : "32",
                      "driver" : "i915",
                      "latency" : "0",
                      "mode" : "1920x1080",
                      "resolution" : "1920,1080",
                      "visual" : "truecolor",
                      "xres" : "1920",
                      "yres" : "1080"
                    },
                    "capabilities" : {
                      "pciexpress" : "PCI Express",
                      "msi" : "Message Signalled Interrupts",
                      "pm" : "Power Management",
                      "vga_controller" : true,
                      "bus_master" : "bus mastering",
                      "cap_list" : "PCI capabilities listing",
                      "rom" : "extension ROM",
                      "fb" : "framebuffer"
                    }
                  }
                ]"""

    lshw_output_err = """
                    [
                     {
                       "id" : "display",
                       "class" : "display",
                       "claimed" : true,
                       "handle" : "PCI:0000:00:02.0",
                       "description" : "VGA compatible controller",
                       "product" : "TigerLake-LP GT2 [Iris Xe Graphics]",
                       "vendor" : "Intel Corporation",
                       "physid" : "2",
                       "logicalname" : "/dev/fb0",
                       "version" : "01",
                       "width" : 64,
                       "clock" : 33000000,
                       "configuration" : {
                         "depth" : "32",
                         "driver" : "i915",
                         "latency" : "0",
                         "mode" : "1920x1080",
                         "resolution" : "1920,1080",
                         "visual" : "truecolor",
                         "xres" : "1920",
                         "yres" : "1080"
                       }
                     }
                   ]"""

    @patch("prime_offload_tester.PrimeOffloader._run_command")
    def test_name_found_check(self, mock_cmd):
        po = PrimeOffloader()
        mock_cmd.return_value = self.lshw_output
        self.assertEqual(
            po.find_card_name("0000:00:02.0"),
            "TigerLake-LP GT2 [Iris Xe Graphics]",
        )
        mock_cmd.assert_called_with(
            ["lshw", "-c", "display", "-numeric", "-json"]
        )

    @patch("prime_offload_tester.PrimeOffloader._run_command")
    def test_pci_bdf_error_name_not_found_check(self, mock_cmd):
        po = PrimeOffloader()
        # pci_bdf error
        mock_cmd.return_value = self.lshw_output
        with self.assertRaises(SystemExit):
            po.find_card_name("0000:00:00.0")
        mock_cmd.assert_called_with(
            ["lshw", "-c", "display", "-numeric", "-json"]
        )

    @patch("prime_offload_tester.PrimeOffloader._run_command")
    def test_no_lshw_output_name_not_found_check(self, mock_cmd):
        po = PrimeOffloader()
        # no businfo in lshw output
        mock_cmd.return_value = self.lshw_output_err
        with self.assertRaises(SystemExit):
            po.find_card_name("0000:00:00.0")
        mock_cmd.assert_called_with(
            ["lshw", "-c", "display", "-numeric", "-json"]
        )

    @patch("prime_offload_tester.PrimeOffloader._run_command")
    def test_empty_string_name_not_found_check(self, mock_cmd):
        po = PrimeOffloader()
        # empty string
        mock_cmd.return_value = ""
        with self.assertRaises(SystemExit):
            po.find_card_name("0000:00:00.0")
        mock_cmd.assert_called_with(
            ["lshw", "-c", "display", "-numeric", "-json"]
        )

    @patch("prime_offload_tester.PrimeOffloader._run_command")
    def test_none_name_not_found_check(self, mock_cmd):
        po = PrimeOffloader()
        # None
        mock_cmd.return_value = None
        with self.assertRaises(SystemExit):
            po.find_card_name("0000:00:00.0")
        mock_cmd.assert_called_with(
            ["lshw", "-c", "display", "-numeric", "-json"]
        )

    @patch("prime_offload_tester.PrimeOffloader._run_command")
    def test_keyerror_name_not_found_check(self, mock_cmd):
        po = PrimeOffloader()
        mock_cmd.side_effect = KeyError
        with self.assertRaises(SystemExit):
            po.find_card_name("0000:00:00.0")
        mock_cmd.assert_called_with(
            ["lshw", "-c", "display", "-numeric", "-json"]
        )


class GetClientsTests(unittest.TestCase):
    """
    This function should return the data in the right
    "/sys/kernel/debug/dri/*/clients"
    """

    @patch("prime_offload_tester.PrimeOffloader._run_command")
    def test_get_clients(self, mock_cmd):
        po = PrimeOffloader()
        mock_cmd.return_value = "echo"
        self.assertEqual(po.get_clients(0), "echo")
        mock_cmd.assert_called_with(["cat", "/sys/kernel/debug/dri/0/clients"])


class CheckOffloadTests(unittest.TestCase):
    """
    This function will check process is showed in specific dri devide
    debug file system
    """

    @patch("time.sleep", return_value=None)
    @patch("prime_offload_tester.PrimeOffloader.get_clients")
    def test_offload_succ_check(self, mock_client, mock_sleep):
        cmd = ["echo"]
        mock_client.return_value = cmd
        po = PrimeOffloader()
        self.assertEqual(
            po.check_offload(cmd, "card_id", "card_name", 1), None
        )
        self.assertEqual(po.check_result, False)

    @patch("time.sleep", return_value=None)
    @patch("prime_offload_tester.PrimeOffloader.get_clients")
    def test_offload_fail_check(self, mock_client, mock_sleep):
        cmd = ["echo"]
        # get_clients return string that doesn't include cmd
        mock_client.return_value = ""
        po = PrimeOffloader()
        self.assertEqual(
            po.check_offload(cmd, "card_id", "card_name", 1), None
        )
        self.assertEqual(po.check_result, True)

        # get_clients return None by CalledProcessError
        mock_client.return_value = None
        po = PrimeOffloader()
        self.assertEqual(
            po.check_offload(cmd, "card_id", "card_name", 1), None
        )
        self.assertEqual(po.check_result, True)


class FindBDFTests(unittest.TestCase):
    """
    This function should return the BDF in the right
    "/sys/kernel/debug/dri/*/name"
    """

    @patch("prime_offload_tester.PrimeOffloader._run_command")
    def test_find_bdf(self, mock_cmd):
        po = PrimeOffloader()
        card = "/sys/kernel/debug/dri/0/clients"
        mock_cmd.return_value = "i915 dev=0000:00:02.0 unique=0000:00:02.0"
        self.assertEqual(po._find_bdf(card), "0000:00:02.0")
        mock_cmd.assert_called_with(["cat", card.replace("clients", "name")])


class FindOffloadTests(unittest.TestCase):
    """
    This function should try to find which GPU is the renderer
    for the specific command.
    """

    @patch("time.sleep", return_value=None)
    @patch("prime_offload_tester.PrimeOffloader._run_command")
    def test_found(self, mock_cmd, mock_sleep):
        mock_cmd.return_value = (
            "/sys/kernel/debug/dri/0/clients\n"
            + "/sys/kernel/debug/dri/128/clients\n"
        )
        cmd = "echo"
        po = PrimeOffloader()
        po._find_bdf = MagicMock(return_value="0")
        po.find_card_id = MagicMock(return_value="0")
        po.find_card_name = MagicMock(return_value="Intel")
        self.assertEqual(po.find_offload(cmd, 1), None)
        mock_cmd.assert_called_with(
            [
                "grep",
                "-lr",
                "--include=clients",
                "echo",
                "/sys/kernel/debug/dri",
            ]
        )
        self.assertEqual(po.check_result, False)

    @patch("time.sleep", return_value=None)
    @patch("prime_offload_tester.PrimeOffloader._run_command")
    def test_not_found(self, mock_cmd, mock_sleep):
        mock_cmd.return_value = ""
        cmd = "echo"
        po = PrimeOffloader()
        po._find_bdf = MagicMock(return_value="0")
        po.find_card_id = MagicMock(return_value="0")
        po.find_card_name = MagicMock(return_value="Intel")
        self.assertEqual(po.find_offload(cmd, 1), None)
        mock_cmd.assert_called_with(
            [
                "grep",
                "-lr",
                "--include=clients",
                "echo",
                "/sys/kernel/debug/dri",
            ]
        )
        self.assertEqual(po.check_result, True)


class CheckNvOffloadEnvTests(unittest.TestCase):
    """
    This function will check this system could use prime offload or not.
    Only on-demand mode is supported for NV driver.
    """

    @patch("subprocess.check_output")
    def test_on_demand_check(self, mock_check):
        po = PrimeOffloader()
        # with nv driver, not on-demand mode
        mock_check.return_value = "prime-select"
        with self.assertRaises(SystemExit):
            po.check_nv_offload_env()
        mock_check.assert_called_with(
            ["prime-select", "query"], universal_newlines=True
        )

    @patch("subprocess.check_output")
    def test_nvlink_check(self, mock_check):
        po = PrimeOffloader()
        # with nv driver, on-demand mode. This might be NVLINK environment
        mock_check.return_value = "prime-select on-demand"
        with self.assertRaises(SystemExit):
            po.check_nv_offload_env()
        mock_check.assert_called_with(
            ["nvidia-smi", "nvlink", "-s"], universal_newlines=True
        )

        # with nv driver, on-demand mode, nv driver error
        mock_check.side_effect = ["on-demand", "error"]
        with self.assertRaises(SystemExit):
            po.check_nv_offload_env()
        mock_check.assert_called_with(
            ["nvidia-smi", "nvlink", "-s"], universal_newlines=True
        )

        # with nv driver, on-demand mode, no nv driver error
        mock_check.side_effect = ["on-demand", ""]
        self.assertEqual(None, po.check_nv_offload_env())
        mock_check.assert_called_with(
            ["nvidia-smi", "nvlink", "-s"], universal_newlines=True
        )

        # No prime-select
        mock_check.side_effect = FileNotFoundError
        self.assertEqual(po.check_nv_offload_env(), None)


class ReformatCmdTimeoutTests(unittest.TestCase):
    """
    This function should return the right format command with timeout setting
    and the real timeout for futher usage.
    """

    def test_timeout_in_cmd(self):
        po = PrimeOffloader()
        with self.assertRaises(SystemExit):
            po._reformat_cmd_timeout("timeout 10 echo", 10)

    def test_timeout_greater_than_zero(self):
        po = PrimeOffloader()
        (cmd, timeout) = po._reformat_cmd_timeout("echo test", 10)
        self.assertEqual(cmd, ["timeout", "10", "echo", "test"])
        self.assertEqual(timeout, 10)

    def test_timeout_less_than_zero(self):
        po = PrimeOffloader()
        (cmd, timeout) = po._reformat_cmd_timeout("echo test", 0)
        self.assertEqual(cmd, ["echo", "test"])
        self.assertEqual(timeout, 20)


class CmdRunnerTests(unittest.TestCase):
    """
    This function should run the command with Popen mode
    and the right environment variables.
    """

    o_env = {"DRI_PRIME": "pci-0000_00_00_0"}

    @patch("subprocess.Popen")
    def test_cmd_runner_succ(self, mock_open):
        po = PrimeOffloader()
        os.environ.copy = MagicMock(return_value={})
        po.cmd_runner(["echo", "0000:00:00.0", "xxx", 0], self.o_env)
        # check cmd_runner executing correct command
        mock_open.assert_called_with(
            ["echo", "0000:00:00.0", "xxx", 0],
            env=self.o_env,
            stdout=subprocess.PIPE,
            universal_newlines=True,
        )

    @patch("subprocess.Popen")
    def test_cmd_runner_fail(self, mock_open):
        po = PrimeOffloader()
        mock_open.side_effect = subprocess.CalledProcessError(-1, "test")
        with self.assertRaises(SystemExit):
            po.cmd_runner(["echo", "0000:00:00.0", "xxx", 0], self.o_env)


class CmdFinderTests(unittest.TestCase):
    """
    This function should find the command is rendered by which GPU
    """

    @patch("prime_offload_tester.PrimeOffloader.cmd_runner")
    def test_found(self, mock_runner):
        po = PrimeOffloader()
        po._reformat_cmd_timeout = MagicMock(
            return_value=(["timeout", "20", "glxgears"], 20)
        )
        po.find_offload = MagicMock(return_value="")
        os.environ.copy = MagicMock(return_value={})
        po.check_result = False
        po.cmd_finder("glxgears", 20)
        # check cmd_finder executing correct command
        mock_runner.assert_called_with(
            ["timeout", "20", "glxgears"],
        )
        # check check_offload function get correct args
        po.find_offload.assert_called_with("glxgears", 20)

    @patch("prime_offload_tester.PrimeOffloader.cmd_runner")
    def test_not_found(self, mock_runner):
        po = PrimeOffloader()
        po._reformat_cmd_timeout = MagicMock(
            return_value=(["timeout", "20", "glxgears"], 20)
        )
        po.find_offload = MagicMock(return_value="")
        os.environ.copy = MagicMock(return_value={})
        po.check_result = True
        with self.assertRaises(SystemExit):
            po.cmd_finder("glxgears", 20)
        # check cmd_finder executing correct command
        mock_runner.assert_called_with(
            ["timeout", "20", "glxgears"],
        )
        # check check_offload function get correct args
        po.find_offload.assert_called_with("glxgears", 20)


class CmdCheckerTests(unittest.TestCase):
    """
    This function is the entry point to run the command with prime offload,
    if the environment is supported.
    """

    nv_env = {
        "__NV_PRIME_RENDER_OFFLOAD": "1",
        "__GLX_VENDOR_LIBRARY_NAME": "nvidia",
    }
    o_env = {"DRI_PRIME": "pci-0000_00_00_0"}

    def test_no_card_id_check(self):
        po = PrimeOffloader()
        # no card id
        po.find_card_id = MagicMock(side_effect=SystemExit)
        with self.assertRaises(SystemExit):
            po.cmd_checker("echo", "0000:00:00.0", "driver", 0)

    def test_no_card_name_check(self):
        po = PrimeOffloader()
        # no card name
        po.find_card_id = MagicMock(return_value="0")
        po.find_card_name = MagicMock(side_effect=SystemExit)
        with self.assertRaises(SystemExit):
            po.cmd_checker("echo", "0000:00:00.0", "driver", 0)

    def test_timeout_in_cmd_check(self):
        po = PrimeOffloader()
        # timeout in command
        po.find_card_id = MagicMock(return_value="0")
        po.find_card_name = MagicMock(return_value="Card")
        with self.assertRaises(SystemExit):
            po.cmd_checker("timeout 10 echo", "0000:00:00.0", "driver", 0)

    def test_nv_env_fail_check(self):
        po = PrimeOffloader()
        # check_nv_offload_env failed
        po.find_card_id = MagicMock(return_value="0")
        po.find_card_name = MagicMock(return_value="Card")
        po.check_nv_offload_env = MagicMock(side_effect=SystemExit)
        with self.assertRaises(SystemExit):
            po.cmd_checker("echo", "0000:00:00.0", "driver", 0)

    @patch("prime_offload_tester.PrimeOffloader.cmd_runner")
    def test_non_nv_driver_check(self, mock_runner):

        # non NV driver
        po = PrimeOffloader()
        po.find_card_id = MagicMock(return_value="0")
        po.find_card_name = MagicMock(return_value="Intel")
        po.check_nv_offload_env = MagicMock(return_value=None)
        po.check_offload = MagicMock(return_value="")
        po._reformat_cmd_timeout = MagicMock(
            return_value=(["timeout", "20", "glxgears"], 20)
        )
        os.environ.copy = MagicMock(return_value={})
        po.cmd_checker("glxgears", "0000:00:00.0", "xxx", 0)
        # check cmd_checker executing correct command
        mock_runner.assert_called_with(
            ["timeout", "20", "glxgears"],
            self.o_env,
        )
        # check check_offload function get correct args
        po.check_offload.assert_called_with("glxgears", "0", "Intel", 20)

    @patch("prime_offload_tester.PrimeOffloader.cmd_runner")
    def test_nv_driver_check(self, mock_runner):

        # NV driver
        po = PrimeOffloader()
        po.find_card_id = MagicMock(return_value="0")
        po.find_card_name = MagicMock(return_value="NV")
        po.check_nv_offload_env = MagicMock(return_value=None)
        po.check_offload = MagicMock(return_value="")
        po._reformat_cmd_timeout = MagicMock(
            return_value=(["timeout", "1", "glxgears"], 1)
        )
        os.environ.copy = MagicMock(return_value={})
        po.cmd_checker("glxgears", "0000:00:00.0", "nvidia", 1)
        # check run_offload_cmd executing correct command
        mock_runner.assert_called_with(
            ["timeout", "1", "glxgears"],
            self.nv_env,
        )
        # check check_offload function get correct args
        po.check_offload.assert_called_with("glxgears", "0", "NV", 1)

    @patch("prime_offload_tester.PrimeOffloader.cmd_runner")
    def test_not_found(self, mock_runner):
        po = PrimeOffloader()
        po.find_card_id = MagicMock(return_value="0")
        po.find_card_name = MagicMock(return_value="NV")
        po._reformat_cmd_timeout = MagicMock(
            return_value=(["timeout", "20", "glxgears"], 20)
        )
        po.check_offload = MagicMock(return_value="")
        os.environ.copy = MagicMock(return_value={})
        po.check_result = True
        with self.assertRaises(SystemExit):
            po.cmd_checker("glxgears", "0000:00:00.0", "nvidia", 1)
        # check cmd_checker executing correct command
        mock_runner.assert_called_with(
            ["timeout", "20", "glxgears"],
            self.nv_env,
        )
        # check check_offload function get correct args
        po.check_offload.assert_called_with("glxgears", "0", "NV", 20)


class ParseArgsTests(unittest.TestCase):
    def test_success(self):
        po = PrimeOffloader()
        # no arguments, load default
        args = []
        rv = po.parse_args(args)
        self.assertEqual(rv.command, "glxgears")
        self.assertEqual(rv.pci, None)
        self.assertEqual(rv.driver, None)
        self.assertEqual(rv.timeout, 20)

        # change command
        args = ["-c", "glxgears -fullscreen"]
        rv = po.parse_args(args)
        self.assertEqual(rv.command, "glxgears -fullscreen")
        self.assertEqual(rv.pci, None)
        self.assertEqual(rv.driver, None)
        self.assertEqual(rv.timeout, 20)

        # change pci
        args = ["-p", "0000:00:01.0"]
        rv = po.parse_args(args)
        self.assertEqual(rv.command, "glxgears")
        self.assertEqual(rv.pci, "0000:00:01.0")
        self.assertEqual(rv.driver, None)
        self.assertEqual(rv.timeout, 20)

        # change driver
        args = ["-d", "nvidia"]
        rv = po.parse_args(args)
        self.assertEqual(rv.command, "glxgears")
        self.assertEqual(rv.pci, None)
        self.assertEqual(rv.driver, "nvidia")
        self.assertEqual(rv.timeout, 20)

        # change timeout
        args = ["-t", "5"]
        rv = po.parse_args(args)
        self.assertEqual(rv.command, "glxgears")
        self.assertEqual(rv.pci, None)
        self.assertEqual(rv.driver, None)
        self.assertEqual(rv.timeout, 5)

        # change all
        args = [
            "-c",
            "glxgears -fullscreen",
            "-p",
            "0000:00:01.0",
            "-d",
            "nvidia",
            "-t",
            "5",
        ]
        rv = po.parse_args(args)
        self.assertEqual(rv.command, "glxgears -fullscreen")
        self.assertEqual(rv.pci, "0000:00:01.0")
        self.assertEqual(rv.driver, "nvidia")
        self.assertEqual(rv.timeout, 5)


class MainTests(unittest.TestCase):
    @patch("prime_offload_tester.PrimeOffloader.parse_args")
    @patch("prime_offload_tester.PrimeOffloader.cmd_checker")
    def test_run_cmd_checker_succ(self, mock_checker, mock_parse_args):
        args_mock = MagicMock()
        args_mock.command = "cmd"
        args_mock.pci = "pci"
        args_mock.driver = "driver"
        args_mock.timeout = "1"
        mock_parse_args.return_value = args_mock
        self.assertEqual(PrimeOffloader().main(), None)
        mock_checker.assert_called_with(
            "cmd",
            "pci",
            "driver",
            "1",
        )

    @patch("prime_offload_tester.PrimeOffloader.parse_args")
    @patch("prime_offload_tester.PrimeOffloader.cmd_finder")
    def test_run_cmd_finder_succ(self, mock_finder, mock_parse_args):
        args_mock = MagicMock()
        args_mock.command = "cmd"
        args_mock.pci = None
        args_mock.driver = None
        args_mock.timeout = "1"
        mock_parse_args.return_value = args_mock
        self.assertEqual(PrimeOffloader().main(), None)
        mock_finder.assert_called_with(
            "cmd",
            "1",
        )


if __name__ == "__main__":
    unittest.main()
