#!/usr/bin/env python3
# encoding: utf-8
# Copyright 2025 Canonical Ltd.
# Written by:
#   Hector Cao <hector.cao@canonical.com>
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
from unittest.mock import (
    patch,
    mock_open,
    MagicMock
)
import pathlib
from argparse import Namespace
import json

from qatctl import (
    status_dev,
    list_dev,
    get_pci_ids,
    get_vfio_device,
    VFIOGroup,
    DeviceData,
    CounterType,
    CounterEngine,
    QatDeviceTelemetry,
    QatDevManager,
    Qat4xxxDevice,
    QatDeviceTelemetry,
    QatDeviceDebugfs,
    qatctl,
)

class TestVFIOGroup(unittest.TestCase):

    @patch("pathlib.Path.open", new_callable=mock_open, read_data="1\n")
    def test_numa_and_str(self, mock_file):
        mock_dev = MagicMock()
        mock_dev.bdf = "0000:00:01.0"

        vfio_group = VFIOGroup("10", mock_dev)

        self.assertEqual(vfio_group["numa_node"], "1")
        self.assertEqual(vfio_group["vfio_dev"], "/dev/vfio/10")
        json_str = str(vfio_group)
        self.assertEqual(isinstance(json.loads(json_str), dict), True)

class TestDeviceData(unittest.TestCase):

    @patch("qatctl.QatDevManager.filter_counter", return_value=True)
    def test_parse_and_avg(self, mock_filter):
        data = (
            "util_cph0 12\n"
            "util_cph1 14\n"
            "exec_ath0 3\n"
            "exec_ath1 7\n"
        )
        dd = DeviceData()
        dd.parse(data)

        self.assertIn("util_cph", dd)
        self.assertEqual(dd["util_cph"], [12, 14])
        self.assertEqual(dd.avg(CounterType.UTILIZATION, CounterEngine.CIPHER), 13.0)
        # non existing data for a given data type should return -1
        self.assertEqual(dd.avg(CounterType.UTILIZATION, CounterEngine.UNIFIED_CRYPTO_SLICE), -1)

class TestQatDeviceTelemetry(unittest.TestCase):

    DEBUGFS_TELEMETRY_PATH="/sys/kernel/debug/qat_4xxx_0000:00:01.0/telemetry"

    @patch("pathlib.Path.open", new_callable=mock_open, read_data="util_cph0 5\nutil_cph1 15\n")
    def test_collect(self, mock_file):
        telemetry_path = pathlib.Path(TestQatDeviceTelemetry.DEBUGFS_TELEMETRY_PATH)
        telemetry = QatDeviceTelemetry(telemetry_path)
        telemetry.collect()
        self.assertEqual(telemetry.debugfs_enabled, True)
        self.assertIn("device_data", telemetry)
        self.assertIn("util_cph", telemetry["device_data"])
        self.assertEqual(telemetry["device_data"]["util_cph"], [5, 15])

    @patch("pathlib.Path.open", side_effect=OSError("Failed to open file"))
    def test_collect_ko_open(self, mock_file):
        telemetry_path = pathlib.Path(TestQatDeviceTelemetry.DEBUGFS_TELEMETRY_PATH)
        telemetry = QatDeviceTelemetry(telemetry_path)
        telemetry.collect()
        self.assertEqual(telemetry["device_data"], {})

    @patch("pathlib.Path.open", new_callable=mock_open, read_data="junk_data")
    def test_collect_ko_data(self, mock_file):
        telemetry_path = pathlib.Path(TestQatDeviceTelemetry.DEBUGFS_TELEMETRY_PATH)
        telemetry = QatDeviceTelemetry(telemetry_path)
        telemetry.collect()
        self.assertEqual(telemetry["device_data"], {})

    def test_enable_telemetry_opens_correct_path_and_writes_1(self):
        telemetry_path = pathlib.Path(TestQatDeviceTelemetry.DEBUGFS_TELEMETRY_PATH)
        control_path = telemetry_path / "control"

        m = mock_open()

        # create an side effect for the open() operation and
        # record the filepath and open mode
        opened_paths = []
        def open_side_effect(self, *args, **kwargs):
            filepath=self
            mode=args[0]
            opened_paths.append((filepath,mode))
            return m()

        with patch("pathlib.Path.open", open_side_effect):
            telemetry = QatDeviceTelemetry(telemetry_path)
            telemetry.debugfs_enabled = True

            m.reset_mock()
            opened_paths.clear()
            telemetry.enable_telemetry()

        # Check that the correct path was used
        self.assertEqual(len(opened_paths), 1)

        filepath=opened_paths[0][0]
        mode=opened_paths[0][1]
        self.assertEqual(control_path, filepath)
        self.assertEqual('w+', mode)

        # Check that "1\n" was written to the file
        m().write.assert_called_once_with("1\n")


class TestQat4xxxDevice(unittest.TestCase):

    @patch("pathlib.Path.open", new_callable=mock_open)
    @patch("qatctl.get_pci_ids", return_value=[])
    @patch("qatctl.QatDeviceDebugfs")
    @patch("qatctl.get_vfio_device", return_value=11)
    def test_ctor_vf(self, mock_file, mock_pci_ids, mock_debugfs, mock_get_vfio):
        device_id = {"pf_id": "4940", "vf_id": "4941", "driver": "4xxx"}
        dev = Qat4xxxDevice(device_id, "00:00.0", is_virtual_function=True)
        self.assertEqual(dev.vfio['vfio_dev'], '/dev/vfio/11')
        self.assertEqual(hasattr(dev, "vfs"), False)
        # test repr
        self.assertEqual(str(dev), '00:00.0\t{\n  "vfio_dev": "/dev/vfio/11",\n  "numa_node": ""\n}')

    @patch("pathlib.Path.open", new_callable=mock_open)
    @patch("qatctl.get_pci_ids", return_value=['00:00.9'])
    @patch("qatctl.QatDeviceDebugfs")
    @patch("qatctl.get_vfio_device", return_value=11)
    def test_ctor_pf(self, mock_file, mock_pci_ids, mock_debugfs, mock_get_vfio):
        device_id = {"pf_id": "4940", "vf_id": "4941", "driver": "4xxx"}
        dev = Qat4xxxDevice(device_id, "00:00.0", is_virtual_function=False)
        self.assertEqual(hasattr(dev, "vfio"), False)
        self.assertEqual(dev.vfs[0].pci_id, "00:00.9")
        # test repr
        self.assertIn('00:00.0	/sys/bus/pci/devices/0000:00:00.0', str(dev))
        self.assertIn('VF: 00:00.9 - /dev/vfio/11', str(dev))

    @patch("pathlib.Path.open", new_callable=mock_open, read_data="up")
    @patch("qatctl.get_pci_ids", return_value=[])
    def test_state_properties(self, mock_file, mock_pci_ids):
        device_id = {"pf_id": "4940", "vf_id": "4941", "driver": "4xxx"}
        with patch("pathlib.Path.__truediv__", return_value=pathlib.Path("/mock/path")), \
             patch("qatctl.QatDeviceDebugfs"):
            dev = Qat4xxxDevice(device_id, "00:00.0")
            self.assertEqual(dev.state, "up")
        
    @patch("pathlib.Path.open", new_callable=mock_open, read_data="up")
    def test_set_state_and_cfg_services(self, mock_file):
        device_id = {"pf_id": "4940", "vf_id": "4941", "driver": "4xxx"}
        with patch("qatctl.get_pci_ids", return_value=[]), \
             patch("pathlib.Path.open", mock_open(read_data="up")), \
             patch("qatctl.QatDeviceDebugfs"):
            dev = Qat4xxxDevice(device_id, "00:00.0")
            dev.set_state("down")
            dev.set_cfg_services("sym")
            self.assertTrue(True)

    @patch("builtins.open", new_callable=mock_open, read_data="on")
    def test_auto_reset(self, mock_file):
        device_id = {"pf_id": "4940", "vf_id": "4941", "driver": "4xxx"}
        with patch("qatctl.get_pci_ids", return_value=[]),              patch("qatctl.QatDeviceDebugfs"):
            dev = Qat4xxxDevice(device_id, "00:00.0")
            # force patching open inside Path context
            with patch("pathlib.Path.open", mock_open(read_data="on")):
                self.assertEqual(dev.auto_reset, "on")

class TestQatDeviceDebugfs(unittest.TestCase):

    def test_qat_device_debugfs_init(self):
        mock_path = MagicMock()
        mock_path.glob.return_value = [MagicMock(name="dev_cfg")]
        with patch("qatctl.QatDeviceTelemetry"), \
             patch("qatctl.QatDeviceDebugfs.read", return_value="cfg") as mock_read:
            dbgfs = QatDeviceDebugfs(mock_path)
            self.assertIn("telemetry", dbgfs)
            self.assertEqual(dbgfs["dev_cfg"], "cfg")

    @patch("qatctl.QatDeviceDebugfs.read", return_value="cfg")
    def test_qat_device_debugfs_repr(self, mock_read):
        mock_path = MagicMock()
        mock_path.glob.return_value = [MagicMock(name="dev_cfg")]

        class DummyTelemetry(dict):
            def enable_telemetry(self):
                pass

            def __str__(self):
                return json.dumps({"device_data": {"util_cph": [1, 2]}})

        with patch("qatctl.QatDeviceTelemetry", return_value=DummyTelemetry()):
            dbgfs = QatDeviceDebugfs(mock_path)
            result = str(dbgfs)

            self.assertIn("telemetry", result)
            self.assertIn("dev_cfg", result)

class TestQatCtl(unittest.TestCase):

    @patch("subprocess.check_output")
    def test_get_pci_ids(self, mock_check_output):
        mock_check_output.return_value = "0000:00:01.0 Intel QAT\n0000:00:02.0 Intel QAT"
        result = get_pci_ids("4940", "8086")
        self.assertEqual(result, ["0000:00:01.0", "0000:00:02.0"])
        mock_check_output.assert_called_once_with(["lspci", "-d", "8086:4940"], universal_newlines=True)

    @patch("pathlib.Path.glob")
    def test_get_vfio_device(self, mock_glob):
        mock_vfio_file = MagicMock()
        mock_vfio_file.name = "10"

        # mock the glob() function of pathlib.Path
        # "/sys/kernel/iommu_groups/10/devices/"
        # object to return [0000:00:01.0]
        mock_device_path = MagicMock()
        mock_device_path.name = "0000:00:01.0"
        mock_iommu_path = MagicMock()
        mock_iommu_path.glob.return_value = [mock_device_path]

        with patch("pathlib.Path", side_effect=lambda path: mock_iommu_path if "iommu_groups" in path
                   else MagicMock(glob=MagicMock(return_value=[mock_vfio_file]))):
            # case 1: matching BDF in VFIO
            result = get_vfio_device("0000:00:01.0")
            self.assertEqual(result, 10)
            # case 2: non existing BDF in VFIO
            result = get_vfio_device("0000:00:01.1")
            self.assertEqual(result, 0)
            # case 3: empty /sys/kernel/iommu_groups/{vfio_device}/devices/
            mock_iommu_path.glob.return_value = []
            result = get_vfio_device("0000:00:01.0")
            self.assertEqual(result, 0)


class TestQatDevManager(unittest.TestCase):

    @patch("qatctl.get_pci_ids")
    @patch("qatctl.Qat4xxxDevice")
    @patch("builtins.print")
    def test_status_dev(self, mock_print, mock_dev, mock_get_ids):
        mock_dev_instance = MagicMock()
        mock_dev_instance.pci_id = "00:00.0"
        mock_dev_instance.pci_device_id = {"driver": "4xxx"}

        mock_get_ids.return_value = ["00:00.0"]
        mock_dev.return_value = mock_dev_instance

        manager = QatDevManager(filter_devs=["00:00.0"])
        args = Namespace(vfio = True)
        status_dev(args, manager)

    @patch("qatctl.get_pci_ids")
    @patch("qatctl.Qat4xxxDevice")
    @patch("builtins.print")
    def test_qat_dev_manager_list_devices(self, mock_print, mock_dev, mock_get_ids):
        mock_dev_instance = MagicMock()
        mock_dev_instance.pci_id = "00:00.0"
        mock_dev_instance.pci_device_id = {"driver": "4xxx"}

        mock_get_ids.return_value = ["00:00.0"]
        mock_dev.return_value = mock_dev_instance

        manager = QatDevManager(filter_devs=["00:00.0"])
        args = Namespace(short = True)
        # calling list_dev is equivalent to call manager.list_devices(short=True)
        list_dev(args, manager)

        # Gather printed calls and assert expected content
        printed_lines = [call.args[0] for call in mock_print.call_args_list]
        self.assertIn("00:00.0 4xxx", printed_lines)

    @patch("pathlib.Path.open", new_callable=mock_open, read_data="control")
    def test_qat_device_telemetry_control(self, mock_open_fn):
        telemetry_path = pathlib.Path("/mock/telemetry")
        telemetry = QatDeviceTelemetry(telemetry_path)
        telemetry.debugfs_enabled = True
        control_data = telemetry.control()
        self.assertEqual(control_data, "control")

    @patch("qatctl.get_pci_ids", return_value=["00:00.0"])
    @patch("qatctl.Qat4xxxDevice")
    def test_qat_dev_manager_set_cfg_services(self, mock_dev_class, mock_ids):
        mock_dev = MagicMock()
        mock_dev_class.return_value = mock_dev
        manager = QatDevManager(filter_devs=["00:00.0"])
        manager.set_cfg_services("sym")
        mock_dev.set_cfg_services.assert_called_with("sym")

    @patch("qatctl.get_pci_ids", return_value=["00:00.0"])
    @patch("qatctl.Qat4xxxDevice")
    def test_qat_dev_manager_get_state(self, mock_dev_class, mock_ids):
        mock_dev = MagicMock()
        mock_dev.state = "up"
        mock_dev_class.return_value = mock_dev
        manager = QatDevManager(filter_devs=["00:00.0"])
        with patch("builtins.print") as mock_print:
            manager.get_state()
            mock_print.assert_any_call("up")

    @patch("qatctl.get_pci_ids", return_value=["00:00.0"])
    @patch("qatctl.Qat4xxxDevice")
    def test_qat_dev_manager_print_vf(self, mock_dev_class, mock_ids):
        vf = MagicMock()
        vf.bdf = "0000:00:02.0"
        mock_dev = MagicMock()
        mock_dev.vfs = [vf]
        mock_dev_class.return_value = mock_dev
        manager = QatDevManager(filter_devs=["00:00.0"])
        with patch("builtins.print") as mock_print:
            manager.print_vf()
            mock_print.assert_any_call("0000:00:02.0")

    @patch("qatctl.get_pci_ids", return_value=["00:00.0"])
    @patch("qatctl.Qat4xxxDevice")
    def test_qat_dev_manager_print_vfio(self, mock_dev_class, mock_ids):
        vf = MagicMock()
        vf.vfio = {"vfio_dev": "/dev/vfio/10"}
        mock_dev = MagicMock()
        mock_dev.vfs = [vf]
        mock_dev_class.return_value = mock_dev
        manager = QatDevManager(filter_devs=["00:00.0"])
        with patch("builtins.print") as mock_print:
            manager.print_vfio()
            mock_print.assert_any_call("/dev/vfio/10")

class TestQatCli(unittest.TestCase):

    @patch("qatctl.QatDevManager")
    def test_qatctl_cli_set_state(self, MockManager):
        mock_mgr = MockManager.return_value
        args = Namespace(
            set_state="down", get_state=False, get_telemetry_data=False,
            set_service=None, func=None, devices=None
        )
        with patch("builtins.print") as mock_print:
            qatctl(args, None)
            mock_mgr.set_state.assert_called_once_with("down")
            mock_print.assert_any_call("Set device state : down")

    @patch("qatctl.QatDevManager")
    def test_qatctl_cli_set_service(self, MockManager):
        mock_mgr = MockManager.return_value
        args = Namespace(
            set_state=None, get_state=False, get_telemetry_data=False,
            set_service="sym", func=None, devices=None
        )
        with patch("builtins.print") as mock_print:
            qatctl(args, None)
            mock_mgr.set_cfg_services.assert_called_once_with("sym")
            mock_print.assert_any_call("Set device service : sym")
            mock_print.assert_any_call("Please restart qat service to update the config")

class TestQatCtlFinalCoverage(unittest.TestCase):

    def test_device_data_parse_skips_unfiltered(self):
        data = "unknown0 123\n"
        dd = DeviceData()
        with patch("qatctl.QatDevManager.filter_counter", return_value=False):
            dd.parse(data)
        self.assertEqual(dd, {})

    def test_device_data_avg_missing_key(self):
        dd = DeviceData()
        result = dd.avg(CounterType.UTILIZATION, CounterEngine.CIPHER)
        self.assertEqual(result, -1)

    def test_device_data_str(self):
        dd = DeviceData()
        dd["util_cph"] = [1, 2]
        s = str(dd)
        self.assertTrue("util_cph" in s)

    def test_telemetry_debugfs_disabled(self):
        path = pathlib.Path("/invalid/path")
        telemetry = QatDeviceTelemetry(path)
        self.assertFalse(telemetry.is_debugfs_enabled())

    @patch("qatctl.get_pci_ids", return_value=["00:00.0"])
    @patch("qatctl.Qat4xxxDevice")
    def test_qatctl_cli_get_state(self, mock_dev_class, mock_ids):
        mock_dev = MagicMock()
        mock_dev.state = "up"
        mock_dev_class.return_value = mock_dev
        args = Namespace(
            set_state=None, get_state=True, get_telemetry_data=False,
            set_service=None, func=None, devices=["00:00.0"]
        )
        with patch("builtins.print") as mock_print:
            qatctl(args, None)
            mock_print.assert_any_call("up")

    @patch("qatctl.get_pci_ids", return_value=["00:00.0"])
    @patch("qatctl.Qat4xxxDevice")
    def test_qatctl_cli_get_telemetry(self, mock_dev_class, mock_ids):
        telemetry = MagicMock()
        telemetry.collect.side_effect = RuntimeError("fail")  # 💥 trigger sys.exit

        mock_dev = MagicMock()
        mock_dev.debugfs = {"telemetry": telemetry}
        mock_dev_class.return_value = mock_dev

        args = Namespace(
            set_state=None, get_state=False, get_telemetry_data=True,
            set_service=None, func=None, devices=["00:00.0"]
        )

        with self.assertRaises(SystemExit):
            qatctl(args, None)

if __name__ == '__main__':
    unittest.main()
