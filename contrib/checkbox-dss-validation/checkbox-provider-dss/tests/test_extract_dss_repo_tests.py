#!/usr/bin/env python3
#
# This file is part of Checkbox.
#
# Copyright 2025 Canonical Ltd.
#
# Authors:
#     Abdullah (@motjuste) <abdullah.abdullah@canonical.com>
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
#
"""Tests for `extract_dss_repo_tests.py`"""

from contextlib import redirect_stdout
from io import StringIO
import os
from subprocess import CalledProcessError, STDOUT
import tempfile
import unittest
from unittest import mock

import extract_dss_repo_tests


class TestMain(unittest.TestCase):
    dss_repo = "some/repo"
    tox_env = "integration"
    tox_path = extract_dss_repo_tests.TOX_PATH_IN_REPO

    def test_fails_when_dss_repo_is_missing(self):
        dss_repo = "/something/missing"
        args = [dss_repo, self.tox_env]
        with self.assertRaises(FileNotFoundError) as caught:
            extract_dss_repo_tests.main(args)
        self.assertIn(
            f"No such file or directory: '{dss_repo}'", str(caught.exception)
        )

    def test_fails_when_dss_repo_has_no_venv(self):
        with tempfile.TemporaryDirectory() as dss_repo:
            args = [dss_repo, self.tox_env]
            with self.assertRaises(FileNotFoundError) as caught:
                extract_dss_repo_tests.main(args)
            self.assertIn(
                f"No such file or directory: '{self.tox_path}'",
                str(caught.exception),
            )

    def test_fails_when_tox_is_not_installed(self):
        with tempfile.TemporaryDirectory() as dss_repo:
            os.makedirs(dss_repo + os.path.dirname(self.tox_path))
            args = [dss_repo, self.tox_env]
            with self.assertRaises(FileNotFoundError) as caught:
                extract_dss_repo_tests.main(args)
            self.assertIn(
                f"No such file or directory: '{self.tox_path}'",
                str(caught.exception),
            )

    @mock.patch("subprocess.check_output")
    def test_fails_when_tox_command_fails(self, mock_run):
        args = [self.dss_repo, self.tox_env]

        expected_exception = CalledProcessError(["testing"], "fake failure")
        mock_run.side_effect = expected_exception

        with self.subTest("must raise exception"):
            with self.assertRaises(CalledProcessError) as caught:
                extract_dss_repo_tests.main(args)
            self.assertEquals(caught.exception, expected_exception)

        with self.subTest("verify call args"):
            mock_run.assert_called_once_with(
                [
                    self.tox_path,
                    "-e",
                    self.tox_env,
                    "--",
                    "--collect-only",
                    "-qq",
                ],
                cwd=self.dss_repo,
                text=True,
                stderr=STDOUT,
            )

    @mock.patch("subprocess.check_output")
    def test_prints_test_cases_and_names_normally(self, mock_run):
        args = [self.dss_repo, self.tox_env]

        mock_run.return_value = SAMPLE_OUTPUT_WITH_MATCHES

        buffer = StringIO()
        with redirect_stdout(buffer):
            extract_dss_repo_tests.main(args)

        with self.subTest("verify tox call"):
            mock_run.assert_called_once_with(
                [
                    self.tox_path,
                    "-e",
                    self.tox_env,
                    "--",
                    "--collect-only",
                    "-qq",
                ],
                cwd=self.dss_repo,
                text=True,
                stderr=STDOUT,
            )

        with self.subTest("verify parsed test cases and names"):
            self.assertEquals(buffer.getvalue(), SAMPLE_MATCHED_TESTS)

    @mock.patch("subprocess.check_output")
    def test_prints_test_cases_and_names_for_resource(self, mock_run):
        args = [self.dss_repo, self.tox_env]

        mock_run.return_value = SAMPLE_OUTPUT_WITH_MATCHES

        buffer = StringIO()
        with redirect_stdout(buffer):
            extract_dss_repo_tests.main(args)
        lines = buffer.getvalue().splitlines()

        with self.subTest("every third line is a newline"):
            for i, line in list(enumerate(lines))[2::3]:
                with self.subTest(f"line: {i}"):
                    self.assertEquals(line, "")

        with self.subTest("every first line is for test_case"):
            for i, line in list(enumerate(lines))[0::3]:
                with self.subTest(f"line: {i}"):
                    self.assertTrue(line.startswith("test_case: "))

        with self.subTest("every second line is for test_name"):
            for i, line in list(enumerate(lines))[1::3]:
                with self.subTest(f"line: {i}"):
                    self.assertTrue(line.startswith("test_name: "))

    @mock.patch("subprocess.check_output")
    def test_fails_on_missing_matches(self, mock_run):
        args = [self.dss_repo, self.tox_env]

        for case, sample_output in (
            ("empty output", ""),
            ("empty lines", "\n\n\n"),
            ("completely irrelevant", "completely irrelevant"),
            ("no tests", SAMPLE_OUTPUT_WITHOUT_ANY_TESTS),
            ("no matches", SAMPLE_OUTPUT_WITHOUT_MATCHES),
        ):
            with self.subTest(case):
                mock_run.return_value = sample_output
                with self.assertRaises(ValueError) as caught:
                    extract_dss_repo_tests.main(args)
                self.assertIn(sample_output, str(caught.exception))
            mock_run.reset_mock()


SAMPLE_OUTPUT_PREAMBLE = """\
integration: install_deps> python -I -m pip install -r requirements-test.txt
integration: commands[0]> pip install .
Processing /tmp/dss-repo
  Installing build dependencies: started
  Installing build dependencies: finished with status 'done'
  Getting requirements to build wheel: started
  Getting requirements to build wheel: finished with status 'done'
  Preparing metadata (pyproject.toml): started
  Preparing metadata (pyproject.toml): finished with status 'done'
Requirement already satisfied: charmed-kubeflow-chisme in ./.tox/integration/lib/python3.10/site-packages (from dss==0.1) (0.2.1)
Requirement already satisfied: urllib3<3,>=1.21.1 in ./.tox/integration/lib/python3.10/site-packages (from requests->serialized-data-interface->charmed-kubeflow-chisme->dss==0.1) (2.2.0)
Building wheels for collected packages: dss
  Building wheel for dss (pyproject.toml): started
  Building wheel for dss (pyproject.toml): finished with status 'done'
  Created wheel for dss: filename=dss-0.1-py3-none-any.whl size=25116 sha256=d8f42dc99c665f86b66d7e2db78b0d419a1a306096bc90fed49a66bba75f392a
  Stored in directory: /home/ubuntu/.cache/pip/wheels/11/cf/57/f3f17499dfd7495c080da28a529073492963c29e8882e05e0c
Successfully built dss
Installing collected packages: dss
Successfully installed dss-0.1
"""

SAMPLE_OUTPUT_PART_WITH_MATCHES = """\
integration: commands[1]> pytest /tmp/dss-repo/tests//integration/ -m cpu -v --tb native -s --notebook-image=kubeflownotebookswg/jupyter-scipy:v1.8.0 --collect-only -qq
tests/integration/test_dss.py::test_status_before_initialize[cpu]
tests/integration/test_dss.py::test_initialize_creates_dss
tests/integration/test_dss.py::test_create_notebook
tests/integration/test_dss.py::test_list_after_create
tests/integration/test_dss.py::test_status_after_initialize[cpu]
tests/integration/test_dss.py::test_log_command
tests/integration/test_dss.py::test_stop_notebook
tests/integration/test_dss.py::test_start_notebook
tests/integration/test_dss.py::test_remove_notebook
tests/integration/test_dss.py::test_purge
"""

SAMPLE_MATCHED_TESTS = """\
test_case: tests/integration/test_dss.py
test_name: test_status_before_initialize[cpu]

test_case: tests/integration/test_dss.py
test_name: test_initialize_creates_dss

test_case: tests/integration/test_dss.py
test_name: test_create_notebook

test_case: tests/integration/test_dss.py
test_name: test_list_after_create

test_case: tests/integration/test_dss.py
test_name: test_status_after_initialize[cpu]

test_case: tests/integration/test_dss.py
test_name: test_log_command

test_case: tests/integration/test_dss.py
test_name: test_stop_notebook

test_case: tests/integration/test_dss.py
test_name: test_start_notebook

test_case: tests/integration/test_dss.py
test_name: test_remove_notebook

test_case: tests/integration/test_dss.py
test_name: test_purge

"""

SAMPLE_OUTPUT_PART_WITHOUT_MATCHES = """\
integration: commands[1]> pytest /tmp/dss-repo/tests//integration/ -m cpu -v --tb native -s --notebook-image=kubeflownotebookswg/jupyter-scipy:v1.8.0 --collect-only -qq
tests/other-integration/test_dss.py::test_status_before_initialize[cpu]
tests/other-integration/test_dss.py::test_initialize_creates_dss
tests/other-integration/test_dss.py::test_create_notebook
tests/other-integration/test_dss.py::test_list_after_create
tests/other-integration/test_dss.py::test_status_after_initialize[cpu]
tests/other-integration/test_dss.py::test_log_command
tests/other-integration/test_dss.py::test_stop_notebook
tests/other-integration/test_dss.py::test_start_notebook
tests/other-integration/test_dss.py::test_remove_notebook
tests/other-integration/test_dss.py::test_purge
"""

SAMPLE_OUTPUT_PART_WITHOUT_ANY_TESTS = """\
integration: commands[1]> pytest /tmp/dss-repo/tests//integration/ -m cpu -v --tb native -s --notebook-image=kubeflownotebookswg/jupyter-scipy:v1.8.0 --collect-only -qq
"""

SAMPLE_OUTPUT_END_PART = """\
10/13 tests collected (3 deselected) in 0.24s
  integration: OK (9.52=setup[6.38]+cmd[2.59,0.55] seconds)
  congratulations :) (9.54 seconds)
"""

SAMPLE_OUTPUT_WITH_MATCHES = (
    SAMPLE_OUTPUT_PREAMBLE
    + SAMPLE_OUTPUT_PART_WITH_MATCHES
    + SAMPLE_OUTPUT_END_PART
)

SAMPLE_OUTPUT_WITHOUT_MATCHES = (
    SAMPLE_OUTPUT_PREAMBLE
    + SAMPLE_OUTPUT_PART_WITHOUT_MATCHES
    + SAMPLE_OUTPUT_END_PART
)

SAMPLE_OUTPUT_WITHOUT_ANY_TESTS = (
    SAMPLE_OUTPUT_PREAMBLE
    + SAMPLE_OUTPUT_PART_WITHOUT_ANY_TESTS
    + SAMPLE_OUTPUT_END_PART
)
