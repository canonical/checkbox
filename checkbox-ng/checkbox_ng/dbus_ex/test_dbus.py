# This file is part of Checkbox.
#
# Copyright 2012, 2013 Canonical Ltd.
# Written by:
#
#   Daniel Manrique <roadmr@ubuntu.com>
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
checkbox_ng.dbus_ex.test_dbus
=============================

Test definitions for checkbox_ng.dbus_ex module
"""
import re

from plainbox.testing_utils.testcases import TestCaseWithParameters

from checkbox_ng.dbus_ex import mangle_object_path


class TestManglePath(TestCaseWithParameters):
    parameter_names = ('dbus_path',)
    parameter_values = (
        ('/plainbox/whitelist/some-bogus.whitelist', ),
        ('/plainbox/provider/2013.com.example:test-provider', ))

    def setUp(self):
        # Note this regex fails to capture the root ("/") dbus path, not
        # a problem in this use case though.
        self.dbus_regex = re.compile(r'^/([a-zA-Z0-9_]+/)+([a-zA-Z0-9_]+)$')

    def test_mangle_path(self):
        mangled_path = mangle_object_path(self.parameters.dbus_path)
        self.assertTrue(self.dbus_regex.match(mangled_path), mangled_path)
