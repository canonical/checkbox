# This file is part of Checkbox.
#
# Copyright 2012, 2013 Canonical Ltd.
# Written by:
#   Zygmunt Krynicki <zygmunt.krynicki@canonical.com>
#
# Checkbox is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Checkbox is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Checkbox.  If not, see <http://www.gnu.org/licenses/>.

"""
plainbox.impl.test_session
==========================

Test definitions for plainbox.impl.session module
"""

import json
import os
import tempfile
import shutil

from unittest import TestCase

from plainbox.abc import IJobResult
from plainbox.impl.result import MemoryJobResult
from plainbox.impl.session.legacy import SessionStateLegacyAPICompatImpl
from plainbox.impl.testing_utils import make_job


class SessionStateSmokeTests(TestCase):

    def setUp(self):
        A = make_job('A', requires='R.attr == "value"')
        B = make_job('B', depends='C')
        C = make_job('C')
        self.job_list = [A, B, C]
        self.session_state = SessionStateLegacyAPICompatImpl(self.job_list)

    def test_initial_job_list(self):
        expected = self.job_list
        observed = self.session_state.job_list
        self.assertEqual(expected, observed)

    def test_initial_desired_job_list(self):
        expected = []
        observed = self.session_state.desired_job_list
        self.assertEqual(expected, observed)

    def test_initial_run_list(self):
        expected = []
        observed = self.session_state.run_list
        self.assertEqual(expected, observed)

    def test_initial_session_dir(self):
        self.assertIsNone(self.session_state.session_dir)


class SessionStateLocalStorageTests(TestCase):

    def setUp(self):
        # session data are kept in XDG_CACHE_HOME/plainbox/.session
        # To avoid resuming a real session, we have to select a temporary
        # location instead
        self._sandbox = tempfile.mkdtemp()
        self._env = os.environ
        os.environ['XDG_CACHE_HOME'] = self._sandbox

    def job_state(self, name):
        # A helper function to avoid overly long expressions
        return self.session.job_state_map[name]

    def test_persistent_save(self):
        self.job_A = make_job("A")
        self.job_list = [self.job_A]
        self.session = SessionStateLegacyAPIOriginalImpl(self.job_list)
        result_A = MemoryJobResult({
            'outcome': IJobResult.OUTCOME_PASS,
            'comments': 'All good',
            'return_code': 0,
            'io_log': ((0, 'stdout', "Success !\n"),)
        })
        session_json_text = """{
            "_job_state_map": {
                "A": {
                    "_job": {
                        "data": {
                            "name": "A",
                            "plugin": "dummy"
                        },
                        "_class_id": "JOB_DEFINITION"
                    },
                    "_result": {
                        "data": {
                            "outcome": "pass",
                            "return_code": 0,
                            "comments": "All good",
                            "io_log": [
                                [
                                    0,
                                    "stdout",
                                    "Success !\\n"
                                ]
                            ]
                        },
                        "_class_id": "JOB_RESULT(m)"
                    },
                    "_class_id": "JOB_STATE"
                }
            },
            "_desired_job_list": [
                {
                    "data": {
                        "name": "A",
                        "plugin": "dummy"
                    },
                    "_class_id": "JOB_DEFINITION"
                }
            ],
            "_class_id": "SESSION_STATE"
        }"""
        self.session.open()
        self.session.update_desired_job_list([self.job_A])
        self.session.update_job_result(self.job_A, result_A)
        self.session.persistent_save()
        session_file = self.session.previous_session_file()
        self.session.close()
        self.assertIsNotNone(session_file)
        with open(session_file) as f:
            raw_json = json.load(f)
            self.maxDiff = None
            self.assertEqual(raw_json, json.loads(session_json_text))

    def test_resume_session(self):
        # All of the tests below are using one session. The session has four
        # jobs, Job A depends on a resource provided by job R which has no
        # dependencies at all. Both Job X and Y depend on job A.
        #
        # A -(resource dependency)-> R
        #
        # X -(direct dependency) -> A
        #
        # Y -(direct dependency) -> A
        self.job_A = make_job("A", requires="R.attr == 'value'")
        self.job_A_expr = self.job_A.get_resource_program().expression_list[0]
        self.job_R = make_job("R", plugin="resource")
        self.job_X = make_job("X", depends='A')
        self.job_Y = make_job("Y", depends='A')
        self.job_list = [self.job_A, self.job_R, self.job_X, self.job_Y]
        # Create a new session (session_dir is empty)
        self.session = SessionStateLegacyAPIOriginalImpl(self.job_list)
        result_R = MemoryJobResult({
            'io_log': [(0, 'stdout', b"attr: value\n")]})
        result_A = MemoryJobResult({'outcome': IJobResult.OUTCOME_PASS})
        result_X = MemoryJobResult({'outcome': IJobResult.OUTCOME_PASS})
        # Job Y can't start as it requires job A
        self.assertFalse(self.job_state('Y').can_start())
        self.session.update_desired_job_list([self.job_X, self.job_Y])
        self.session.open()
        self.session.update_job_result(self.job_R, result_R)
        self.session.update_job_result(self.job_A, result_A)
        self.session.update_job_result(self.job_X, result_X)
        self.session.persistent_save()
        self.session.close()
        # Create a new session (session_dir should contain session data)
        self.session = SessionStateLegacyAPIOriginalImpl(self.job_list)
        self.session.open()
        # Resume the previous session
        self.session.resume()
        # This time job Y can start
        self.assertTrue(self.job_state('Y').can_start())
        self.session.close()

    def tearDown(self):
        shutil.rmtree(self._sandbox)
        os.environ = self._env
