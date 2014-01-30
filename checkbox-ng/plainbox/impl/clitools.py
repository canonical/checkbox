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
:mod:`plainbox.impl.clitools ` -- support code for command line utilities
=========================================================================

.. warning::

    THIS MODULE DOES NOT HAVE STABLE PUBLIC API
"""

import abc
import argparse
import errno
import inspect
import logging
import os
import pdb
import sys

from plainbox.impl.logging import adjust_logging
from plainbox.impl._argparse import LegacyHelpFormatter


logger = logging.getLogger("plainbox.clitools")


class CommandBase(metaclass=abc.ABCMeta):
    """
    Simple interface class for sub-commands of :class:`ToolBase`.

    Command objects like this are consumed by `ToolBase` subclasses to
    implement hierarchical command system. The API supports arbitrary many sub
    commands in arbitrary nesting arrangement.

    Subcommands need to be registered inside the :meth:`register_parser()`,
    either manually by calling add_parser() on the passed subparsers instance,
    or by calling the helper :meth:`add_subcommand()` method. By common
    convention each subclass of CommandBase adds exactly one subcommand to the
    parser.
    """

    @abc.abstractmethod
    def invoked(self, ns):
        """
        Implement what should happen when the command gets invoked

        The ns is the namespace produced by argument parser
        """

    @abc.abstractmethod
    def register_parser(self, subparsers):
        """
        Implement what should happen to register the additional parser for this
        command. The subparsers argument is the return value of
        ArgumentParser.add_subparsers()
        """

    def autopager(self):
        """
        Enable automatic pager.

        This invokes :func:`autopager()` which wraps execution in a pager
        program so that long output is not a problem to read. Do not call this
        in interactive commands.
        """
        autopager()

    def get_command_name(self):
        """
        Get the name of the command, as seen on command line.

        :returns:
            self.name, if defined
        :returns:
            lower-cased class name, with the string "command" stripped out
        """
        try:
            return self.name
        except AttributeError:
            name = self.__class__.__name__.lower()
            if name.endswith("command"):
                name = name.replace("command", "")
        return name

    def get_command_help(self):
        """
        Get a single-line help string associated with this command, as seen on
        command line.

        :returns:
            self.help, if defined
        :returns:
            The first line of the docstring of this class, if any
        :returns:
            None, otherwise
        """
        try:
            return self.help
        except AttributeError:
            pass
        try:
            return inspect.getdoc(self.__class__).splitlines()[0]
        except (AttributeError, ValueError, IndexError):
            pass

    def get_command_description(self):
        """
        Get a multi-line description string associated with this command, as
        seen on command line.

        The description is printed after command usage but before argument and
        option definitions.

        :returns:
            self.description, if defined
        :returns:
            A substring of the class docstring between the first line (which
            goes to :meth:`get_command_help()`) and the string ``@EPILOG@`, if
            present, or the end of the docstring, if any.
        :returns:
            None, otherwise
        """
        try:
            return self.description
        except AttributeError:
            pass
        try:
            return '\n'.join(
                inspect.getdoc(self.__class__).splitlines()[1:]
            ).split('@EPILOG@', 1)[0].strip()
        except (AttributeError, IndexError, ValueError):
            pass

    def get_command_epilog(self):
        """
        Get a multi-line description string associated with this command, as
        seen on command line.

        The epilog is printed after the definitions of arguments and options

        :returns:
            self.epilog, if defined
        :returns:
            A substring of the class docstring between the string ``@EPILOG``
            and the end of the docstring, if defined
        :returns:
            None, otherwise
        """
        try:
            return self.epilog
        except AttributeError:
            pass
        try:
            return '\n'.join(
                inspect.getdoc(self.__class__).splitlines()[1:]
            ).split('@EPILOG@', 1)[1].strip()
        except (AttributeError, IndexError, ValueError):
            pass

    def add_subcommand(self, subparsers):
        """
        Add a parser to the specified subparsers instance.

        :returns:
            The new parser for the added subcommand

        This command works by convention, depending on
        :meth:`get_command_name(), :meth:`get_command_help()`,
        :meth:`get_command_description()` and :meth:`get_command_epilog()`.
        """
        parser = subparsers.add_parser(
            self.get_command_name(),
            help=self.get_command_help(),
            description=self.get_command_description(),
            epilog=self.get_command_epilog())
        parser.set_defaults(command=self)
        return parser


class ToolBase(metaclass=abc.ABCMeta):
    """
    Base class for implementing programs with hierarchical subcommands

    The tools support a variety of sub-commands, logging and debugging support.
    If argcomplete module is available and used properly in the shell then
    advanced tab-completion is also available.

    There are three methods to implement for a basic tool. Those are:

    1. :meth:`get_exec_name()` -- to know how the tool will be called
    2. :meth:`get_exec_version()` -- to know how the version of the tool
    3. :meth:`add_subcommands()` -- to add some actual commands to execute

    This class has some complex control flow to support important and
    interesting use cases. It is important to know that input is parsed with
    two parsers, the early parser and the full parser.  The early parser
    quickly checks for a fraction of supported arguments and uses that data to
    initialize environment before construction of a full parser is possible.
    The full parser sees the reminder of the input and does not re-parse things
    that where already handled.
    """

    def __init__(self):
        """
        Initialize all the variables, real stuff happens in main()
        """
        self._early_parser = None  # set in _early_init()
        self._parser = None  # set in main()

    def main(self, argv=None):
        """
        Run as if invoked from command line directly
        """
        # Another try/catch block for catching KeyboardInterrupt
        # This one is really only meant for the early init abort
        # (when someone runs main but bails out before we really
        # get to the point when we do something useful and setup
        # all the exception handlers).
        try:
            self.early_init()
            early_ns = self._early_parser.parse_args(argv)
            self.late_init(early_ns)
            # Construct the full command line argument parser
            self._parser = self.construct_parser()
            logger.debug("parsed early namespace: %s", early_ns)
            # parse the full command line arguments, this is also where we
            # do argcomplete-dictated exit if bash shell completion
            # is requested
            ns = self._parser.parse_args(argv)
            logger.debug("parsed full namespace: %s", ns)
            self.final_init(ns)
        except KeyboardInterrupt:
            pass
        else:
            return self.dispatch_and_catch_exceptions(ns)

    @classmethod
    @abc.abstractmethod
    def get_exec_name(cls):
        """
        Get the name of this executable
        """

    @classmethod
    @abc.abstractmethod
    def get_exec_version(cls):
        """
        Get the version reported by this executable
        """

    @abc.abstractmethod
    def add_subcommands(self, subparsers):
        """
        Add top-level subcommands to the argument parser.

        This can be overridden by subclasses to use a different set of
        top-level subcommands.
        """

    def early_init(self):
        """
        Do very early initialization. This is where we initialize stuff even
        without seeing a shred of command line data or anything else.
        """
        self._early_parser = self.construct_early_parser()

    def late_init(self, early_ns):
        """
        Initialize with early command line arguments being already parsed
        """
        adjust_logging(
            level=early_ns.log_level, trace_list=early_ns.trace,
            debug_console=early_ns.debug_console)

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

    def create_parser_object(self):
        """
        Construct a bare parser object.

        This method is responsible for creating the main parser object and
        adding --version and other basic top-level properties to it (but not
        any of the commands).

        It exists as a separate method in case some special customization is
        required, so that subclasses can still use standard version of
        :meth:`construct_parser()`.

        :returns:
            argparse.ArgumentParser instance.
        """
        parser = argparse.ArgumentParser(
            prog=self.get_exec_name(),
            formatter_class=LegacyHelpFormatter)
        parser.add_argument(
            "--version", action="version", version=self.get_exec_version())
        return parser

    def construct_parser(self):
        parser = self.create_parser_object()
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
        group = parser.add_argument_group(
            title="logging and debugging")
        # Add the --log-level argument
        group.add_argument(
            "-l", "--log-level",
            action="store",
            choices=('DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'),
            default=None,
            help=argparse.SUPPRESS)
        # Add the --verbose argument
        group.add_argument(
            "-v", "--verbose",
            dest="log_level",
            action="store_const",
            const="INFO",
            help="be more verbose (same as --log-level=INFO)")
        # Add the --debug flag
        group.add_argument(
            "-D", "--debug",
            dest="log_level",
            action="store_const",
            const="DEBUG",
            help="enable DEBUG messages on the root logger")
        # Add the --debug flag
        group.add_argument(
            "-C", "--debug-console",
            action="store_true",
            help="display DEBUG messages in the console")
        # Add the --trace flag
        group.add_argument(
            "-T", "--trace",
            metavar="LOGGER",
            action="append",
            default=[],
            help=("enable DEBUG messages on the specified logger "
                  "(can be used multiple times)"))
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


def autopager(pager_list=['sensible-pager', 'less', 'more']):
    """
    Enable automatic pager

    :param pager_list:
        List of pager programs to try.

    :returns:
        Nothing immedaitely if auto-pagerification cannot be turned on.
        This is true when running on windows or when sys.stdout is not
        a tty.

    This function executes the following steps:

        * A pager is selected
        * A pipe is created
        * The current process forks
        * The parent uses execlp() and becomes the pager
        * The child/python carries on the execution of python code.
        * The parent/pager stdin is connected to the childs stdout.
        * The child/python stderr is connected to parent/pager stdin only when
          sys.stderr is connected to a tty

    .. note::
        Pager selection is influenced by the pager environment variabe. if set
        it will be prepended to the pager_list. This makes the expected
        behavior of allowing users to customize their environment work okay.

    .. warning::
        This function must not be used for interactive commands. Doing so
        will prevent users from feeding any input to plainbox as all input
        will be "stolen" by the pager process.
    """
    # If stdout is not connected to a tty or when running on win32, just return
    if not sys.stdout.isatty() or sys.platform == "win32":
        return
    # Check if the user has a PAGER set, if so, consider that the prime
    # candidate for the effective pager.
    pager = os.getenv('PAGER')
    if pager is not None:
        pager_list = [pager] + pager_list
    # Find the best pager based on user perferences and built-in knowledge
    try:
        pager_name, pager_pathname = find_exec(pager_list)
    except LookupError:
        # If none of the pagers are installed, just return
        return
    # Flush any pending output
    sys.stdout.flush()
    sys.stderr.flush()
    # Create a pipe that we'll use to glue ourselves to the pager
    read_end, write_end = os.pipe()
    # Fork so that we can have a pager process
    if os.fork() == 0:
        # NOTE: this is where plainbox will run
        # Rewire stdout and stderr (if a tty) to the pipe
        os.dup2(write_end, sys.stdout.fileno())
        if sys.stderr.isatty():
            os.dup2(write_end, sys.stderr.fileno())
        # Close the unused end of the pipe
        os.close(read_end)
    else:
        # NOTE: this is where the pager will run
        # Rewire stdin to the pipe
        os.dup2(read_end, sys.stdin.fileno())
        # Close the unused end of the pipe
        os.close(write_end)
        # Execute the pager
        os.execl(pager_pathname, pager_name)


def find_exec(name_list):
    """
    Find the first executable from name_list in PATH

    :param name_list:
        List of names of executable programs to look for, in the order
        of preference. Only basenames should be passed here (not absolute
        pathnames)
    :returns:
        Tuple (name, pathname), if the executable can be found
    :raises:
        LookupError if none of the names in name_list are executable
        programs in PATH
    """
    path_list = os.getenv('PATH', '').split(os.path.pathsep)
    for name in name_list:
        for path in path_list:
            pathname = os.path.join(path, name)
            if os.access(pathname, os.X_OK):
                return (name, pathname)
    raise LookupError(
        "Unable to find any of the executables {}".format(
            ", ".join(name_list)))
