# This file is part of Checkbox.
#
# Copyright 2013-2023 Canonical Ltd.
# Written by:
#   Maciej Kisielewski <maciej.kisielewski@canonical.com>
#   Massimiliano Girardi <massimiliano.girardi@canonical.com>
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


# The order here defines the priority
# launcher > ~/.config > /etc/xdg > $SNAP_DATA
SEARCH_DIRS = [
    "~/.config/",
    "/etc/xdg/",
    "$SNAP_DATA",
]


def expand_all(path):
    """Expand both: envvars and ~ in `path`."""
    return os.path.expandvars(os.path.expanduser(path))


def _search_configs_by_name(name: str) -> "list[str]":
    """
    Returns all well known config locations that have a `name` file
    in them
    """
    if os.path.isabs(expand_all(name)):
        return [name]
    to_r = []
    _logger.debug("Searching for %s files...", name)
    for sdir in SEARCH_DIRS:
        config = expand_all(os.path.join(sdir, name))
        if os.path.exists(config):
            to_r.append(config)
        else:
            _logger.debug("not found in %s", sdir)
    return to_r


def load_configs(launcher_file=None, cfg=None):
    """
    Read a chain of configs/launchers.

    In theory there can be a very long list of configs that are linked by
    specifying config_filename in each. Each config that defines a
    config_filename imports the values that are defined in the path/name
    provided. The imported are overwritten by the importee and whoever has
    an higher priority.

    Ex: If ~/.config/checkbox.conf has config_filename A and we have both
        ~/.config/A and /etc/xdg/A:

        - ~/.config/A has an higher priority than /etc/xdg/A
        - anything that ~/.config/A imports has a higher priority
            than /etc/xdg/A but lower than ~/.config/A itself
        - anything that /etc/xdg/A imports has the lowest possible
            priority
    """
    assert not (
        launcher_file and cfg
    ), "config_filename in cfg will be ignored, FIXME"
    if not cfg:
        cfg = Configuration()
    if launcher_file:
        # Use the config_filename if it is defined in launcher
        launcher_file_conf = Configuration.from_path(launcher_file)
        to_load_conf_names = _search_configs_by_name(
            launcher_file_conf.get_value("config", "config_filename")
        )
    else:
        # configs to read which may reference other configs
        to_load_conf_names = _search_configs_by_name(
            cfg.get_value("config", "config_filename")
        )
    # used to avoid "loops"
    # Note: checkbox.conf is always the default "config_filename"
    #       so we *always* have a loop eventually
    already_loaded = {cfg.get_value("config", "config_filename")}
    loaded_confs_sources = []
    while to_load_conf_names:
        to_load = to_load_conf_names.pop(0)
        curr_cfg = Configuration.from_path(to_load)
        imported_cfg_name = curr_cfg.get_value("config", "config_filename")
        if imported_cfg_name and imported_cfg_name not in already_loaded:
            # next load what this conf imports
            to_load_conf_names = (
                _search_configs_by_name(imported_cfg_name) + to_load_conf_names
            )
            already_loaded.add(imported_cfg_name)
        loaded_confs_sources.append((curr_cfg, to_load))

    # here if A -> B -> C in loaded_confs_sources we have [A_conf, B_conf, C_conf]
    #  but A -> B means A overrides B so we reverse order
    _logger.debug("Applying conf, latest applied has the highest priority")
    for conf, source in reversed(loaded_confs_sources):
        _logger.debug("Applying %s", source)
        cfg.update_from_another(conf, "config file: {}".format(source))

    if launcher_file:
        cfg.update_from_another(
            launcher_file_conf,
            "Launcher file: {}".format(launcher_file),
        )

    return cfg
