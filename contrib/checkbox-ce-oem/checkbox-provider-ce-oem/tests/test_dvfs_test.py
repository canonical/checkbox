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

import json
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
        parent=None,
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
        dev_dir = (parent if parent is not None else self.tmp_path) / name
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

    def write_config(self, config: dict) -> str:
        """Write a DVFS device-map JSON file and return its absolute path."""
        config_path = self.tmp_path / "dvfs_processors.json"
        config_path.write_text(json.dumps(config))
        return str(config_path)


class TestListDevfreqProcessors(DvfsTestCaseBase):
    def test_empty_root_returns_empty_list(self):
        self.assertEqual(dvfs_test.list_devfreq_processors(), [])

    def test_missing_root_returns_empty_list(self):
        dvfs_test.DEVFREQ_ROOT = self.tmp_path / "does-not-exist"
        self.assertEqual(dvfs_test.list_devfreq_processors(), [])

    def test_finds_devices_with_governor_node(self):
        self.make_device("13000000.gpu")
        self.make_device("soc:vpu_devfreq")
        # A directory without a "governor" node must be ignored.
        (self.tmp_path / "not-a-devfreq-dev").mkdir()
        self.assertEqual(
            dvfs_test.list_devfreq_processors(),
            ["13000000.gpu", "soc:vpu_devfreq"],
        )


class TestGovernorsAndFrequencies(DvfsTestCaseBase):
    def test_get_available_governors(self):
        dev_path = self.make_device(
            "dev0", available_governors=("userspace", "performance")
        )
        self.assertEqual(
            dvfs_test.get_available_governors(dev_path),
            ["userspace", "performance"],
        )

    def test_get_available_frequencies(self):
        dev_path = self.make_device(
            "dev0", available_frequencies=(300, 100, 200)
        )
        self.assertEqual(
            dvfs_test.get_available_frequencies(dev_path),
            [300, 100, 200],
        )

    def test_missing_device_returns_empty(self):
        dev_path = self.tmp_path / "nope"
        self.assertEqual(dvfs_test.get_available_governors(dev_path), [])
        self.assertEqual(dvfs_test.get_available_frequencies(dev_path), [])

    def test_unexpected_content_returns_empty(self):
        dev_path = self.make_device("dev0")
        (dev_path / "available_frequencies").write_text("not-a-number")
        self.assertEqual(dvfs_test.get_available_frequencies(dev_path), [])


class TestResolveDvfsProcessors(DvfsTestCaseBase):
    @patch.object(dvfs_test, "DVFS_PROCESSORS_FILE_PATH", "")
    def test_falls_back_to_default_root_scan(self):
        self.make_device("13000000.gpu")
        self.make_device("soc:vpu_devfreq")
        result = dvfs_test.resolve_dvfs_processors()
        expected_governors = [
            "simple_ondemand",
            "userspace",
            "powersave",
            "performance",
        ]
        self.assertEqual(
            result,
            {
                "13000000.gpu": {
                    "path": self.tmp_path / "13000000.gpu",
                    "type": "other",
                    "governors": expected_governors,
                },
                "soc:vpu_devfreq": {
                    "path": self.tmp_path / "soc:vpu_devfreq",
                    "type": "other",
                    "governors": expected_governors,
                },
            },
        )

    def test_uses_config_file_allowlist(self):
        config = {
            "allowlist": [
                {
                    "device_name": "13000000.gpu",
                    "type": "gpu",
                    "governors": ["userspace", "performance"],
                },
                {
                    "device_name": "soc:mdla_devfreq",
                    "governors": ["simple_ondemand"],
                },
            ],
            "denylist": [],
        }
        config_path = self.write_config(config)
        with patch.object(dvfs_test, "DVFS_PROCESSORS_FILE_PATH", config_path):
            result = dvfs_test.resolve_dvfs_processors()
        self.assertEqual(
            result["13000000.gpu"],
            {
                "path": self.tmp_path / "13000000.gpu",
                "type": "gpu",
                "governors": ["userspace", "performance"],
            },
        )
        # "type" omitted -> defaults to "other".
        self.assertEqual(result["soc:mdla_devfreq"]["type"], "other")

    def test_uses_sysfs_path_override(self):
        alt_root = self.tmp_path / "alt-root"
        dev_path = self.make_device("13000000.gpu", parent=alt_root)
        config = {
            "allowlist": [
                {
                    "device_name": "13000000.gpu",
                    "type": "gpu",
                    "sysfs_path": str(dev_path),
                    "governors": ["userspace"],
                }
            ],
            "denylist": [],
        }
        config_path = self.write_config(config)
        with patch.object(dvfs_test, "DVFS_PROCESSORS_FILE_PATH", config_path):
            result = dvfs_test.resolve_dvfs_processors()
        self.assertEqual(result["13000000.gpu"]["path"], dev_path)

    def test_denylist_excludes_device(self):
        config = {
            "allowlist": [
                {
                    "device_name": "13000000.gpu",
                    "type": "gpu",
                    "governors": ["userspace"],
                },
                {
                    "device_name": "soc:vpu_devfreq",
                    "type": "vpu",
                    "governors": ["userspace"],
                },
            ],
            "denylist": ["soc:vpu_devfreq"],
        }
        config_path = self.write_config(config)
        with patch.object(dvfs_test, "DVFS_PROCESSORS_FILE_PATH", config_path):
            result = dvfs_test.resolve_dvfs_processors()
        self.assertEqual(set(result.keys()), {"13000000.gpu"})


class TestDoCheck(DvfsTestCaseBase):
    @patch.object(dvfs_test, "DVFS_PROCESSORS_FILE_PATH", "")
    def test_fails_when_no_devices_and_no_config(self):
        with self.assertRaises(SystemExit):
            dvfs_test.do_check()

    @patch.object(dvfs_test, "DVFS_PROCESSORS_FILE_PATH", "")
    def test_passes_when_devices_present_and_no_config(self):
        self.make_device("13000000.gpu")
        dvfs_test.do_check()

    def test_passes_when_expected_matches(self):
        self.make_device(
            "13000000.gpu",
            available_governors=(
                "simple_ondemand",
                "userspace",
                "powersave",
                "performance",
            ),
        )
        config = {
            "allowlist": [
                {
                    "device_name": "13000000.gpu",
                    "type": "gpu",
                    "governors": [
                        "simple_ondemand",
                        "userspace",
                        "powersave",
                        "performance",
                    ],
                }
            ],
            "denylist": [],
        }
        config_path = self.write_config(config)
        with patch.object(dvfs_test, "DVFS_PROCESSORS_FILE_PATH", config_path):
            dvfs_test.do_check()

    def test_fails_when_expected_governors_mismatch(self):
        self.make_device(
            "13000000.gpu", available_governors=("userspace", "powersave")
        )
        config = {
            "allowlist": [
                {
                    "device_name": "13000000.gpu",
                    "type": "gpu",
                    "governors": ["userspace"],
                }
            ],
            "denylist": [],
        }
        config_path = self.write_config(config)
        with patch.object(dvfs_test, "DVFS_PROCESSORS_FILE_PATH", config_path):
            with self.assertRaises(SystemExit):
                dvfs_test.do_check()

    def test_fails_when_expected_device_missing(self):
        self.make_device("13000000.gpu")
        config = {
            "allowlist": [
                {
                    "device_name": "missing-device",
                    "type": "gpu",
                    "governors": ["userspace"],
                }
            ],
            "denylist": [],
        }
        config_path = self.write_config(config)
        with patch.object(dvfs_test, "DVFS_PROCESSORS_FILE_PATH", config_path):
            with self.assertRaises(SystemExit):
                dvfs_test.do_check()

    def test_passes_when_using_sysfs_path_override(self):
        alt_root = self.tmp_path / "alt-root"
        dev_path = self.make_device(
            "13000000.gpu", parent=alt_root, available_governors=("userspace",)
        )
        config = {
            "allowlist": [
                {
                    "device_name": "13000000.gpu",
                    "type": "gpu",
                    "sysfs_path": str(dev_path),
                    "governors": ["userspace"],
                }
            ],
            "denylist": [],
        }
        config_path = self.write_config(config)
        with patch.object(dvfs_test, "DVFS_PROCESSORS_FILE_PATH", config_path):
            dvfs_test.do_check()


class TestCmdResource(DvfsTestCaseBase):
    @patch.object(dvfs_test, "DVFS_PROCESSORS_FILE_PATH", "")
    def test_returns_none_with_no_devices(self):
        self.assertIsNone(dvfs_test.cmd_resource())

    @patch.object(dvfs_test, "DVFS_PROCESSORS_FILE_PATH", "")
    def test_emits_one_record_per_device_governor_pair(self):
        self.make_device(
            "dev0", available_governors=("userspace", "performance")
        )
        with patch("sys.stdout", new_callable=StringIO) as out:
            dvfs_test.cmd_resource()
        text = out.getvalue()
        self.assertIn("dvfs_processor_name: dev0", text)
        self.assertIn("dvfs_processor_type: other", text)
        self.assertIn("governor: userspace", text)
        self.assertIn("governor: performance", text)

    def test_uses_config_file_to_scope_devices(self):
        self.make_device(
            "gpu0", available_governors=("userspace", "performance")
        )
        self.make_device(
            "vpu0", available_governors=("userspace", "performance")
        )
        config = {
            "allowlist": [
                {
                    "device_name": "gpu0",
                    "type": "gpu",
                    "governors": ["userspace", "performance"],
                }
            ],
            "denylist": [],
        }
        config_path = self.write_config(config)
        with patch.object(
            dvfs_test, "DVFS_PROCESSORS_FILE_PATH", config_path
        ), patch("sys.stdout", new_callable=StringIO) as out:
            dvfs_test.cmd_resource()
        text = out.getvalue()
        self.assertIn("dvfs_processor_name: gpu0", text)
        self.assertIn("dvfs_processor_type: gpu", text)
        self.assertNotIn("dvfs_processor_name: vpu0", text)


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
            freqs = dvfs_test.get_available_frequencies(dev_dir)
            if value == "performance" and freqs:
                self._orig_write_node(dev_dir / "cur_freq", max(freqs))
            elif value == "powersave" and freqs:
                self._orig_write_node(dev_dir / "cur_freq", min(freqs))
            return True
        return self._orig_write_node(path, value)

    def test_unknown_device_fails(self):
        with self.assertRaises(SystemExit):
            dvfs_test.cmd_test("nope", "gpu", "", "performance")

    def test_unknown_governor_fails(self):
        self.make_device("dev0")
        with self.assertRaises(SystemExit):
            dvfs_test.cmd_test("dev0", "gpu", "", "bogus")

    def test_performance_locks_to_max_frequency(self):
        self.make_device("dev0", available_frequencies=(100, 200, 300))
        dvfs_test.cmd_test("dev0", "gpu", "", "performance")

    def test_powersave_locks_to_min_frequency(self):
        self.make_device("dev0", available_frequencies=(100, 200, 300))
        dvfs_test.cmd_test("dev0", "gpu", "", "powersave")

    def test_userspace_sweeps_every_frequency(self):
        self.make_device("dev0", available_frequencies=(100, 200, 300))
        dvfs_test.cmd_test("dev0", "gpu", "", "userspace")

    def test_simple_ondemand_only_checks_switch(self):
        self.make_device("dev0")
        dvfs_test.cmd_test("dev0", "gpu", "", "simple_ondemand")

    def test_unimplemented_governor_fails_even_if_switch_succeeds(self):
        # "conservative" is a real, switchable governor here (present
        # in available_governors and the write/poll succeeds), but
        # since it has no dedicated verification branch it must still
        # be reported as a failure instead of a silent pass.
        self.make_device(
            "dev0",
            available_governors=(
                "simple_ondemand",
                "userspace",
                "powersave",
                "performance",
                "conservative",
            ),
        )
        with self.assertRaises(SystemExit):
            dvfs_test.cmd_test("dev0", "gpu", "", "conservative")

    def test_restores_original_state_after_test(self):
        dev_dir = self.make_device("dev0", governor="userspace", cur_freq=200)
        dvfs_test.cmd_test("dev0", "gpu", "", "performance")
        self.assertEqual(
            dvfs_test._read_node(dev_dir / "governor"), "userspace"
        )
        self.assertEqual(dvfs_test._read_node(dev_dir / "cur_freq"), "200")

    def test_fails_when_governor_write_rejected(self):
        self.make_device("dev0")
        with patch.object(dvfs_test, "_write_node", return_value=False):
            with self.assertRaises(SystemExit):
                dvfs_test.cmd_test("dev0", "gpu", "", "performance")

    def test_uses_explicit_sysfs_path(self):
        alt_root = self.tmp_path / "alt-root"
        dev_dir = self.make_device(
            "dev0",
            parent=alt_root,
            available_frequencies=(100, 200, 300),
        )
        dvfs_test.cmd_test("dev0", "gpu", str(dev_dir), "performance")
        self.assertEqual(
            dvfs_test._read_node(dev_dir / "governor"),
            "simple_ondemand",
        )


if __name__ == "__main__":
    unittest.main()
