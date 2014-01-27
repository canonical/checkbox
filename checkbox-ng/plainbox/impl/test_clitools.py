# This file is part of Checkbox.
#
# Copyright 2014 Canonical Ltd.
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
plainbox.impl.test_clitools
===========================

Test definitions for plainbox.impl.clitools module
"""

from unittest import TestCase

from plainbox.impl.clitools import CommandBase


class DummyCommand(CommandBase):
    """
    Concrete implementation of the abstract CommandBase class, for testing
    """

    def invoked(self):
        raise NotImplementedError()

    def register_parser(self, subparsers):
        raise NotImplementedError()


class TestCommandBase(TestCase):
    """
    Test cases for CommandBase
    """

    def test_get_command_name(self):
        """
        verify various modes of CommandBase.get_command_name()
        """
        # If class has a name attribute, just use it
        class TheFooCmd(DummyCommand):
            name = "foo"

        self.assertEqual(TheFooCmd().get_command_name(), "foo")

        # Otherwise just use lower-case class name
        class Foo(DummyCommand):
            pass

        self.assertEqual(Foo().get_command_name(), "foo")

        # The word "command" is stripped from the class name though
        class FooCommand(DummyCommand):
            pass

        self.assertEqual(FooCommand().get_command_name(), "foo")

    def test_get_command_help(self):
        """
        verify various modes of CommandBase.get_command_help()
        """
        # If class has a help attribute, just use it
        class Foo(DummyCommand):
            help = "help text"

        self.assertEqual(Foo().get_command_help(), "help text")

        # Otherwise use the first line of the docstring
        class Foo(DummyCommand):
            """
            help text

            other stuff
            """

        self.assertEqual(Foo().get_command_help(), "help text")

        # If there is no docstring, there is no help either
        class Foo(DummyCommand):
            pass

        self.assertEqual(Foo().get_command_help(), None)

    def test_get_command_description(self):
        """
        verify various modes of CommandBase.get_command_description()
        """
        # If class has a description attribute, just use it
        class Foo(DummyCommand):
            description = "description"

        self.assertEqual(Foo().get_command_description(), "description")

        # Otherwise use the docstring skipping the first line
        class Foo(DummyCommand):
            """
            help text

            description
            """

        self.assertEqual(Foo().get_command_description(), "description")

        # The description runs until the end of the docstring or
        # until the string @EPILOG@
        class Foo(DummyCommand):
            """
            help text

            description

            @EPILOG@

            other stuff
            """

        self.assertEqual(Foo().get_command_description(), "description")

        # If there is no docstring, there is no description either
        class Foo(DummyCommand):
            pass

        self.assertEqual(Foo().get_command_description(), None)

    def test_get_command_epilog(self):
        """
        verify various modes of CommandBase.get_command_epilog()
        """
        # If class has a epilog attribute, just use it
        class Foo(DummyCommand):
            epilog = "epilog"

        self.assertEqual(Foo().get_command_epilog(), "epilog")

        # Otherwise use the docstring after the @EPILOG@ string
        class Foo(DummyCommand):
            """
            help text

            other stuff

            @EPILOG@

            epilog
            """

        self.assertEqual(Foo().get_command_epilog(), "epilog")

        # If the @EPILOG@ line isn't present, there is no epilog
        class Foo(DummyCommand):
            """
            help text

            other stuff
            """

        self.assertEqual(Foo().get_command_epilog(), None)

        # If there is no docstring, there is no epilog either
        class Foo(DummyCommand):
            pass

        self.assertEqual(Foo().get_command_epilog(), None)
