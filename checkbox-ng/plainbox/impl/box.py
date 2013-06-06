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
:mod:`plainbox.impl.box` -- command line interface
==================================================

.. warning::

    THIS MODULE DOES NOT HAVE STABLE PUBLIC API
"""

from argparse import ArgumentParser, ArgumentDefaultsHelpFormatter
from argparse import _ as argparse_gettext
from logging import basicConfig
from logging import getLogger
import argparse
import sys

from plainbox import __version__ as version
from plainbox.impl.applogic import PlainBoxConfig
from plainbox.impl.checkbox import CheckBox
from plainbox.impl.commands.run import RunCommand
from plainbox.impl.commands.selftest import SelfTestCommand
from plainbox.impl.commands.special import SpecialCommand
from plainbox.impl.commands.sru import SRUCommand
from plainbox.impl.commands.check_config import CheckConfigCommand
from plainbox.impl.commands.script import ScriptCommand
from plainbox.impl.commands.dev import DevCommand


logger = getLogger("plainbox.box")


class PlainBox:
    """
    High-level plainbox object
    """

    def main(self, argv=None):
        # TODO: setup sane logging system that works just as well for Joe user
        # that runs checkbox from the CD as well as for checkbox developers and
        # custom debugging needs.  It would be perfect^Hdesirable not to create
        # another broken, never-rotated, uncapped logging crap that kills my
        # SSD by writing junk to ~/.cache/
        basicConfig(level="WARNING")
        config = PlainBoxConfig.get()
        # Since we need a CheckBox instance to create the main argument parser
        # and we need to be able to specify where Checkbox is, we parse that
        # option alone before parsing everything else
        checkbox_mode_args = ('-c', '--checkbox')
        checkbox_mode_kwargs = {'action': 'store',
                                'choices': list(CheckBox._DIRECTORY_MAP.keys()) + ['auto'],
                                'default': 'auto',
                                'help': "where to find the installation "
                                        "of Checkbox."}
        checkbox_mode_parser = self._construct_mode_parser(checkbox_mode_args,
                                                           checkbox_mode_kwargs)
        (mode_ns, rest) = checkbox_mode_parser.parse_known_args(argv)
        checkbox_mode = None if mode_ns.checkbox == 'auto' else mode_ns.checkbox
        self._checkbox = CheckBox(mode=checkbox_mode)
        parser = self._construct_parser(config, checkbox_mode_args,
                                        checkbox_mode_kwargs)
        ns = parser.parse_args(rest)
        # Set the desired log level
        getLogger("").setLevel(ns.log_level)
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
            parser.error(argparse_gettext("too few arguments"))
        else:
            return ns.command.invoked(ns)

    def _construct_mode_parser(self, checkbox_mode_args, checkbox_mode_kwargs):
        parser = ArgumentParser(add_help=False)
        parser.add_argument(*checkbox_mode_args, **checkbox_mode_kwargs)

        try:
            import argcomplete
        except ImportError:
            pass
        else:
            argcomplete.autocomplete(parser)

        return parser

    def _construct_parser(self, config, checkbox_mode_args,
                          checkbox_mode_kwargs):
        parser = ArgumentParser(
            prog="plainbox", formatter_class=ArgumentDefaultsHelpFormatter)
        parser.add_argument(
            "-v", "--version", action="version",
            version="{}.{}.{}".format(*version[:3]))
        parser.add_argument(
            "-l", "--log-level", action="store",
            choices=('DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'),
            default='WARNING',
            help=argparse.SUPPRESS)
        parser.add_argument(*checkbox_mode_args, **checkbox_mode_kwargs)
        subparsers = parser.add_subparsers()
        RunCommand(self._checkbox).register_parser(subparsers)
        SelfTestCommand().register_parser(subparsers)
        SRUCommand(self._checkbox, config).register_parser(subparsers)
        CheckConfigCommand(config).register_parser(subparsers)
        DevCommand(self._checkbox, config).register_parser(subparsers)
        try:
            import argcomplete
        except ImportError:
            pass
        else:
            argcomplete.autocomplete(parser)
        #group = parser.add_argument_group(title="user interface options")
        #group.add_argument(
        #    "-u", "--ui", action="store",
        #    default=None, choices=('headless', 'text', 'graphics'),
        #    help="select the UI front-end (defaults to auto)")
        return parser


def main(argv=None):
    # Instantiate a global plainbox instance
    # XXX: Allow one to control the checkbox= argument via
    # environment or config.
    try:
        box = PlainBox()
        retval = box.main(argv)
        raise SystemExit(retval)
    except KeyboardInterrupt:
        return 1
    except IOError as exc:
        if exc.errno == 32:  # pipe
            pass
        else:
            raise



def get_builtin_jobs():
    raise NotImplementedError("get_builtin_jobs() not implemented")


def save(something, somewhere):
    raise NotImplementedError("save() not implemented")


def run(*args, **kwargs):
    raise NotImplementedError("run() not implemented")
