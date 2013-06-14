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
:mod:`plainbox.impl.box` -- command line interface
==================================================

.. warning::

    THIS MODULE DOES NOT HAVE STABLE PUBLIC API
"""

import argparse
import errno
import logging
import pdb
import sys

from plainbox import __version__ as version
from plainbox.impl.applogic import PlainBoxConfig
from plainbox.impl.checkbox import CheckBox
from plainbox.impl.commands.check_config import CheckConfigCommand
from plainbox.impl.commands.dev import DevCommand
from plainbox.impl.commands.run import RunCommand
from plainbox.impl.commands.selftest import SelfTestCommand
from plainbox.impl.commands.sru import SRUCommand


logger = logging.getLogger("plainbox.box")


class PlainBox:
    """
    Command line interface to PlainBox
    """

    def __init__(self):
        """
        Initialize all the variables, real stuff happens in main()
        """
        self._early_parser = None  # set in _early_init()
        self._config = None  # set in _late_init()
        self._checkbox = None  # set in _late_init()
        self._parser = None  # set in _late_init()

    def main(self, argv=None):
        """
        Run as if invoked from command line directly
        """
        self.early_init()
        early_ns = self._early_parser.parse_args(argv)
        self.late_init(early_ns)
        logger.debug("parsed early namespace: %s", early_ns)
        # parse the full command line arguments, this is also where we
        # do argcomplete-dictated exit if bash shell completion is requested
        ns = self._parser.parse_args(argv)
        logger.debug("parsed full namespace: %s", ns)
        self.final_init(ns)
        return self.dispatch_and_catch_exceptions(ns)

    @classmethod
    def get_config_cls(cls):
        """
        Get the Config class that is used by this implementation.

        This can be overriden by subclasses to use a different config class
        that is suitable for the particular application.
        """
        return PlainBoxConfig

    @classmethod
    def get_exec_name(cls):
        """
        Get the name of this executable
        """
        return "plainbox"

    @classmethod
    def get_exec_version(cls):
        """
        Get the version reported by this executable
        """
        return "{}.{}.{}".format(*version[:3])

    def add_subcommands(self, subparsers):
        """
        Add top-level subcommands to the argument parser.

        This can be overriden by subclasses to use a different set of
        top-level subcommands.
        """
        # TODO: switch to plainbox plugins
        RunCommand(self._checkbox).register_parser(subparsers)
        SelfTestCommand().register_parser(subparsers)
        SRUCommand(self._checkbox, self._config).register_parser(subparsers)
        CheckConfigCommand(self._config).register_parser(subparsers)
        DevCommand(self._checkbox, self._config).register_parser(subparsers)

    def early_init(self):
        """
        Do very early initialization. This is where we initalize stuff even
        without seeing a shred of command line data or anything else.
        """
        self._early_parser = self.construct_early_parser()

    def late_init(self, early_ns):
        """
        Initialize with early command line arguments being already parsed
        """
        # Load plainbox configuration
        self._config = self.get_config_cls().get()
        # Load and initialize checkbox provider
        # TODO: rename to provider, switch to plugins
        self._checkbox = CheckBox(
            mode=None if early_ns.checkbox == 'auto' else early_ns.checkbox)
        # Construct the full command line argument parser
        self._parser = self.construct_parser()

    def final_init(self, ns):
        """
        Do some final initialization just before the command gets
        dispatched. This is empty here but maybe useful for subclasses.
        """

    def construct_early_parser(self):
        """
        Create a parser that captures some of the early data we need to
        be able to have a real parser and initialize the rest.
        """
        parser = argparse.ArgumentParser(add_help=False)
        # Fake --help and --version
        parser.add_argument("-h", "--help", action="store_const", const=None)
        parser.add_argument("--version", action="store_const", const=None)
        self.add_early_parser_arguments(parser)
        # A catch-all net for everything else
        parser.add_argument("rest", nargs="...")
        return parser

    def construct_parser(self):
        parser = argparse.ArgumentParser(
            prog=self.get_exec_name(),
            formatter_class=argparse.ArgumentDefaultsHelpFormatter)
        parser.add_argument(
            "--version", action="version", version=self.get_exec_version())
        # Add all the things really parsed by the early parser so that it
        # shows up in --help and bash tab completion.
        self.add_early_parser_arguments(parser)
        subparsers = parser.add_subparsers()
        self.add_subcommands(subparsers)
        # Enable argcomplete if it is available.
        try:
            import argcomplete
        except ImportError:
            pass
        else:
            argcomplete.autocomplete(parser)
        return parser

    def add_early_parser_arguments(self, parser):
        # Since we need a CheckBox instance to create the main argument parser
        # and we need to be able to specify where Checkbox is, we parse that
        # option alone before parsing everything else
        # TODO: rename this to -p | --provider
        parser.add_argument(
            '-c', '--checkbox',
            action='store',
            # TODO: have some public API for this, pretty please
            choices=list(CheckBox._DIRECTORY_MAP.keys()) + ['auto'],
            default='auto',
            help="where to find the installation of CheckBox.")
        group = parser.add_argument_group(
            title="logging and debugging")
        # Add the --pdb flag
        group.add_argument(
            "-P", "--pdb",
            action="store_true",
            default=False,
            help="jump into pdb (python debugger) when a command crashes")
        # Add the --debug-interrupt flag
        group.add_argument(
            "-I", "--debug-interrupt",
            action="store_true",
            default=False,
            help="crash on SIGINT/KeyboardInterrupt, useful with --pdb")

    def dispatch_command(self, ns):
        # Argh the horrror!
        #
        # Since CPython revision cab204a79e09 (landed for python3.3)
        # http://hg.python.org/cpython/diff/cab204a79e09/Lib/argparse.py
        # the argparse module behaves differently than it did in python3.2
        #
        # In practical terms subparsers are now optional in 3.3 so all of the
        # commands are no longer required parameters.
        #
        # To compensate, on python3.3 and beyond, when the user just runs
        # plainbox without specifying the command, we manually, explicitly do
        # what python3.2 did: call parser.error(_('too few arguments'))
        if (sys.version_info[:2] >= (3, 3)
                and getattr(ns, "command", None) is None):
            self._parser.error(argparse._("too few arguments"))
        else:
            return ns.command.invoked(ns)

    def dispatch_and_catch_exceptions(self, ns):
        try:
            return self.dispatch_command(ns)
        except SystemExit:
            # Don't let SystemExit be caught in the logic below, we really
            # just want to exit when that gets thrown.
            logger.debug("caught SystemExit, exiting")
            # We may want to raise SystemExit as it can carry a status code
            # along and we cannot just consume that.
            raise
        except BaseException as exc:
            logger.debug("caught %r, deciding on what to do next", exc)
            # For all other exceptions (and I mean all), do a few checks
            # and perform actions depending on the command line arguments
            # By default we want to re-raise the exception
            action = 'raise'
            # We want to ignore IOErrors that are really EPIPE
            if isinstance(exc, IOError):
                if exc.errno == errno.EPIPE:
                    action = 'ignore'
            # We want to ignore KeyboardInterrupt unless --debug-interrupt
            # was passed on command line
            elif isinstance(exc, KeyboardInterrupt):
                if ns.debug_interrupt:
                    action = 'debug'
                else:
                    action = 'ignore'
            else:
                # For all other execptions, debug if requested
                if ns.pdb:
                    action = 'debug'
            logger.debug("action for exception %r is %s", exc, action)
            if action == 'ignore':
                return 0
            elif action == 'raise':
                logging.getLogger("plainbox.crashes").fatal(
                    "Executable %r invoked with %r has crashed",
                    self.get_exec_name(), ns, exc_info=1)
                raise
            elif action == 'debug':
                logger.error("caught runaway exception: %r", exc)
                logger.error("starting debugger...")
                pdb.post_mortem()
                return 1


def main(argv=None):
    raise SystemExit(PlainBox().main(argv))


def get_builtin_jobs():
    raise NotImplementedError("get_builtin_jobs() not implemented")


def save(something, somewhere):
    raise NotImplementedError("save() not implemented")


def run(*args, **kwargs):
    raise NotImplementedError("run() not implemented")
