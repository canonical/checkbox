# This file is part of Checkbox.
#
# Copyright 2013 Canonical Ltd.
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
plainbox.impl.test_applogic
===========================

Test definitions for plainbox.impl.applogic module
"""

from unittest import TestCase

from plainbox.impl.applogic import get_matching_job_list
from plainbox.impl.secure.qualifiers import RegExpJobQualifier
from plainbox.impl.testing_utils import make_job


class FunctionTests(TestCase):

    def test_get_matching_job_list(self):
        job_list = [make_job('foo'), make_job('froz'), make_job('barg')]
        self.assertEqual(
            get_matching_job_list(job_list, RegExpJobQualifier('f.*')),
            [make_job('foo'), make_job('froz')])
