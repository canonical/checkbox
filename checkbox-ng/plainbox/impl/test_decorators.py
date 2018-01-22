# This file is part of Checkbox.
#
# Copyright 2012-2014 Canonical Ltd.
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
plainbox.impl.test_decorators
=============================

Test definitions for plainbox.impl.decorators module
"""
import sys
import unittest

from plainbox.impl.decorators import raises
from plainbox.impl.decorators import UndocumentedException


class RaisesTests(unittest.TestCase):

    def test_adds_annotation_to_functions(self):
        @raises(ValueError, IOError)
        def func():
            pass
        self.assertEqual(
            func.__annotations__['raise'], (ValueError, IOError))

    def test_adds_annotation_to_methods(self):
        class C:
            @raises(ValueError, IOError)
            def meth(self):
                pass
        self.assertEqual(
            C.meth.__annotations__['raise'], (ValueError, IOError))

    @unittest.skipIf(
        sys.version_info[0:2] < (3, 4), "assertLogs not supported")
    def test_logs_and_forwards_unknown_exceptions(self):
        @raises(ValueError)
        def func():
            raise KeyError
        with self.assertLogs('plainbox.bug', level='ERROR') as cm:
            with self.assertRaises(KeyError):
                func()
        self.assertEqual(cm.output, [(
            'ERROR:plainbox.bug:'
            'Undeclared exception KeyError raised from func')])

    def test_forwards_known_exceptions(self):
        @raises(ValueError)
        def func():
            raise ValueError
        with self.assertRaises(ValueError):
            func()

    def test_enforces_documentation(self):
        with self.assertRaises(UndocumentedException):
            @raises(ValueError)
            def func():
                """
                This function never fails
                """
                raise ValueError

    def test_doesnt_enforce_documentation_for_undocumented_things(self):
        @raises(ValueError)
        def func():
            raise ValueError
