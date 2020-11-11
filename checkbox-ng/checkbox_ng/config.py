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

from plainbox.impl.config import Configuration


_ = gettext.gettext

_logger = logging.getLogger("config")


SEARCH_DIRS = [
        '$SNAP_DATA',
        '/etc/xdg/',
        '~/.config/',
    ]

def expand_all(path):
    return os.path.expandvars(os.path.expanduser(path))

def load_configs(launcher_file=None):
    cfg = Configuration()
    for d in SEARCH_DIRS:
        # ATM the only supported filename for config is checkbox.conf
        config = expand_all(os.path.join(d, 'checkbox.conf'))
        if os.path.exists(config):
            cfg.update_from_another(
                Configuration.from_path(config),
                'config file: {}'.format(config))
    if launcher_file:
        cfg.update_from_another(
            Configuration.from_path(launcher_file),
            'Launcher file: {}'.format(launcher_file))
    return cfg
