# This file is part of Checkbox.
#
# Copyright 2012, 2013 Canonical Ltd.
# Written by:
#   Zygmunt Krynicki <zygmunt.krynicki@canonical.com>
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

"""
plainbox.impl.test_session
==========================

Test definitions for plainbox.impl.session module
"""

from unittest import TestCase

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

    def test_commit_open_doesnt_garble_session(self):
        self.session_state.open()
        self.session_state.manager
        self.assertIs(self.session_state, self.session_state.manager.state)

    def test_commit_clean_doesnt_garble_session(self):
        self.session_state.open()
        self.session_state.clean()
        self.session_state.manager
        self.assertIs(self.session_state, self.session_state.manager.state)
