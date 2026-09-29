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

import unittest
from time import sleep
import subprocess
import requests


class TestKriaDashboardPackage(unittest.TestCase):
    _before_test = {}

    @classmethod
    def setUpClass(cls):
        # save current status before test
        cls._before_test["service-status"] = (
            cls._systemctl_call(cls, "is-active") == 0
        )

    @classmethod
    def tearDownClass(cls):
        if cls._before_test["service-status"]:
            cls._systemctl_call(cls, "start")
        else:
            cls._systemctl_call(cls, "stop")

    def setUp(self) -> None:
        self._systemctl_call("stop")

    def _systemctl_call(self, command):
        return_code = subprocess.call(
            ["systemctl", command, "--quiet", "kria-dashboard"]
        )
        # Give kria-dashboard extra time to settle because it can fail
        # eventually after start.
        sleep(5)
        return return_code

    def test_kria_dashboard_runs(self):
        self._systemctl_call("start")
        status = self._systemctl_call("is-active") == 0

        self.assertTrue(status, "kria-dashboard should be activated.")

    def test_kria_dashboard_serves(self):
        self._systemctl_call("start")
        sleep(5)  # give some time to bokeh to be ready to serve
        requests.get(
            "http://localhost:5006/kria-dashboard", timeout=5
        ).raise_for_status()

    def test_kria_dashboard_service_restart(self):
        self._systemctl_call("start")
        self.assertTrue(self._systemctl_call("is-active") == 0)
        self._systemctl_call("restart")
        self.assertTrue(self._systemctl_call("is-active") == 0)

    def test_kria_dashboard_service_stop(self):
        self._systemctl_call("start")
        self._systemctl_call("stop")
        self.assertTrue(self._systemctl_call("is-active") != 0)


if __name__ == "__main__":
    unittest.main()
