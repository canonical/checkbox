# This file is part of Checkbox.
#
# Copyright 2013-2019 Canonical Ltd.
# Written by:
#   Maciej Kisielewski <maciej.kisielewski@canonical.com>
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
:mod:`checkbox_ng.config` -- CheckBoxNG configuration
=====================================================
"""
import gettext
import itertools
import logging
import os

from plainbox.impl.applogic import PlainBoxConfig
from plainbox.impl.launcher import DefaultLauncherDefinition
from plainbox.impl.launcher import LauncherDefinition


_ = gettext.gettext

_logger = logging.getLogger("config")

class CheckBoxConfig(PlainBoxConfig):
    """
    Configuration for checkbox-ng
    """

    class Meta(PlainBoxConfig.Meta):
        # TODO: properly depend on xdg and use real code that also handles
        # XDG_CONFIG_HOME.
        #
        # NOTE: filename_list is composed of checkbox and plainbox variables,
        # mixed so that:
        # - checkbox takes precedence over plainbox
        # - ~/.config takes precedence over /etc
        filename_list = list(
            itertools.chain(
                *zip(
                    PlainBoxConfig.Meta.filename_list, (
                        '/etc/xdg/checkbox.conf',
                        os.path.expanduser('~/.config/checkbox.conf')))))

def load_configs(launcher_file=None):
    if not launcher_file:
        # launcher not supplied from cli - using the default one
        launcher = DefaultLauncherDefinition()
        configs = [
            '/etc/xdg/{}'.format(launcher.config_filename),
            os.path.expanduser(
                '~/.config/{}'.format(launcher.config_filename))]
    else:
        configs = [launcher_file]
        try:
            with open(launcher_file, 'rt', encoding='UTF-8') as stream:
                first_line = stream.readline()
                if not first_line.startswith("#!"):
                    stream.seek(0)
                text = stream.read()
        except IOError as exc:
            _logger.error(_("Unable to load launcher definition: %s"), exc)
            raise SystemExit(1)
        generic_launcher = LauncherDefinition()
        generic_launcher.read_string(text)
        config_filename = os.path.expandvars(
            generic_launcher.config_filename)
        # if wrapper specifies just the basename
        if not os.path.split(config_filename)[0]:
            if "SNAP_DATA" in os.environ:
                configs = [launcher_file]
                configs.append(os.path.join(
                    os.path.expandvars('$SNAP_DATA'), config_filename))
            else:
                configs += [
                    '/etc/xdg/{}'.format(config_filename),
                    os.path.expanduser('~/.config/{}'.format(
                        config_filename))]
        # if wrapper specifies an absolute file
        else:
            configs.append(config_filename)
        launcher = generic_launcher.get_concrete_launcher()
    launcher.read(configs)
    if launcher.problem_list:
        _logger.error(_("Unable to start launcher because of errors:"))
        for problem in launcher.problem_list:
            _logger.error("%s", str(problem))
        raise SystemExit(1)
    return launcher
