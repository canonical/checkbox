# This file is part of Checkbox.
#
# Copyright 2014 Canonical Ltd.
# Written by:
#  Maciej Kisielewski <maciej.kisielewski@canonical.com>
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

import json
import os
import subprocess
import sys

from plainbox import __version__ as plainbox_version
from plainbox.i18n import docstring
from plainbox.i18n import gettext as _
from plainbox.i18n import gettext_noop as N_
from plainbox.impl import get_plainbox_dir
from plainbox.impl.applogic import PlainBoxConfig
from plainbox.impl.clitools import SingleCommandToolMixIn
from plainbox.impl.commands import PlainBoxCommand
from plainbox.impl.commands import PlainBoxToolBase


@docstring(
    # TRANSLATORS: please leave various options (both long and short forms),
    # environment variables and paths in their original form. Also keep the
    # special @EPILOG@ string. The first line of the translation is special and
    # is used as the help message. Please keep the pseudo-statement form and
    # don't finish the sentence with a dot. Pay extra attention to whitespace.
    # It must be correctly preserved or the result won't work. In particular
    # the leading whitespace *must* be preserved and *must* have the same
    # length on each line.
    N_("""
    run qml job in standalone shell

    Runs specified file as it would be a plainbox' qml job.
    Returns 0 if job returned 'pass', 1 if job returned 'fail', or
    other value in case of an error.

    @EPILOG@

    General purpose of this command is to make development of qml-native jobs
    faster, by making it easier to test qml file(s) that constitute to job
    without resorting to installation of provider and running plainbox run.
    Typical approach to the development of new qml job would be as follows:

    - have an idea for a job

    - create a qml file in Ubuntu-SDK or Your Favourite Editor

    - hack on the file and iterate using qmlscene (or use plainbox-qml-shell
      immediately if you start with next point)

    - make it conformant to plainbox qml-native API described in CEP-5
      (calling test-done at the end)

    - copy qml file over to data dir of a provider and add a job unit to it

    """))
class QmlShellCommand(PlainBoxCommand):
    def register_parser(self, subparsers):
        parser = subparsers.add_parser(
            "plainbox-qml-shell",
            help=_("run qml-native test in a standalone shell"))

        self.register_arguments(parser)

    def register_arguments(self, parser):
        parser.set_defaults(command=self)
        parser.add_argument('QML_FILE', help=_("qml file with job to be run"),
                            metavar='QML-FILE')

    def invoked(self, ns):
        QML_SHELL_PATH = os.path.join(get_plainbox_dir(), 'qml_shell',
                                      'qml_shell.qml')
        QML_MODULES_PATH = os.path.join(get_plainbox_dir(), 'data',
                                        'plainbox-qml-modules')

        test_result_object_prefix = "qml: __test_result_object:"
        test_res = None
        p = subprocess.Popen(['qmlscene', '-I', QML_MODULES_PATH, '--job',
                             os.path.abspath(ns.QML_FILE), QML_SHELL_PATH],
                             stderr=subprocess.PIPE)
        for line in iter(p.stderr.readline, ''):
            line = line.decode(sys.stderr.encoding)
            if not line:
                break
            if line.startswith(test_result_object_prefix):
                obj_json = line[len(test_result_object_prefix):]
                test_res = json.loads(obj_json)
            else:
                print(line)

        if not test_res:
            return _("Job did not return any result")

        print(_("Test outcome: {}").format(test_res['outcome']))
        return test_res['outcome'] != "pass"


class PlainboxQmlShellTool(SingleCommandToolMixIn, PlainBoxToolBase):
    def get_command(self):
        return QmlShellCommand()

    @classmethod
    def get_exec_name(cls):
        return "plainbox-qml-shell"

    @classmethod
    def get_exec_version(cls):
        """
        Get the version reported by this executable
        """
        return cls.format_version_tuple(plainbox_version)

    @classmethod
    def get_config_cls(cls):
        """
        Get the Config class that is used by this implementation.

        This can be overridden by subclasses to use a different config
        class that is suitable for the particular application.
        """
        return PlainBoxConfig


def main(argv=None):
    raise SystemExit(PlainboxQmlShellTool().main(argv))


def get_parser_for_sphinx():
    return PlainboxQmlShellTool().construct_parser()
