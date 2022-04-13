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
import logging
import os

from plainbox.impl.config import Configuration


_ = gettext.gettext

_logger = logging.getLogger("config")


SEARCH_DIRS = [
        '$SNAP_DATA',
        '/etc/xdg/',
        '~/.config/',
    ]


def expand_all(path):
    """Expand both: envvars and ~ in `path`."""
    return os.path.expandvars(os.path.expanduser(path))


def load_configs(launcher_file=None, cfg=None):
    """
    Read a chain of configs/launchers.

    In theory there can be a very long list of configs that are linked by
    specifying config_filename in each. Each time this happen we need to
    consider the new one and override all the values contained therein.
    And after this chain is exhausted the values in the launcher should
    take precedence over the previously read.
    Warning: some recursion ahead.
    """
    if not cfg:
        cfg = Configuration()
    previous_cfg_name = cfg.get_value('config', 'config_filename')
    if os.path.isabs(expand_all(previous_cfg_name)):
        cfg.update_from_another(
            Configuration.from_path(expand_all(previous_cfg_name)),
            'config file: {}'.format(previous_cfg_name))
    else:
        for sdir in SEARCH_DIRS:
            config = expand_all(os.path.join(sdir, previous_cfg_name))
            if os.path.exists(config):
                cfg.update_from_another(
                    Configuration.from_path(config),
                    'config file: {}'.format(config))
            else:
                _logger.info(
                    "Referenced config file doesn't exist: %s", config)
    new_cfg_filename = cfg.get_value('config', 'config_filename')
    if new_cfg_filename != previous_cfg_name:
        load_configs(launcher_file, cfg)
    if launcher_file:
        cfg.update_from_another(
            Configuration.from_path(launcher_file),
            'Launcher file: {}'.format(launcher_file))
    return cfg
