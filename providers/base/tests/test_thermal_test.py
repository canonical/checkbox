#!/usr/bin/env python3
# This file is part of Checkbox.
#
# Copyright 2025 Canonical Ltd.
# Written by:
#   Checkbox Contributors
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

import argparse
import unittest
from unittest.mock import patch, mock_open, MagicMock

import thermal_test


class HelperTests(unittest.TestCase):
    def test_read_ok(self):
        with patch("builtins.open", mock_open(read_data=" value \n")):
            self.assertEqual(thermal_test._read("/some/path"), "value")

    def test_read_missing(self):
        with patch("builtins.open", side_effect=OSError):
            self.assertIsNone(thermal_test._read("/some/path"))

    def test_glob_read_skips_unreadable(self):
        with patch("thermal_test.glob.glob", return_value=["/a", "/b"]), patch(
            "thermal_test._read", side_effect=["x", None]
        ):
            self.assertEqual(
                list(thermal_test._glob_read("/*")), [("/a", "x")]
            )


class SysfsDirTests(unittest.TestCase):
    def test_rapl_present(self):
        with patch("thermal_test.os.path.isdir", return_value=True):
            thermal_test.check_rapl(None)  # no raise

    def test_rapl_absent(self):
        with patch("thermal_test.os.path.isdir", return_value=False), patch(
            "thermal_test.glob.glob", return_value=[]
        ):
            with self.assertRaises(SystemExit):
                thermal_test.check_rapl(None)

    def test_rapl_mmio_present(self):
        with patch("thermal_test.os.path.isdir", return_value=True):
            thermal_test.check_rapl_mmio(None)

    def test_rapl_mmio_absent(self):
        with patch("thermal_test.os.path.isdir", return_value=False):
            with self.assertRaises(SystemExit):
                thermal_test.check_rapl_mmio(None)

    def test_pstate_present(self):
        with patch("thermal_test.os.path.isdir", return_value=True):
            thermal_test.check_pstate(None)

    def test_pstate_absent(self):
        with patch("thermal_test.os.path.isdir", return_value=False), patch(
            "thermal_test.glob.glob", return_value=[]
        ):
            with self.assertRaises(SystemExit):
                thermal_test.check_pstate(None)


class PowerclampTests(unittest.TestCase):
    def test_present(self):
        with patch(
            "thermal_test._glob_read",
            return_value=[("/t", "intel_powerclamp")],
        ):
            thermal_test.check_powerclamp(None)

    def test_absent_is_advisory(self):
        # Absence is advisory (non-fatal) per upstream behaviour.
        with patch("thermal_test._glob_read", return_value=[("/t", "other")]):
            self.assertIsNone(thermal_test.check_powerclamp(None))


class X86PkgTempTests(unittest.TestCase):
    def test_present(self):
        with patch(
            "thermal_test._glob_read",
            return_value=[("/z", "x86_pkg_temp")],
        ):
            thermal_test.check_x86_pkg_temp(None)

    def test_accepts_equivalent_names(self):
        for name in ("pkg-temp-0", "soc_dts0"):
            with patch("thermal_test._glob_read", return_value=[("/z", name)]):
                thermal_test.check_x86_pkg_temp(None)

    def test_absent(self):
        with patch("thermal_test._glob_read", return_value=[("/z", "cpu")]):
            with self.assertRaises(SystemExit):
                thermal_test.check_x86_pkg_temp(None)


class CpuThermalTests(unittest.TestCase):
    def test_zone_type_match(self):
        with patch(
            "thermal_test._glob_read",
            return_value=[("/z", "B0D4")],
        ):
            thermal_test.check_cpu_thermal(None)

    def test_coretemp_fallback(self):
        def side_effect(pattern):
            if "thermal_zone" in pattern:
                return [("/z", "acpitz")]
            return [("/h", "coretemp")]

        with patch("thermal_test._glob_read", side_effect=side_effect):
            thermal_test.check_cpu_thermal(None)

    def test_none(self):
        with patch("thermal_test._glob_read", return_value=[("/z", "acpitz")]):
            with self.assertRaises(SystemExit):
                thermal_test.check_cpu_thermal(None)


class TripPointTests(unittest.TestCase):
    def test_zone_has_valid_trip_point(self):
        with patch(
            "thermal_test._glob_read",
            return_value=[("/tp0", "0"), ("/tp1", "95000")],
        ):
            self.assertTrue(thermal_test._zone_has_valid_trip_point("/z"))

    def test_zone_no_valid_trip_point(self):
        with patch(
            "thermal_test._glob_read",
            return_value=[("/tp0", "0"), ("/tp1", "bad")],
        ):
            self.assertFalse(thermal_test._zone_has_valid_trip_point("/z"))

    def test_skips_ignored_zone_types(self):
        with patch("thermal_test.glob.glob", return_value=["/z"]), patch(
            "thermal_test._read", return_value="x86_pkg_temp"
        ), patch("thermal_test._zone_has_valid_trip_point") as valid:
            thermal_test.check_trip_points(None)
            valid.assert_not_called()

    def test_fail_on_invalid(self):
        with patch("thermal_test.glob.glob", return_value=["/z"]), patch(
            "thermal_test._read", return_value="acpitz"
        ), patch(
            "thermal_test._zone_has_valid_trip_point", return_value=False
        ), patch(
            "thermal_test._glob_read", return_value=[]
        ):
            with self.assertRaises(SystemExit):
                thermal_test.check_trip_points(None)

    def test_pass_on_valid(self):
        with patch("thermal_test.glob.glob", return_value=["/z"]), patch(
            "thermal_test._read", return_value="acpitz"
        ), patch("thermal_test._zone_has_valid_trip_point", return_value=True):
            thermal_test.check_trip_points(None)


class ProcThermalTests(unittest.TestCase):
    def test_loaded(self):
        args = argparse.Namespace(path="/devices/pci0000:00/0000:00:04.0")
        with patch("thermal_test.os.path.exists", return_value=True):
            thermal_test.check_proc_thermal(args)

    def test_not_loaded(self):
        args = argparse.Namespace(path="/devices/pci0000:00/0000:00:04.0")
        with patch("thermal_test.os.path.exists", return_value=False):
            with self.assertRaises(SystemExit):
                thermal_test.check_proc_thermal(args)


class ThermaldTests(unittest.TestCase):
    def test_thinkpad_lapmode_skips(self):
        with patch("thermal_test._thinkpad_lapmode", return_value=True):
            thermal_test.check_thermald(None)

    def test_active(self):
        with patch(
            "thermal_test._thinkpad_lapmode", return_value=False
        ), patch(
            "thermal_test.subprocess.run",
            return_value=MagicMock(returncode=0),
        ):
            thermal_test.check_thermald(None)

    def test_inactive(self):
        with patch(
            "thermal_test._thinkpad_lapmode", return_value=False
        ), patch(
            "thermal_test.subprocess.run",
            return_value=MagicMock(returncode=3),
        ):
            with self.assertRaises(SystemExit):
                thermal_test.check_thermald(None)


class CpuSupportTests(unittest.TestCase):
    def test_supported_no_match(self):
        with patch(
            "thermal_test.subprocess.run",
            return_value=MagicMock(returncode=1, stdout=""),
        ):
            thermal_test.check_cpu_support(None)

    def test_supported_empty_stdout(self):
        with patch(
            "thermal_test.subprocess.run",
            return_value=MagicMock(returncode=0, stdout="  \n"),
        ):
            thermal_test.check_cpu_support(None)

    def test_unsupported(self):
        line = "thermald: Unsupported cpu model or platform"
        with patch(
            "thermal_test.subprocess.run",
            return_value=MagicMock(returncode=0, stdout=line + "\n"),
        ):
            with self.assertRaises(SystemExit):
                thermal_test.check_cpu_support(None)


class ThermalPolicyTests(unittest.TestCase):
    def _args(self):
        return argparse.Namespace(path="/devices/platform/INT3400:00")

    def test_no_node(self):
        with patch("thermal_test.os.path.exists", return_value=False):
            thermal_test.check_thermal_policy(self._args())

    def test_valid_policy(self):
        with patch("thermal_test.os.path.exists", return_value=True), patch(
            "thermal_test._read", return_value="3A95C389-..."
        ):
            thermal_test.check_thermal_policy(self._args())

    def test_invalid_policy(self):
        with patch("thermal_test.os.path.exists", return_value=True), patch(
            "thermal_test._read", return_value="INVALID"
        ):
            with self.assertRaises(SystemExit):
                thermal_test.check_thermal_policy(self._args())


class UnknownCondTests(unittest.TestCase):
    def test_clean(self):
        with patch(
            "thermal_test.subprocess.run",
            return_value=MagicMock(returncode=1),
        ):
            thermal_test.check_unknown_cond(None)

    def test_found(self):
        with patch(
            "thermal_test.subprocess.run",
            return_value=MagicMock(returncode=0),
        ):
            with self.assertRaises(SystemExit):
                thermal_test.check_unknown_cond(None)


class AdaptiveFallbackTests(unittest.TestCase):
    def test_ok(self):
        with patch("thermal_test.os.path.exists", return_value=False):
            thermal_test.check_adaptive_fallback(None)

    def test_sentinel_present(self):
        with patch("thermal_test.os.path.exists", return_value=True):
            with self.assertRaises(SystemExit):
                thermal_test.check_adaptive_fallback(None)


class MainTests(unittest.TestCase):
    def test_dispatch(self):
        with patch("thermal_test.check_rapl") as func:
            thermal_test.main(["rapl"])
            func.assert_called_once()

    def test_dispatch_with_path(self):
        with patch("thermal_test.check_proc_thermal") as func:
            thermal_test.main(["proc-thermal", "/devices/x"])
            func.assert_called_once()
            self.assertEqual(func.call_args[0][0].path, "/devices/x")

    def test_requires_command(self):
        with self.assertRaises(SystemExit):
            thermal_test.main([])


if __name__ == "__main__":
    unittest.main()
