#!/usr/bin/env python3
# This file is part of Checkbox.
#
# Copyright 2026 Canonical Ltd.
# Authors:
#   Zhongning Li <zhongning.li@canonical.com>
#
# Checkbox is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License version 3,
# as published by the Free Software Foundation.
#
# Checkbox is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Checkbox.  If not, see <http://www.gnu.org/licenses/>.

import ctypes
import tempfile
from pathlib import Path
from unittest import TestCase
import unittest
from unittest.mock import MagicMock, patch

from checkbox_support.ethtool.ts_info import (
    ETHTOOL_GET_TS_INFO,
    SIOCETHTOOL,
    ethtool_ts_info,
    get_ts_info,
    is_ptp_capable,
    _is_ethernet_interface,
)


class TestEthtoolTsInfoStr(TestCase):
    def test_str_pretty_prints_scalars_and_arrays(self):
        info = ethtool_ts_info()
        info.cmd = ETHTOOL_GET_TS_INFO
        info.so_timestamping = 0x1F
        info.phc_index = 2
        info.tx_types = 7
        info.tx_reserved[0] = 1
        info.tx_reserved[1] = 2
        info.tx_reserved[2] = 3
        info.rx_filters = 9
        info.rx_reserved[0] = 4
        info.rx_reserved[1] = 5
        info.rx_reserved[2] = 6

        expected = (
            "ethtool_ts_info(cmd={}, so_timestamping=31, phc_index=2, "
            "tx_types=7, tx_reserved=[1, 2, 3], rx_filters=9, "
            "rx_reserved=[4, 5, 6])"
        ).format(ETHTOOL_GET_TS_INFO)
        self.assertEqual(str(info), expected)

    def test_str_default_values(self):
        info = ethtool_ts_info()
        expected = (
            "ethtool_ts_info(cmd=0, so_timestamping=0, phc_index=0, "
            "tx_types=0, tx_reserved=[0, 0, 0], rx_filters=0, "
            "rx_reserved=[0, 0, 0])"
        )
        self.assertEqual(str(info), expected)


class TestIsEthernetInterface(TestCase):
    def _make_sys_class_net(
        self,
        tmp_dir,
        has_type=True,
        is_ether=True,
        has_device=True,
        is_wifi=False,
    ):
        iface_dir = Path(tmp_dir) / "enp1s0"
        iface_dir.mkdir(parents=True)
        if has_type:
            (iface_dir / "type").write_text("1\n" if is_ether else "772\n")
        if has_device:
            (iface_dir / "device").mkdir()
        if is_wifi:
            (iface_dir / "phy80211").mkdir()
        return iface_dir.parent

    def test_physical_ethernet_interface(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            base = self._make_sys_class_net(tmp_dir)
            with patch(
                "checkbox_support.ethtool.ts_info.Path",
                side_effect=lambda p: (
                    base if "/sys/class/net" in p else Path(p)
                ),
            ):
                self.assertTrue(_is_ethernet_interface("enp1s0"))

    def test_not_ether_type(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            base = self._make_sys_class_net(tmp_dir, is_ether=False)
            with patch(
                "checkbox_support.ethtool.ts_info.Path",
                side_effect=lambda p: (
                    base if "/sys/class/net" in p else Path(p)
                ),
            ):
                self.assertFalse(_is_ethernet_interface("enp1s0"))

    def test_no_device_dir(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            base = self._make_sys_class_net(tmp_dir, has_device=False)
            with patch(
                "checkbox_support.ethtool.ts_info.Path",
                side_effect=lambda p: (
                    base if "/sys/class/net" in p else Path(p)
                ),
            ):
                self.assertFalse(_is_ethernet_interface("enp1s0"))

    def test_wifi_interface(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            base = self._make_sys_class_net(tmp_dir, is_wifi=True)
            with patch(
                "checkbox_support.ethtool.ts_info.Path",
                side_effect=lambda p: (
                    base if "/sys/class/net" in p else Path(p)
                ),
            ):
                self.assertFalse(_is_ethernet_interface("enp1s0"))

    def test_missing_interface_returns_false(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            base = Path(tmp_dir)
            with patch(
                "checkbox_support.ethtool.ts_info.Path",
                side_effect=lambda p: (
                    base if "/sys/class/net" in p else Path(p)
                ),
            ):
                self.assertFalse(_is_ethernet_interface("does-not-exist"))


class TestGetTsInfo(TestCase):
    def _fake_ioctl(self, fd, request, arg, mutate_flag=False):
        # mock kernel response to the SIOCETHTOOL ioctl
        self.assertEqual(request, SIOCETHTOOL)
        info_ptr = ctypes.cast(
            arg.ifr_ifru.ifr_data, ctypes.POINTER(ethtool_ts_info)
        )
        info_ptr.contents.so_timestamping = 0x1F
        info_ptr.contents.phc_index = 3
        info_ptr.contents.tx_types = 7
        info_ptr.contents.rx_filters = 9
        return 0

    @patch("checkbox_support.ethtool.ts_info._is_ethernet_interface")
    @patch("checkbox_support.ethtool.ts_info.fcntl.ioctl")
    def test_get_ts_info_populates_struct(
        self, ioctl_mock: MagicMock, is_ethernet_mock: MagicMock
    ):
        is_ethernet_mock.return_value = True
        ioctl_mock.side_effect = self._fake_ioctl

        info = get_ts_info("enp1s0")

        self.assertGreaterEqual(len(ioctl_mock.call_args_list), 1)
        self.assertEqual(info.cmd, ETHTOOL_GET_TS_INFO)
        self.assertEqual(info.phc_index, 3)
        self.assertEqual(info.so_timestamping, 0x1F)
        self.assertEqual(info.tx_types, 7)
        self.assertEqual(info.rx_filters, 9)

    @patch("checkbox_support.ethtool.ts_info._is_ethernet_interface")
    @patch("checkbox_support.ethtool.ts_info.fcntl.ioctl")
    def test_get_ts_info_warns_on_non_ethernet(
        self, ioctl_mock, is_ethernet_mock
    ):
        is_ethernet_mock.return_value = False
        ioctl_mock.side_effect = self._fake_ioctl

        with self.assertLogs(level="WARNING"):
            get_ts_info("wlp1s0")


class TestIsPtpCapable(TestCase):
    @patch("checkbox_support.ethtool.ts_info.os.path.exists")
    @patch("checkbox_support.ethtool.ts_info.get_ts_info")
    def test_ptp_capable(self, get_ts_info_mock, exists_mock):
        get_ts_info_mock.return_value = ethtool_ts_info(phc_index=0)
        exists_mock.return_value = True

        self.assertTrue(is_ptp_capable("enp1s0"))
        exists_mock.assert_called_once_with("/dev/ptp0")

    @patch("checkbox_support.ethtool.ts_info.os.path.exists")
    @patch("checkbox_support.ethtool.ts_info.get_ts_info")
    def test_no_phc_device(self, get_ts_info_mock, exists_mock):
        get_ts_info_mock.return_value = ethtool_ts_info(phc_index=-1)
        exists_mock.return_value = False

        self.assertFalse(is_ptp_capable("enp1s0"))

    @patch("checkbox_support.ethtool.ts_info.os.path.exists")
    @patch("checkbox_support.ethtool.ts_info.get_ts_info")
    def test_phc_index_valid_but_device_missing(
        self, get_ts_info_mock, exists_mock
    ):
        get_ts_info_mock.return_value = ethtool_ts_info(phc_index=1)
        exists_mock.return_value = False

        self.assertFalse(is_ptp_capable("enp1s0"))


if __name__ == "__main__":
    unittest.main()
