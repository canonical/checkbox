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

from plainbox.impl.launcher import DefaultLauncherDefinition
from plainbox.impl.launcher import LauncherDefinition


_ = gettext.gettext

_logger = logging.getLogger("config")

def expand_all(path):
    return os.path.expandvars(os.path.expanduser(path))

def load_configs(launcher_file=None):
    # launcher can override the default name of config files to look for
    # so first we need to establish the filename to look for
    configs = []
    config_filename = 'checkbox.conf'
    launcher = DefaultLauncherDefinition()
    if launcher_file:
        configs.append(launcher_file)
        generic_launcher = LauncherDefinition()
        if not os.path.exists(launcher_file):
            _logger.error(_(
                "Unable to load launcher '%s'. File not found!"),
                launcher_file)
            raise SystemExit(1)
        generic_launcher.read(launcher_file)
        config_filename = os.path.expandvars(os.path.expanduser(
            generic_launcher.config_filename))
        launcher = generic_launcher.get_concrete_launcher()
    if os.path.isabs(config_filename):
        configs.append(config_filename)
    else:
        search_dirs = [
            '$SNAP_DATA',
            '/etc/xdg/',
            '~/.config/',
        ]
        for d in search_dirs:
            config = expand_all(os.path.join(d, config_filename))
            if os.path.exists(config):
                configs.append(config)
    launcher.read(configs)
    if launcher.problem_list:
        _logger.error(_("Unable to start launcher because of errors:"))
        for problem in launcher.problem_list:
            _logger.error("%s", str(problem))
        raise SystemExit(1)
    return launcher
