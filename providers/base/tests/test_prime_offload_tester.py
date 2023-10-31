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
from unittest.mock import Mock, patch

from prime_offload_tester import *


class FindCardIdTests(unittest.TestCase):
    """
    This function should extract card id from debug file system by pci name
    (pci bus information)
    """

    @patch("subprocess.run")
    def test_pci_name_format_check(self, mock_run):
        # correct format
        mock_run.return_value = Mock(stdout="/sys/kernel/debug/dri/card0/name")
        card_id = PrimeOffloader().find_card_id("0000:00:00.0")
        self.assertEqual(card_id, "card0")

        # error format - with alphabet
        card_id = PrimeOffloader().find_card_id("000r:00:00.0")
        self.assertEqual(card_id, PrimeOffloaderError.NO_CARD_ID)

        # error format - digital position error
        card_id = PrimeOffloader().find_card_id("0000:00:000.0")
        self.assertEqual(card_id, PrimeOffloaderError.NO_CARD_ID)

    @patch("subprocess.run")
    def test_id_not_found(self, mock_run):
        # empty string
        mock_run.return_value = Mock(stdout="")
        card_id = PrimeOffloader().find_card_id("0000:00:00.0")
        self.assertEqual(card_id, PrimeOffloaderError.NO_CARD_ID)

        # None
        mock_run.return_value = Mock(stdout=None)
        card_id = PrimeOffloader().find_card_id("0000:00:00.0")
        self.assertEqual(card_id, PrimeOffloaderError.NO_CARD_ID)


class FindCardNameTests(unittest.TestCase):
    """
    This function should extract card name from lshw by pci name
    (pci bus information)
    """

    lshw_output = '[\
                  {\
                    "id" : "display",\
                    "class" : "display",\
                    "claimed" : true,\
                    "handle" : "PCI:0000:00:02.0",\
                    "description" : "VGA compatible controller",\
                    "product" : "TigerLake-LP GT2 [Iris Xe Graphics]",\
                    "vendor" : "Intel Corporation",\
                    "physid" : "2",\
                    "businfo" : "pci@0000:00:02.0",\
                    "logicalname" : "/dev/fb0",\
                    "version" : "01",\
                    "width" : 64,\
                    "clock" : 33000000,\
                    "configuration" : {\
                      "depth" : "32",\
                      "driver" : "i915",\
                      "latency" : "0",\
                      "mode" : "1920x1080",\
                      "resolution" : "1920,1080",\
                      "visual" : "truecolor",\
                      "xres" : "1920",\
                      "yres" : "1080"\
                    },\
                    "capabilities" : {\
                      "pciexpress" : "PCI Express",\
                      "msi" : "Message Signalled Interrupts",\
                      "pm" : "Power Management",\
                      "vga_controller" : true,\
                      "bus_master" : "bus mastering",\
                      "cap_list" : "PCI capabilities listing",\
                      "rom" : "extension ROM",\
                      "fb" : "framebuffer"\
                    }\
                  }\
                ]'

    @patch("subprocess.run")
    def test_name_found_check(self, mock_run):
        mock_run.return_value = Mock(stdout=self.lshw_output)
        card_name = PrimeOffloader().find_card_name("0000:00:02.0")
        self.assertEqual(card_name, "TigerLake-LP GT2 [Iris Xe Graphics]")

    @patch("subprocess.run")
    def test_name_not_found_check(self, mock_run):
        # pci_name error
        mock_run.return_value = Mock(stdout=self.lshw_output)
        card_name = PrimeOffloader().find_card_name("0000:00:00.0")
        self.assertEqual(card_name, None)

        # empty string
        mock_run.return_value = Mock(stdout="")
        card_name = PrimeOffloader().find_card_name("0000:00:00.0")
        self.assertEqual(card_name, None)

        # None
        mock_run.return_value = Mock(stdout=None)
        card_name = PrimeOffloader().find_card_name("0000:00:00.0")
        self.assertEqual(card_name, None)


class CheckOffloadTests(unittest.TestCase):
    """
    This function will check process is showed in specific dri devide
    debug file system
    """

    @patch("subprocess.run")
    def test_offload_succ_check(self, mock_run):
        cmd = "echo"
        mock_run.return_value = Mock(stdout=cmd)
        pf = PrimeOffloader()
        rv = pf.check_offload(cmd, "card_id", "card_name")
        self.assertEqual(rv, None)
        self.assertEqual(pf.check_result,
                         PrimeOffloaderError.NO_ERROR)

    @patch("subprocess.run")
    def test_offload_fail_check(self, mock_run):
        # cmd, card id and card name are checked and won't be None

        # cmd isn't showed in debug file system
        # empty string
        cmd = "echo"
        mock_run.return_value = Mock(stdout="")
        pf = PrimeOffloader()
        rv = pf.check_offload(cmd, "card_id", "card_name")
        self.assertEqual(rv, None)
        self.assertEqual(pf.check_result,
                         PrimeOffloaderError.OFFLOAD_FAIL)

        # None
        cmd = "echo"
        mock_run.return_value = Mock(stdout=None)
        pf = PrimeOffloader()
        rv = pf.check_offload(cmd, "card_id", "card_name")
        self.assertEqual(rv, None)
        self.assertEqual(pf.check_result,
                         PrimeOffloaderError.OFFLOAD_FAIL)

        # OS Error
        # Missing file or permissions
        cmd = "echo"
        mock_run.side_effect = OSError
        pf = PrimeOffloader()
        rv = pf.check_offload(cmd, "card_id", "card_name")
        self.assertEqual(rv, None)
        self.assertEqual(pf.check_result,
                         PrimeOffloaderError.OFFLOAD_FAIL)


class CheckNvOffloadEnvTests(unittest.TestCase):
    """
    This function will check this system could use prime offload or not.
    Only on-demand mode is supported for NV driver.
    """

    @patch("subprocess.run")
    def test_no_prime_select_check(self, mock_run):
        mock_run.return_value = Mock(stdout="")
        rv = PrimeOffloader().check_nv_offload_env()
        self.assertEqual(rv, PrimeOffloaderError.NO_ERROR)

    @patch("subprocess.run")
    def test_on_demand_check(self, mock_run):
        # with nv driver, not on-demand mode
        mock_run.return_value = Mock(stdout="prime-select")
        rv = PrimeOffloader().check_nv_offload_env()
        self.assertEqual(rv, PrimeOffloaderError.NOT_SUPPORT_NV_PRIME)

    @patch("subprocess.run")
    def test_nvlink_check(self, mock_run):
        # with nv driver, on-demand mode. This might be NVLINK environment
        mock_run.return_value = Mock(stdout="prime-select on-demand")
        rv = PrimeOffloader().check_nv_offload_env()
        self.assertEqual(rv, PrimeOffloaderError.NOT_SUPPORT_NV_PRIME)

        # with nv driver, on-demand mode, nv driver error
        mock_run.return_value = Mock(stdout="prime-select on-demand error")
        rv = PrimeOffloader().check_nv_offload_env()
        self.assertEqual(rv, PrimeOffloaderError.NV_DRIVER_ERROR)

        # with nv driver, on-demand mode, no nv driver error
        mock_run.side_effect = [Mock(stdout="prime-select on-demand"),
                                Mock(stdout="prime-select on-demand"),
                                Mock(stdout="")]
        rv = PrimeOffloader().check_nv_offload_env()
        self.assertEqual(rv, PrimeOffloaderError.NO_ERROR)


class RunOffloadCmdTests(unittest.TestCase):
    """
    This function is the entry point to run the command with prime offload,
    if the environment is supported.
    """

    def test_condition_check(self):
        # no card id
        pf = PrimeOffloader()
        pf.find_card_id = Mock(return_value=PrimeOffloaderError.NO_CARD_ID)
        rv = pf.run_offload_cmd("echo", "0000:00:00.0", "driver", 0)
        self.assertEqual(rv, PrimeOffloaderError.NO_CARD_ID)

        # no card name
        pf.find_card_id = Mock(return_value="card0")
        pf.find_card_name = Mock(return_value=None)
        rv = pf.run_offload_cmd("echo", "0000:00:00.0", "driver", 0)
        self.assertEqual(rv, PrimeOffloaderError.NO_CARD_NAME)

    @patch("subprocess.Popen")
    def test_offload_cmd_check(self, mock_open):
        # non NV driver
        pf = PrimeOffloader()
        pf.find_card_id = Mock(return_value="card0")
        pf.find_card_name = Mock(return_value="Intel")
        pf.check_nv_offload_env =\
            Mock(return_value=PrimeOffloaderError.NO_ERROR)
        pf.check_offload = Mock(return_value="")
        rv = pf.run_offload_cmd("echo", "0000:00:00.0", "xxx", 0)
        # check run_offload_cmd executing correct command
        mock_open.assert_called_with('DRI_PRIME=pci-0000_00_00_0 echo',
                                     shell=True,
                                     stdout=subprocess.PIPE,
                                     universal_newlines=True)
        # check check_offload function get correct args
        pf.check_offload.assert_called_with('echo', 'card0', 'Intel')

        # non NV driver with timeout setting
        pf = PrimeOffloader()
        pf.find_card_id = Mock(return_value="card0")
        pf.find_card_name = Mock(return_value="Intel")
        pf.check_nv_offload_env =\
            Mock(return_value=PrimeOffloaderError.NO_ERROR)
        pf.check_offload = Mock(return_value="")
        rv = pf.run_offload_cmd("echo", "0000:00:00.0", "xxx", 1)
        # check run_offload_cmd executing correct command
        mock_open.assert_called_with("DRI_PRIME=pci-0000_00_00_0 "
                                     "timeout 1 echo",
                                     shell=True,
                                     stdout=subprocess.PIPE,
                                     universal_newlines=True)
        # check check_offload function get correct args
        pf.check_offload.assert_called_with('echo', 'card0', 'Intel')

        # NV driver
        pf = PrimeOffloader()
        pf.find_card_id = Mock(return_value="card0")
        pf.find_card_name = Mock(return_value="NV")
        pf.check_nv_offload_env =\
            Mock(return_value=PrimeOffloaderError.NO_ERROR)
        pf.check_offload = Mock(return_value="")
        rv = pf.run_offload_cmd("echo", "0000:00:00.0", "nvidia", 0)
        # check run_offload_cmd executing correct command
        mock_open.assert_called_with('__NV_PRIME_RENDER_OFFLOAD=1'
                                     ' __GLX_VENDOR_LIBRARY_NAME=nvidia echo',
                                     shell=True,
                                     stdout=subprocess.PIPE,
                                     universal_newlines=True)
        # check check_offload function get correct args
        pf.check_offload.assert_called_with('echo', 'card0', 'NV')

        # Not support nvidia prime
        pf = PrimeOffloader()
        pf.find_card_id = Mock(return_value="card0")
        pf.find_card_name = Mock(return_value="NV")
        pf.check_nv_offload_env =\
            Mock(return_value=PrimeOffloaderError.NOT_SUPPORT_NV_PRIME)
        pf.check_offload = Mock(return_value="")
        rv = pf.run_offload_cmd("echo", "0000:00:00.0", "nvidia", 0)
        # check run_offload_cmd executing correct command
        mock_open.assert_called_with('echo',
                                     shell=True,
                                     stdout=subprocess.PIPE,
                                     universal_newlines=True)
        self.assertEqual(rv, PrimeOffloaderError.NO_ERROR)

class parseArgsTests(unittest.TestCase):
    def test_success(self):
        pf = PrimeOffloader()
        # no arguments, load default
        args = []
        rv = pf.parse_args(args)
        self.assertEqual(rv.command, "glxgears")
        self.assertEqual(rv.pci, "0000:00:02.0")
        self.assertEqual(rv.driver, "i915")
        self.assertEqual(rv.timeout, 0)

        pf = PrimeOffloader()
        # change command
        args = ["-c", "glxgears -fullscreen"]
        rv = pf.parse_args(args)
        self.assertEqual(rv.command, "glxgears -fullscreen")
        self.assertEqual(rv.pci, "0000:00:02.0")
        self.assertEqual(rv.driver, "i915")
        self.assertEqual(rv.timeout, 0)

        pf = PrimeOffloader()
        # change pci
        args = ["-p", "0000:00:01.0"]
        rv = pf.parse_args(args)
        self.assertEqual(rv.command, "glxgears")
        self.assertEqual(rv.pci, "0000:00:01.0")
        self.assertEqual(rv.driver, "i915")
        self.assertEqual(rv.timeout, 0)

        pf = PrimeOffloader()
        # change driver
        args = ["-d", "nvidia"]
        rv = pf.parse_args(args)
        self.assertEqual(rv.command, "glxgears")
        self.assertEqual(rv.pci, "0000:00:02.0")
        self.assertEqual(rv.driver, "nvidia")
        self.assertEqual(rv.timeout, 0)

        pf = PrimeOffloader()
        # change timeout
        args = ["-t", "5"]
        rv = pf.parse_args(args)
        self.assertEqual(rv.command, "glxgears")
        self.assertEqual(rv.pci, "0000:00:02.0")
        self.assertEqual(rv.driver, "i915")
        self.assertEqual(rv.timeout, 5)

        pf = PrimeOffloader()
        # change all
        args = ["-c", "glxgears -fullscreen",
                "-p", "0000:00:01.0",
                "-d", "nvidia",
                "-t", "5"]
        rv = pf.parse_args(args)
        self.assertEqual(rv.command, "glxgears -fullscreen")
        self.assertEqual(rv.pci, "0000:00:01.0")
        self.assertEqual(rv.driver, "nvidia")
        self.assertEqual(rv.timeout, 5)



if __name__ == '__main__':
    unittest.main()
