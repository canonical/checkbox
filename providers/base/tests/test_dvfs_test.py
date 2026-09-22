#!/usr/bin/env python3
# This file is part of Checkbox.
#
# Copyright 2026 Canonical Ltd.
# Written by:
#   Patrick Chang <patrick.chang@canonical.com>
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

import os
import tempfile
import unittest
from io import StringIO
from pathlib import Path
from unittest.mock import patch

import dvfs_test


class DvfsTestCaseBase(unittest.TestCase):
    """Sets up a fake /sys/class/devfreq/<dev>/ tree under a tempdir and
    points dvfs_test.DEVFREQ_ROOT at it for the duration of the test."""

    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmpdir.cleanup)
        self.tmp_path = Path(self._tmpdir.name)
        self._orig_root = dvfs_test.DEVFREQ_ROOT
        dvfs_test.DEVFREQ_ROOT = self.tmp_path
        self.addCleanup(self._restore_root)

    def _restore_root(self):
        dvfs_test.DEVFREQ_ROOT = self._orig_root

    def make_device(
        self,
        name,
        governor="simple_ondemand",
        available_governors=(
            "simple_ondemand",
            "userspace",
            "powersave",
            "performance",
        ),
        available_frequencies=(100, 200, 300),
        cur_freq=200,
    ):
        dev_dir = self.tmp_path / name
        dev_dir.mkdir(parents=True, exist_ok=True)
        (dev_dir / "governor").write_text(governor)
        (dev_dir / "available_governors").write_text(
            " ".join(available_governors)
        )
        (dev_dir / "available_frequencies").write_text(
            " ".join(str(f) for f in available_frequencies)
        )
        (dev_dir / "cur_freq").write_text(str(cur_freq))
        return dev_dir


class TestListDevfreqDevices(DvfsTestCaseBase):
    def test_empty_root_returns_empty_list(self):
        self.assertEqual(dvfs_test.list_devfreq_devices(), [])

    def test_missing_root_returns_empty_list(self):
        dvfs_test.DEVFREQ_ROOT = self.tmp_path / "does-not-exist"
        self.assertEqual(dvfs_test.list_devfreq_devices(), [])

    def test_finds_devices_with_governor_node(self):
        self.make_device("13000000.gpu")
        self.make_device("soc:vpu_devfreq")
        # A directory without a "governor" node must be ignored.
        (self.tmp_path / "not-a-devfreq-dev").mkdir()
        self.assertEqual(
            dvfs_test.list_devfreq_devices(),
            ["13000000.gpu", "soc:vpu_devfreq"],
        )


class TestGovernorsAndFrequencies(DvfsTestCaseBase):
    def test_get_available_governors(self):
        self.make_device(
            "dev0", available_governors=("userspace", "performance")
        )
        self.assertEqual(
            dvfs_test.get_available_governors("dev0"),
            ["userspace", "performance"],
        )

    def test_get_available_frequencies(self):
        self.make_device("dev0", available_frequencies=(300, 100, 200))
        self.assertEqual(
            dvfs_test.get_available_frequencies("dev0"), [300, 100, 200]
        )

    def test_missing_device_returns_empty(self):
        self.assertEqual(dvfs_test.get_available_governors("nope"), [])
        self.assertEqual(dvfs_test.get_available_frequencies("nope"), [])

    def test_unexpected_content_returns_empty(self):
        dev_dir = self.make_device("dev0")
        (dev_dir / "available_frequencies").write_text("not-a-number")
        self.assertEqual(dvfs_test.get_available_frequencies("dev0"), [])


class TestParseExpectedDvfsDevices(unittest.TestCase):
    def test_single_device(self):
        spec = "13000000.gpu|userspace,powersave,performance"
        self.assertEqual(
            dvfs_test.parse_expected_dvfs_devices(spec),
            {"13000000.gpu": ["userspace", "powersave", "performance"]},
        )

    def test_multiple_devices(self):
        spec = (
            "13000000.gpu|userspace,powersave,performance,simple_ondemand "
            "soc:vpu_devfreq|userspace,powersave"
        )
        self.assertEqual(
            dvfs_test.parse_expected_dvfs_devices(spec),
            {
                "13000000.gpu": [
                    "userspace",
                    "powersave",
                    "performance",
                    "simple_ondemand",
                ],
                "soc:vpu_devfreq": ["userspace", "powersave"],
            },
        )

    def test_invalid_entry_raises(self):
        with self.assertRaises(SystemExit):
            dvfs_test.parse_expected_dvfs_devices("no-pipe-here")


class TestCmdDetect(DvfsTestCaseBase):
    def test_fails_when_no_devices(self):
        with self.assertRaises(SystemExit):
            dvfs_test.cmd_detect()

    @patch.dict(os.environ, {}, clear=True)
    def test_passes_when_devices_present(self):
        self.make_device("13000000.gpu")
        dvfs_test.cmd_detect()

    @patch.dict(
        os.environ,
        {
            "EXPECTED_DVFS_DEVICES": (
                "13000000.gpu|simple_ondemand,userspace,powersave,"
                "performance"
            )
        },
    )
    def test_passes_when_expected_matches(self):
        self.make_device("13000000.gpu")
        dvfs_test.cmd_detect()

    @patch.dict(
        os.environ,
        {"EXPECTED_DVFS_DEVICES": "13000000.gpu|userspace,powersave"},
    )
    def test_fails_when_expected_governors_mismatch(self):
        self.make_device("13000000.gpu")
        with self.assertRaises(SystemExit):
            dvfs_test.cmd_detect()

    @patch.dict(
        os.environ, {"EXPECTED_DVFS_DEVICES": "missing-device|userspace"}
    )
    def test_fails_when_expected_device_missing(self):
        self.make_device("13000000.gpu")
        with self.assertRaises(SystemExit):
            dvfs_test.cmd_detect()


class TestCmdResource(DvfsTestCaseBase):
    def test_returns_none_with_no_devices(self):
        self.assertIsNone(dvfs_test.cmd_resource())

    def test_emits_one_record_per_device_governor_pair(self):
        self.make_device(
            "dev0", available_governors=("userspace", "performance")
        )
        with patch("sys.stdout", new_callable=StringIO) as out:
            dvfs_test.cmd_resource()
        text = out.getvalue()
        self.assertIn("dvfs_device_name: dev0", text)
        self.assertIn("governor: userspace", text)
        self.assertIn("governor: performance", text)


class TestCmdTest(DvfsTestCaseBase):
    """cmd_test exercises real read/write of sysfs-like files; write_node
    is monkeypatched only to emulate the kernel side-effect of governor
    switches on cur_freq (performance -> max, powersave -> min)."""

    def setUp(self):
        super().setUp()
        self._orig_write_node = dvfs_test._write_node
        self.addCleanup(self._restore_write_node)
        dvfs_test._write_node = self._fake_write_node

    def _restore_write_node(self):
        dvfs_test._write_node = self._orig_write_node

    def _fake_write_node(self, path, value):
        value = str(value)
        if path.name == "governor":
            self._orig_write_node(path, value)
            dev_dir = path.parent
            freqs = dvfs_test.get_available_frequencies(dev_dir.name)
            if value == "performance" and freqs:
                self._orig_write_node(dev_dir / "cur_freq", max(freqs))
            elif value == "powersave" and freqs:
                self._orig_write_node(dev_dir / "cur_freq", min(freqs))
            return True
        return self._orig_write_node(path, value)

    def test_unknown_device_fails(self):
        with self.assertRaises(SystemExit):
            dvfs_test.cmd_test("nope", "performance")

    def test_unknown_governor_fails(self):
        self.make_device("dev0")
        with self.assertRaises(SystemExit):
            dvfs_test.cmd_test("dev0", "bogus")

    def test_performance_locks_to_max_frequency(self):
        self.make_device("dev0", available_frequencies=(100, 200, 300))
        dvfs_test.cmd_test("dev0", "performance")

    def test_powersave_locks_to_min_frequency(self):
        self.make_device("dev0", available_frequencies=(100, 200, 300))
        dvfs_test.cmd_test("dev0", "powersave")

    def test_userspace_sweeps_every_frequency(self):
        self.make_device("dev0", available_frequencies=(100, 200, 300))
        dvfs_test.cmd_test("dev0", "userspace")

    def test_other_governor_only_checks_switch(self):
        self.make_device("dev0")
        dvfs_test.cmd_test("dev0", "simple_ondemand")

    def test_restores_original_state_after_test(self):
        dev_dir = self.make_device("dev0", governor="userspace", cur_freq=200)
        dvfs_test.cmd_test("dev0", "performance")
        self.assertEqual(
            dvfs_test._read_node(dev_dir / "governor"), "userspace"
        )
        self.assertEqual(dvfs_test._read_node(dev_dir / "cur_freq"), "200")

    def test_fails_when_governor_write_rejected(self):
        self.make_device("dev0")
        with patch.object(dvfs_test, "_write_node", return_value=False):
            with self.assertRaises(SystemExit):
                dvfs_test.cmd_test("dev0", "performance")


if __name__ == "__main__":
    unittest.main()
