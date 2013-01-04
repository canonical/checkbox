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
plainbox.impl.test_box
======================

Test definitions for plainbox.impl.box module
"""

from io import StringIO
from unittest import TestCase
from inspect import cleandoc
import sys


from plainbox import __version__ as version
from plainbox.impl.box import main


class TestIO:
    """
    Helper class for capturing stdin, stdout, stderr IO for testing
    """

    def __init__(self, *, input=None, combined=False):
        self._combined = combined
        self._input = input

    def __enter__(self):
        # Remember the real objects that we'll replace
        self._real_stdin = sys.stdin
        self._real_stdout = sys.stdout
        self._real_stderr = sys.stderr
        # Create fake objects. In combined mode the output is more similar to
        # what a user at a console would see (stdout and stderr are
        # intertwined)
        self._fake_stdin = StringIO(self._input)
        if self._combined:
            self._fake_combined = StringIO()
        else:
            self._fake_stdout = StringIO()
            self._fake_stderr = StringIO()
        # Stub-away .close()
        if self._combined:
            self._fake_combined.close = lambda: None
        else:
            self._fake_stdout.close = lambda: None
            self._fake_stderr.close = lambda: None
        # Lastly replace the real objects
        sys.stdin = self._fake_stdin
        if self._combined:
            sys.stdout = self._fake_combined
            sys.stderr = self._fake_combined
        else:
            sys.stdout = self._fake_stdout
            sys.stderr = self._fake_stderr
        return self

    def __exit__(self, *exc):
        # Save the data that was written to stdout and stderr
        if self._combined:
            self._test_combined = self._fake_combined.getvalue()
        else:
            self._test_stdout = self._fake_stdout.getvalue()
            self._test_stderr = self._fake_stderr.getvalue()
        # Close all fake streams
        self._fake_stdin.close()
        if self._combined:
            self._fake_combined.close()
        else:
            self._fake_stdout.close()
            self._fake_stderr.close()
        # And restore original streams
        sys.stdin = self._real_stdin
        sys.stdout = self._real_stdout
        sys.stderr = self._real_stderr

    @property
    def stdout(self):
        """
        All stdout output
        """
        return self._test_stdout

    @property
    def stderr(self):
        """
        All stderr output
        """
        return self._test_stderr

    @property
    def combined(self):
        """
        All output combined from stdout and stderr
        """
        return self._test_combined


class TestIOTest(TestCase):

    def test_stdin(self):
        with TestIO() as io:
            self.assertRaises(EOFError, input)

    def test_stdin_text(self):
        with TestIO(input="text 1\ntext 2\n") as io:
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


class TestMain(TestCase):

    def test_version(self):
        with TestIO(combined=True) as io:
            with self.assertRaises(SystemExit) as call:
                main(['--version'])
        self.assertEqual(call.exception.args, (0,))
        self.assertEqual(io.combined, "{}.{}.{}\n".format(*version[:3]))

    def test_help(self):
        with TestIO(combined=True) as io:
            with self.assertRaises(SystemExit) as call:
                main(['--help'])
        self.assertEqual(call.exception.args, (0,))
        self.maxDiff = None
        expected = """
        usage: plainbox [-h] [-v] [-l {DEBUG,INFO,WARNING,ERROR,CRITICAL}]
                        [-u {headless,text,graphics}] [--not-interactive]
                        [--load-extra FILE] [-r PATTERN] [-W WHITELIST] [-n]
                        [-f FORMAT] [-p OPTIONS] [-o FILE] [--list-jobs]
                        [--list-expressions] [--dot] [--dot-resources]

        optional arguments:
          -h, --help            show this help message and exit
          -v, --version         show program's version number and exit
          -l {DEBUG,INFO,WARNING,ERROR,CRITICAL}, --log-level {DEBUG,INFO,WARNING,ERROR,CRITICAL}
                                Set logging level

        user interface options:
          -u {headless,text,graphics}, --ui {headless,text,graphics}
                                select the UI front-end (defaults to auto)
          --not-interactive     Skip tests that require interactivity

        job definition options:
          --load-extra FILE     Load extra job definitions from FILE
          -r PATTERN, --run-pattern PATTERN
                                Run jobs matching the given pattern
          -W WHITELIST, --whitelist WHITELIST
                                Load whitelist containing run patterns
          -n, --dry-run         Don't actually run any jobs

        output options:
          -f FORMAT, --output-format FORMAT
                                Save test results in the specified FORMAT (pass ? for
                                a list of choices)
          -p OPTIONS, --output-options OPTIONS
                                Comma-separated list of options for the export
                                mechanism (pass ? for a list of choices)
          -o FILE, --output-file FILE
                                Save test results to the specified FILE (or to stdout
                                if FILE is -)

        special options:
          --list-jobs           List jobs instead of running them
          --list-expressions    List all unique resource expressions
          --dot                 Print a graph of jobs instead of running them
          --dot-resources       Render resource relationships (for --dot)
        """
        self.assertEqual(io.combined, cleandoc(expected) + "\n")

    def test_dummy(self):
        with TestIO(combined=True) as io:
            main([])
        expected = """
        ===============================[ Analyzing Jobs ]===============================
        ==============================[ Running All Jobs ]==============================
        ==================================[ Results ]===================================
        """
        self.assertEqual(io.combined, cleandoc(expected) + "\n")
