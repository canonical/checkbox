#!/usr/bin/env python3
# Copyright 2026 Canonical Ltd.
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

import os
import subprocess
import unittest

SCRIPT = os.path.join(
    os.path.dirname(__file__), "..", "bin", "resource_wrapper.sh"
)


def run_wrapper(*args):
    # capture_output needs Python 3.7, the provider still supports 3.6
    return subprocess.run(
        [SCRIPT, *args],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,
    )


class TestResourceWrapper(unittest.TestCase):
    def test_no_arguments_exits_silently(self):
        result = run_wrapper()
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout, "")
        self.assertEqual(result.stderr, "")

    def test_separator_alone_exits_silently(self):
        result = run_wrapper("--")
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout, "")
        self.assertEqual(result.stderr, "")

    def test_successful_command_stdout_is_printed(self):
        result = run_wrapper("--", "printf", "profile: foo\n")
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout, "profile: foo\n")
        self.assertEqual(result.stderr, "")

    def test_failing_command_is_silent(self):
        result = run_wrapper("--", "sh", "-c", "echo partial; exit 1")
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout, "")
        self.assertEqual(result.stderr, "")

    def test_failing_command_stderr_is_suppressed(self):
        result = run_wrapper("--", "sh", "-c", "echo failed >&2; exit 1")
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout, "")
        self.assertEqual(result.stderr, "")

    def test_empty_stdout_is_not_printed(self):
        result = run_wrapper("--", "true")
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout, "")
        self.assertEqual(result.stderr, "")


if __name__ == "__main__":
    unittest.main()
