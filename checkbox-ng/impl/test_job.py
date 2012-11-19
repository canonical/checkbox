# This file is part of Checkbox.
#
# Copyright 2012 Canonical Ltd.
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
plainbox.impl.test_job
======================

Test definitions for plainbox.impl.job module
"""

from unittest import TestCase

from plainbox.impl.job import JobDefinition


class TestJobDefinition(TestCase):

    _data = {
        'plugin': 'plugin',
        'name': 'name',
        'requires': 'requires',
        'command': 'command',
        'description': 'description'
    }

    def test_basics(self):
        obj = JobDefinition(self._data)
        self.assertEqual(obj.plugin, "plugin")
        self.assertEqual(obj.name, "name")
        self.assertEqual(obj.requires, "requires")
        self.assertEqual(obj.command, "command")
        self.assertEqual(obj.description, "description")
