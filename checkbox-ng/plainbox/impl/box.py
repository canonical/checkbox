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
:mod:`plainbox.impl.box` -- command line interface
==================================================

.. warning::

    THIS MODULE DOES NOT HAVE STABLE PUBLIC API
"""
import collections
import logging
import os

from plainbox import __version__ as plainbox_version
from plainbox.i18n import gettext as _
from plainbox.impl.applogic import PlainBoxConfig
from plainbox.impl.clitools import LazyLoadingToolMixIn
from plainbox.impl.commands import PlainBoxToolBase
from plainbox.impl.logging import setup_logging
from plainbox.impl.secure.plugins import LazyPlugInCollection


logger = logging.getLogger("plainbox.box")


class PlainBoxTool(LazyLoadingToolMixIn, PlainBoxToolBase):
    """
    Command line interface to PlainBox
    """

    def get_command_collection(self):
        p = "plainbox.impl.commands."
        return LazyPlugInCollection(collections.OrderedDict([
            ('run', (p + "cmd_run:RunCommand", self._load_providers,
                     self._load_config)),
            ('session', (p + "cmd_session:SessionCommand",
                         self._load_providers)),
            ('device', (p + "cmd_device:DeviceCommand",)),
            ('self-test', (p + "cmd_selftest:PlainboxSelfTestCommand",)),
            ('check-config', (p + "cmd_check_config:CheckConfigCommand",
                              self._load_config,)),
            ('dev', (p + "dev:DevCommand", self._load_providers,
                     self._load_config)),
            ('startprovider', (p + "cmd_startprovider:StartProviderCommand",)),
        ]))

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
        return cls.format_version_tuple(plainbox_version)

    def create_parser_object(self):
        parser = super().create_parser_object()
        parser.prog = self.get_exec_name()
        # TRANSLATORS: '--help' and '--version' are not translatable,
        # but '[options]' and '<command>' are.
        parser.usage = _("{0} [--help] [--version] | [options] <command>"
                         " ...").format(self.get_exec_name())
        return parser

    @classmethod
    def get_config_cls(cls):
        """
        Get the Config class that is used by this implementation.

        This can be overridden by subclasses to use a different config
        class that is suitable for the particular application.
        """
        return PlainBoxConfig

    def get_gettext_domain(self):
        return "plainbox"

    def get_locale_dir(self):
        return os.getenv("PLAINBOX_LOCALE_DIR", None)


class StubBoxTool(PlainBoxTool):
    """
    Command line interface to StubBox

    The 'stubbox' executable is just just like plainbox but it contains the
    special stubbox provider with representative test jobs.
    """

    @classmethod
    def get_exec_name(cls):
        return "stubbox"

    def _load_providers(self):
        logger.info("Loading stubbox provider...")
        from plainbox.impl.providers.special import get_stubbox
        from plainbox.impl.providers.special import get_exporters
        return [get_stubbox(), get_exporters()]


def main(argv=None):
    raise SystemExit(PlainBoxTool().main(argv))


def stubbox_main(argv=None):
    raise SystemExit(StubBoxTool().main(argv))


def get_parser_for_sphinx():
    return PlainBoxTool().construct_parser()


# Setup logging before anything else starts working.
# If we do it in main() or some other place then unit tests will see
# "leaked" log files which are really closed when the runtime shuts
# down but not when the tests are finishing
setup_logging()
