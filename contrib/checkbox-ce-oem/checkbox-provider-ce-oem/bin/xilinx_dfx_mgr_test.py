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

import xilinx_vut_handler as vut_handler
from xilinx_vut_handler import compare_versions
import unittest
import subprocess
from typing import NamedTuple, List

Package = NamedTuple(
    "Package",
    [
        ("accelerator", str),
        ("accel_type", str),
        ("base", str),
        ("base_type", str),
        ("slots", str),
        ("active_slot", str),
    ],
)


class TestDfxMgrPackage(unittest.TestCase):
    packages_before_test = []

    @classmethod
    def setUpClass(cls):
        # first read all packages to save current status before
        cls.packages_before_test = cls._get_packages(cls)

    @classmethod
    def tearDownClass(cls):
        for package in cls.packages_before_test:
            if not ("-1" in package.active_slot):
                subprocess.run(
                    ["dfx-mgr-client", "-load", package.accelerator],
                    check=False,
                    stdout=subprocess.DEVNULL,
                )

    def _get_packages(self) -> List[Package]:
        packages = []

        result = subprocess.run(
            ["dfx-mgr-client", "-listPackage"], check=True, capture_output=True
        )
        filtered_lines = list(
            filter(
                lambda line: line.strip() != "",
                result.stdout.decode("utf-8").splitlines(),
            )
        )

        for line in filtered_lines[1:]:
            packages.append(Package(*line.split()))

        return packages

    def test_call_with_no_args(self):
        self.assertRaises(
            subprocess.CalledProcessError,
            lambda: subprocess.run(
                "dfx-mgr-client", check=True, stdout=subprocess.DEVNULL
            ),
        )

    def test_call_with_unknown_option(self):
        try:
            subprocess.run(
                ["dfx-mgr-client", "-tchavadar"],
                check=True,
                stdout=subprocess.DEVNULL,
            )
        except subprocess.CalledProcessError:
            self.fail("dfx-mgr-client -tchavadar should not throw an error")

    def test_listPackage_option(self):
        result = subprocess.run(
            ["dfx-mgr-client", "-listPackage"], check=True, capture_output=True
        )
        result.check_returncode()

        filtered_lines = list(
            filter(
                lambda line: line.strip() != "",
                result.stdout.decode("utf-8").splitlines(),
            )
        )
        self.assertGreater(len(filtered_lines), 1)

    def test_help_option(self):
        subprocess.run(["dfx-mgr-client", "-h"], check=True)
        result = subprocess.run(
            ["dfx-mgr-client", "--help"], check=True, capture_output=True
        )
        result.check_returncode()

        contains_usage = "usage" in result.stdout.decode("utf-8").lower()
        self.assertTrue(contains_usage)

    @unittest.skipIf(
        compare_versions(
            "gt", vut_handler.__vut__, "2022.1+20220908+acb025a-0ubuntu0xlnx3"
        ),
        reason="This version is not under test",
    )
    def test_load_option(self):
        example_package = self._get_packages()[0]
        subprocess.run(
            ["dfx-mgr-client", "-remove", "0"],
            check=False,
            stdout=subprocess.DEVNULL,
        )

        subprocess.run(
            ["dfx-mgr-client", "-load", example_package.accelerator],
            check=True,
        )

        # fetch the updated package information
        example_package = self._get_packages()[0]

        self.assertTrue("0" in example_package.active_slot)

    def test_remove_option(self):
        example_package = self._get_packages()[0]
        subprocess.run(
            ["dfx-mgr-client", "-load", example_package.accelerator],
            check=False,
            stdout=subprocess.DEVNULL,
        )

        subprocess.run(["dfx-mgr-client", "-remove", "0"], check=True)

        # fetch the updated package information
        example_package = self._get_packages()[0]

        self.assertTrue("-1" in example_package.active_slot)

    def test_listUIO_option(self):
        subprocess.run(["dfx-mgr-client", "-listUIO", "0"], check=True)

    def test_allocBuffer_option(self):
        # no clear information about expected behaviour
        pass

    def test_freeBuffer_option(self):
        # no clear information about expected behaviour
        pass

    def test_getFDs_option(self):
        # no clear information about expected behaviour
        pass

    def test_getRMInfo_option(self):
        # no clear information about expected behaviour
        pass

    def test_getShellFD_option(self):
        # no clear information about expected behaviour
        pass

    def test_getClockFD_option(self):
        # no clear information about expected behaviour
        pass


if __name__ == "__main__":
    unittest.main()
