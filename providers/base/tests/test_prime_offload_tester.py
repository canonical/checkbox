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


class FindCardIdTests(unittest.TestCase):
    """
    This function should extract card id from debug file system by pci name
    (pci bus information)
    """

    @patch("subprocess.check_output")
    def test_pci_name_format_check(self, mock_check):
        po = PrimeOffloader()
        # correct format
        mock_check.return_value = "/sys/kernel/debug/dri/0/name"
        self.assertEqual(po.find_card_id("0000:00:00.0"), "0")
        mock_check.assert_called_with(["grep",
                                       "-lr",
                                       "--include=name",
                                       "0000:00:00.0",
                                       "/sys/kernel/debug/dri"],
                                      universal_newlines=True)

        # error format - with alphabet
        with self.assertRaises(SystemExit):
            po.find_card_id("000r:00:00.0")

        # error format - digital position error
        with self.assertRaises(SystemExit):
            po.find_card_id("0000:00:000.0")

    @patch("subprocess.check_output")
    def test_id_not_found(self, mock_check):
        po = PrimeOffloader()
        # empty string
        mock_check.return_value = ""
        with self.assertRaises(SystemExit):
            po.find_card_id("0000:00:00.0")
        mock_check.assert_called_with(["grep",
                                       "-lr",
                                       "--include=name",
                                       "0000:00:00.0",
                                       "/sys/kernel/debug/dri"],
                                      universal_newlines=True)

        # subprocess error
        mock_check.side_effect = subprocess.CalledProcessError(-1, "test")
        with self.assertRaises(SystemExit):
            po.find_card_id("0000:00:00.0")
        mock_check.assert_called_with(["grep",
                                       "-lr",
                                       "--include=name",
                                       "0000:00:00.0",
                                       "/sys/kernel/debug/dri"],
                                      universal_newlines=True)


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

    @patch("subprocess.check_output")
    def test_name_found_check(self, mock_check):
        po = PrimeOffloader()
        mock_check.return_value = self.lshw_output
        self.assertEqual(po.find_card_name("0000:00:02.0"),
                         "TigerLake-LP GT2 [Iris Xe Graphics]")
        mock_check.assert_called_with(["lshw",
                                       "-c",
                                       "display",
                                       "-json"],
                                      universal_newlines=True)

    @patch("subprocess.check_output")
    def test_name_not_found_check(self, mock_check):
        po = PrimeOffloader()
        # pci_name error
        mock_check.return_value = self.lshw_output
        with self.assertRaises(SystemExit):
            po.find_card_name("0000:00:00.0")
        mock_check.assert_called_with(["lshw",
                                       "-c",
                                       "display",
                                       "-json"],
                                      universal_newlines=True)

        # no businfo in lshw output
        mock_check.return_value = self.lshw_output_err
        with self.assertRaises(SystemExit):
            po.find_card_name("0000:00:00.0")
        mock_check.assert_called_with(["lshw",
                                       "-c",
                                       "display",
                                       "-json"],
                                      universal_newlines=True)

        # empty string
        mock_check.return_value = ""
        with self.assertRaises(SystemExit):
            po.find_card_name("0000:00:00.0")
        mock_check.assert_called_with(["lshw",
                                       "-c",
                                       "display",
                                       "-json"],
                                      universal_newlines=True)

        # None
        mock_check.return_value = None
        with self.assertRaises(SystemExit):
            po.find_card_name("0000:00:00.0")
        mock_check.assert_called_with(["lshw",
                                       "-c",
                                       "display",
                                       "-json"],
                                      universal_newlines=True)

        # subprocess error
        mock_check.side_effect = subprocess.CalledProcessError(-1, "test")
        with self.assertRaises(SystemExit):
            po.find_card_name("0000:00:00.0")
        mock_check.assert_called_with(["lshw",
                                       "-c",
                                       "display",
                                       "-json"],
                                      universal_newlines=True)


class CheckOffloadTests(unittest.TestCase):
    """
    This function will check process is showed in specific dri devide
    debug file system
    """

    @patch('time.sleep', return_value=None)
    @patch("subprocess.check_output")
    def test_offload_succ_check(self, mock_check, mock_sleep):
        cmd = ["echo"]
        mock_check.return_value = cmd
        po = PrimeOffloader()
        self.assertEqual(po.check_offload(cmd, "card_id", "card_name", 1),
                         None)
        self.assertFalse(po.check_result)
        mock_check.assert_called_with(["cat",
                                       "/sys/kernel/debug/dri/card_id/clients"
                                       ],
                                      universal_newlines=True)

        po = PrimeOffloader()
        self.assertEqual(po.check_offload(cmd, "card_id", "card_name", 0),
                         None)
        self.assertFalse(po.check_result)
        mock_check.assert_called_with(["cat",
                                       "/sys/kernel/debug/dri/card_id/clients"
                                       ],
                                      universal_newlines=True)

        po = PrimeOffloader()
        self.assertEqual(po.check_offload(cmd, "card_id", "card_name", 0),
                         None)
        self.assertFalse(po.check_result)
        mock_check.assert_called_with(["cat",
                                       "/sys/kernel/debug/dri/card_id/clients"
                                       ],
                                      universal_newlines=True)

    @patch('time.sleep', return_value=None)
    @patch("subprocess.check_output")
    def test_offload_fail_check(self, mock_check, mock_sleep):

        # cmd isn't showed in debug file system
        # empty string
        cmd = ["echo"]
        mock_check.return_value = ""
        po = PrimeOffloader()
        self.assertEqual(po.check_offload(cmd, "card_id", "card_name", 0),
                         None)
        self.assertTrue(po.check_result)
        mock_check.assert_called_with(
                ["cat",
                 "/sys/kernel/debug/dri/card_id/clients"
                 ],
                universal_newlines=True)

        # None
        mock_check.return_value = None
        po = PrimeOffloader()
        self.assertEqual(po.check_offload(cmd, "card_id", "card_name", 0),
                         None)
        self.assertTrue(po.check_result)

        # OS Error
        # Missing file or permissions
        mock_check.side_effect = OSError
        po = PrimeOffloader()
        self.assertEqual(po.check_offload(cmd, "card_id", "card_name", 0),
                         None)
        self.assertTrue(po.check_result)

        # no match process
        mock_check.side_effect = ["xxx",
                                  "test\ndemo",
                                  "test\ndemo",
                                  "test\ndemo",
                                  "test\ndemo",
                                  "test\ndemo",
                                  "test\ndemo",
                                  "test\ndemo",
                                  "test\ndemo",
                                  "test\ndemo"
                                  ]
        po = PrimeOffloader()
        self.assertEqual(po.check_offload(cmd, "card_id", "card_name", 0),
                         None)
        self.assertTrue(po.check_result)
        mock_check.assert_called_with(["cat",
                                       "/sys/kernel/debug/dri/card_id/clients"
                                       ],
                                      universal_newlines=True)


class CheckNvOffloadEnvTests(unittest.TestCase):
    """
    This function will check this system could use prime offload or not.
    Only on-demand mode is supported for NV driver.
    """

    @patch("subprocess.check_output")
    def test_no_prime_select_check(self, mock_check):
        po = PrimeOffloader()
        # subprocess failed
        mock_check.side_effect = subprocess.CalledProcessError(-1, "which")
        self.assertEqual(None, po.check_nv_offload_env())
        mock_check.assert_called_with(["which",
                                       "prime-select"
                                       ],
                                      universal_newlines=True)

        mock_check.side_effect = ["xxxxx"]
        self.assertEqual(None, po.check_nv_offload_env())
        mock_check.assert_called_with(["which",
                                       "prime-select"
                                       ],
                                      universal_newlines=True)

    @patch("subprocess.check_output")
    def test_on_demand_check(self, mock_check):
        po = PrimeOffloader()
        # with nv driver, not on-demand mode
        mock_check.return_value = "prime-select"
        with self.assertRaises(RuntimeError):
            po.check_nv_offload_env()
        mock_check.assert_called_with(["prime-select",
                                       "query"],
                                      universal_newlines=True)

    @patch("subprocess.check_output")
    def test_nvlink_check(self, mock_check):
        po = PrimeOffloader()
        # with nv driver, on-demand mode. This might be NVLINK environment
        mock_check.return_value = "prime-select on-demand"
        with self.assertRaises(RuntimeError):
            po.check_nv_offload_env()
        mock_check.assert_called_with(["nvidia-smi",
                                       "nvlink",
                                       "-s"],
                                      universal_newlines=True)

        # with nv driver, on-demand mode, nv driver error
        mock_check.side_effect = ["prime-select", "on-demand", "error"]
        with self.assertRaises(RuntimeError):
            po.check_nv_offload_env()
        mock_check.assert_called_with(["nvidia-smi",
                                       "nvlink",
                                       "-s"],
                                      universal_newlines=True)

        # with nv driver, on-demand mode, no nv driver error
        mock_check.side_effect = ["prime-select",
                                  "on-demand",
                                  ""]
        self.assertEqual(None, po.check_nv_offload_env())
        mock_check.assert_called_with(["nvidia-smi",
                                       "nvlink",
                                       "-s"],
                                      universal_newlines=True)


class RunOffloadCmdTests(unittest.TestCase):
    """
    This function is the entry point to run the command with prime offload,
    if the environment is supported.
    """

    def test_condition_check(self):
        po = PrimeOffloader()
        # no card id
        po.find_card_id = MagicMock(side_effect=RuntimeError)
        with self.assertRaises(RuntimeError):
            po.run_offload_cmd("echo", "0000:00:00.0", "driver", 0)

        # no card name
        po.find_card_id = MagicMock(return_value="0")
        po.find_card_name = MagicMock(side_effect=RuntimeError)
        with self.assertRaises(RuntimeError):
            po.run_offload_cmd("echo", "0000:00:00.0", "driver", 0)

        # timeout in command
        po.find_card_id = MagicMock(return_value="0")
        po.find_card_name = MagicMock(return_value="Card")
        with self.assertRaises(RuntimeError):
            po.run_offload_cmd("timeout 10 echo",
                               "0000:00:00.0",
                               "driver",
                               0)

        # check_nv_offload_env failed
        po.find_card_id = MagicMock(return_value="0")
        po.find_card_name = MagicMock(return_value="Card")
        po.check_nv_offload_env = MagicMock(side_effect=RuntimeError)
        with self.assertRaises(RuntimeError):
            po.run_offload_cmd("echo",
                               "0000:00:00.0",
                               "driver",
                               0)

    @patch('time.sleep', return_value=None)
    @patch("subprocess.Popen")
    def test_offload_cmd_check(self, mock_open, mock_sleep):
        nv_env = {'__NV_PRIME_RENDER_OFFLOAD': '1',
                  '__GLX_VENDOR_LIBRARY_NAME': 'nvidia'}
        o_env = {'DRI_PRIME': 'pci-0000_00_00_0'}

        # non NV driver
        po = PrimeOffloader()
        po.find_card_id = MagicMock(return_value="0")
        po.find_card_name = MagicMock(return_value="Intel")
        po.check_nv_offload_env = MagicMock(return_value=None)
        po.check_offload = MagicMock(return_value="")
        os.environ.copy = MagicMock(return_value={})
        po.run_offload_cmd("echo", "0000:00:00.0", "xxx", 0)
        # check run_offload_cmd executing correct command
        mock_open.assert_called_with(["echo"],
                                     env=o_env,
                                     stdout=subprocess.PIPE,
                                     universal_newlines=True)
        # check check_offload function get correct args
        po.check_offload.assert_called_with(["echo"], '0', 'Intel', 0)

        # non NV driver with timeout setting
        po.find_card_id = MagicMock(return_value="0")
        po.find_card_name = MagicMock(return_value="Intel")
        po.check_nv_offload_env = MagicMock(return_value=None)
        po.check_offload = MagicMock(return_value="")
        os.environ.copy = MagicMock(return_value={})
        po.run_offload_cmd("echo", "0000:00:00.0", "xxx", 1)
        # check run_offload_cmd executing correct command
        mock_open.assert_called_with(["timeout", "1", "echo"],
                                     env=o_env,
                                     stdout=subprocess.PIPE,
                                     universal_newlines=True)
        # check check_offload function get correct args
        po.check_offload.assert_called_with(["echo"], '0', 'Intel', 1)

        # NV driver
        po.find_card_id = MagicMock(return_value="0")
        po.find_card_name = MagicMock(return_value="NV")
        po.check_nv_offload_env = MagicMock(return_value=None)
        po.check_offload = MagicMock(return_value="")
        os.environ.copy = MagicMock(return_value={})
        po.run_offload_cmd("echo", "0000:00:00.0", "nvidia", 1)
        # check run_offload_cmd executing correct command
        mock_open.assert_called_with(["timeout", "1", "echo"],
                                     env=nv_env,
                                     stdout=subprocess.PIPE,
                                     universal_newlines=True)
        # check check_offload function get correct args
        po.check_offload.assert_called_with(["echo"], '0', 'NV', 1)

        # subprocess error
        po.find_card_id = MagicMock(return_value="0")
        po.find_card_name = MagicMock(return_value="NV")
        po.check_nv_offload_env = MagicMock(return_value=None)
        po.check_offload = MagicMock(return_value="")
        os.environ.copy = MagicMock(return_value={})
        mock_open.side_effect = subprocess.CalledProcessError(-1, "test")
        with self.assertRaises(RuntimeError):
            po.run_offload_cmd("echo", "0000:00:00.0", "nvidia", 1)
        # check run_offload_cmd executing correct command
        mock_open.assert_called_with(["timeout", "1", "echo"],
                                     env=nv_env,
                                     stdout=subprocess.PIPE,
                                     universal_newlines=True)
        # check check_offload function get correct args
        po.check_offload.assert_called_with(["echo"], '0', 'NV', 1)

        # check offload failed
        po.find_card_id = MagicMock(return_value="0")
        po.find_card_name = MagicMock(return_value="NV")
        po.check_nv_offload_env = MagicMock(return_value=None)
        po.check_offload = MagicMock(return_value="")
        os.environ.copy = MagicMock(return_value={})
        po.check_result = True
        mock_open.side_effect = None
        with self.assertRaises(RuntimeError):
            po.run_offload_cmd("echo", "0000:00:00.0", "nvidia", 1)
        # check run_offload_cmd executing correct command
        mock_open.assert_called_with(["timeout", "1", "echo"],
                                     env=nv_env,
                                     stdout=subprocess.PIPE,
                                     universal_newlines=True)
        # check check_offload function get correct args
        po.check_offload.assert_called_with(["echo"], '0', 'NV', 1)


class ParseArgsTests(unittest.TestCase):
    def test_success(self):
        po = PrimeOffloader()
        # no arguments, load default
        args = []
        rv = po.parse_args(args)
        self.assertEqual(rv.command, "glxgears")
        self.assertEqual(rv.pci, "0000:00:02.0")
        self.assertEqual(rv.driver, "i915")
        self.assertEqual(rv.timeout, 0)

        # change command
        args = ["-c", "glxgears -fullscreen"]
        rv = po.parse_args(args)
        self.assertEqual(rv.command, "glxgears -fullscreen")
        self.assertEqual(rv.pci, "0000:00:02.0")
        self.assertEqual(rv.driver, "i915")
        self.assertEqual(rv.timeout, 0)

        # change pci
        args = ["-p", "0000:00:01.0"]
        rv = po.parse_args(args)
        self.assertEqual(rv.command, "glxgears")
        self.assertEqual(rv.pci, "0000:00:01.0")
        self.assertEqual(rv.driver, "i915")
        self.assertEqual(rv.timeout, 0)

        # change driver
        args = ["-d", "nvidia"]
        rv = po.parse_args(args)
        self.assertEqual(rv.command, "glxgears")
        self.assertEqual(rv.pci, "0000:00:02.0")
        self.assertEqual(rv.driver, "nvidia")
        self.assertEqual(rv.timeout, 0)

        # change timeout
        args = ["-t", "5"]
        rv = po.parse_args(args)
        self.assertEqual(rv.command, "glxgears")
        self.assertEqual(rv.pci, "0000:00:02.0")
        self.assertEqual(rv.driver, "i915")
        self.assertEqual(rv.timeout, 5)

        # change all
        args = ["-c", "glxgears -fullscreen",
                "-p", "0000:00:01.0",
                "-d", "nvidia",
                "-t", "5"]
        rv = po.parse_args(args)
        self.assertEqual(rv.command, "glxgears -fullscreen")
        self.assertEqual(rv.pci, "0000:00:01.0")
        self.assertEqual(rv.driver, "nvidia")
        self.assertEqual(rv.timeout, 5)


if __name__ == '__main__':
    unittest.main()
