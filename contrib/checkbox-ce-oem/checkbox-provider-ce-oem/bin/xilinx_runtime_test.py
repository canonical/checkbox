#!/usr/bin/env python3
"""
This file is part of Checkbox.

Copyright 2022 Canonical Ltd.
Written by:
  Talha Can Havadar <talha.can.havadar@canonical.com>

Checkbox is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License version 3,
as published by the Free Software Foundation.

Checkbox is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with Checkbox.  If not, see <http://www.gnu.org/licenses/>.
"""

import os
from xilinx_dfx_mgr_test import Package
import unittest
import subprocess
import shlex
import json
from typing import List
from time import sleep


class TestXilinxRuntimePackage(unittest.TestCase):
    packages_before_test = []

    @classmethod
    def setUpClass(cls):
        # first read all packages to save current status before
        cls.packages_before_test = cls._get_packages(cls)

    @classmethod
    def tearDownClass(cls):
        subprocess.run(shlex.split("dfx-mgr-client -remove"), check=False)
        for package in cls.packages_before_test:
            if not ("-1" in package.active_slot):
                subprocess.run(
                    shlex.split(f"dfx-mgr-client -load {package.accelerator}"),
                    check=False,
                    stdout=subprocess.DEVNULL,
                )

    def _get_packages(self) -> List[Package]:
        packages = []

        result = subprocess.run(
            shlex.split("dfx-mgr-client -listPackage"),
            check=True,
            capture_output=True,
        )
        filtered_lines = list(
            filter(
                lambda line: line.strip() != "",
                result.stdout.decode("utf-8").splitlines(),
            )
        )

        for line in filtered_lines[1:]:
            packages.append(Package(*line.replace(",", "").split()))

        return packages

    def _remove_dfx_package(self, slot="0"):
        packages = self._get_packages()
        is_slot_active = False
        for package in packages:
            if str(package.active_slot) == str(slot):
                is_slot_active = True
                break
        if is_slot_active:
            subprocess.run(
                shlex.split(f"dfx-mgr-client -remove {slot}"), check=True
            )
            sleep(1)  # give time to settle

    def test_help_option(self):
        result = subprocess.run(
            shlex.split("xbutil --help"), check=True, capture_output=True
        )
        self.assertIn(
            "DESCRIPTION",
            str(result.stdout),
            "Output of the `--help` must contain 'DESCRIPTION' field.",
        )
        self.assertIn(
            "USAGE",
            str(result.stdout),
            "Output of the `--help` must contain 'USAGE' field.",
        )

    def test_version_option(self):
        result = subprocess.run(
            shlex.split("xbutil --version"), check=True, capture_output=True
        )
        self.assertIn(
            "Version",
            str(result.stdout),
            "Output of the `--version` must contain 'Version' field.",
        )

    def test_examine_command(self):
        result = subprocess.run(
            shlex.split("xbutil examine"), check=True, capture_output=True
        )
        self.assertIn(
            "Devices present",
            str(result.stdout),
            "Output of the `examine` must contain 'Devices present' field.",
        )
        self.assertIn(
            "Distribution",
            str(result.stdout),
            "Output of the `examine` must contain 'Distribution' field.",
        )

    def test_examine_help(self):
        result = subprocess.run(
            shlex.split("xbutil examine --help"),
            check=True,
            capture_output=True,
        )
        self.assertIn(
            "DESCRIPTION",
            str(result.stdout),
            "Output of the `-examine -help` must contain 'DESCRIPTION' field.",
        )
        self.assertIn(
            "USAGE",
            str(result.stdout),
            "Output of the `examine --help` must contain 'USAGE' field.",
        )
        self.assertIn(
            "xbutil examine",
            str(result.stdout),
            "`examine --help` must contain 'xbutil examine' field.",
        )

    def test_examine_devices(self):
        self._remove_dfx_package()

        result = subprocess.run(
            shlex.split("dfx-mgr-client -load kv260-nlp-smartvision"),
            check=True,
            capture_output=True,
        )
        sleep(2)  # give some time to settle
        self.assertNotIn("error:", str(result.stdout).lower())

        examine_output_path = os.path.join(
            os.environ.get("PLAINBOX_SESSION_SHARE", "/tmp"),
            "examine_out.json",
        )
        subprocess.run(
            shlex.split(
                f"xbutil examine -f json -o {examine_output_path} --force"
            ),
            check=True,
        )
        with open(examine_output_path, "r") as f:
            json_data = json.load(f)
            self.assertTrue(len(json_data["system"]["host"]["devices"]) > 0)

    @unittest.skip(
        "dfx-mgr appears to program xclbin when application is loaded"
    )
    def test_program_command(self):
        self._remove_dfx_package()

        result = subprocess.run(
            shlex.split("dfx-mgr-client -load kv260-nlp-smartvision"),
            check=True,
        )
        sleep(2)  # give some time to settle
        self.assertNotIn("error:", str(result.stdout).lower())

        examine_output_path = os.path.join(
            os.environ.get("PLAINBOX_SESSION_SHARE", "/tmp"),
            "examine_out.json",
        )
        subprocess.run(
            shlex.split(
                f"xbutil examine -f json -o {examine_output_path} --force"
            )
        ).check_returncode()
        with open(examine_output_path, "r") as f:
            bdf = json.load(f)["system"]["host"]["devices"][0]["bdf"]
            xclbin_path = (
                "/lib/firmware/xilinx/kv260-nlp-smartvision/"
                "kv260-nlp-smartvision.xclbin"
            )
            subprocess.run(
                shlex.split(f"xbutil program -d {bdf} -u {xclbin_path}"),
                check=True,
            )

    def test_configure_command(self):
        subprocess.run(
            shlex.split("xbutil configure --p2p VALIDATE"), check=True
        )
        # --host-mem functionality is not implemented yet


if __name__ == "__main__":
    unittest.main()
