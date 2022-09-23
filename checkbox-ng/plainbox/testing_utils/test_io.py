# This file is part of Checkbox.
#
# Copyright 2012 Canonical Ltd.
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
plainbox.testing_utils.test_io
==============================

Test definitions for plainbox.testing_utils.io module
"""
import sys
from unittest import TestCase

from plainbox.testing_utils.io import TestIO


class TestIOTest(TestCase):

    def test_stdin(self):
        with TestIO():
            self.assertRaises(EOFError, input)

    def test_stdin_text(self):
        with TestIO(input="text 1\ntext 2\n"):
            value1 = input()
            value2 = input()
        self.assertEqual(value1, "text 1")
        self.assertEqual(value2, "text 2")

    def test_stdout(self):
        with TestIO() as io:
            print("Hello World")
        self.assertEqual(io.stdout, "Hello World\n")
        self.assertEqual(io.stderr, "")

    def test_stderr(self):
        with TestIO() as io:
            print("Hello World", file=sys.stderr)
        self.assertEqual(io.stdout, "")
        self.assertEqual(io.stderr, "Hello World\n")

    def test_both(self):
        with TestIO() as io:
            print("Hello output", file=sys.stdout)
            print("Hello error", file=sys.stderr)
        self.assertEqual(io.stdout, "Hello output\n")
        self.assertEqual(io.stderr, "Hello error\n")

    def test_both_combined(self):
        with TestIO(combined=True) as io:
            print("Hello output", file=sys.stdout)
            print("Hello error", file=sys.stderr)
        self.assertEqual(io.combined, "Hello output\nHello error\n")

    def test_argparse_is_supported(self):
        with TestIO() as io:
            import argparse
            self.assertIs(argparse._sys, sys)
            self.assertIs(argparse._sys.stdout, io._fake_stdout)
            self.assertIs(argparse._sys.stderr, io._fake_stderr)
            parser = argparse.ArgumentParser(prog="foo")
            parser.print_usage()
        self.assertEqual(io.stdout, "usage: foo [-h]\n")
