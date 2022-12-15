# This file is part of Checkbox.
#
# Copyright 2021 Canonical Ltd.
# Written by:
#   Maciej Kisielewski <maciej.kisielewski@canonical.com>
#   Sylvain Pineau <sylvain.pineau@canonical.com>
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
This module implements functions necessary to load metabox configs.
"""
import importlib.util
import subprocess
from pathlib import Path

from loguru import logger


def read_config(filename):
    """
    Parse a config file from the path `filename` and yield
    a configuration object or raise SystemExit on problems.
    """

    try:
        mod_spec = importlib.util.spec_from_file_location(
            'config_file', filename)
        module = importlib.util.module_from_spec(mod_spec)
        mod_spec.loader.exec_module(module)
        config = module.configuration
        return config
    except (AttributeError, SyntaxError, FileNotFoundError) as exc:
        logger.critical(exc)
        raise SystemExit()


def validate_config(config):
    """
    Run a sanity check validation of the config.
    Raises SystemExit when a problem is found.
    """
    if not _has_local_or_remote_declaration(config):
        logger.critical(
            "Configuration has to define at least one way of running checkbox."
            "Define 'local' or 'service' and 'remote'.")
        raise SystemExit()
    for kind in config:
        if kind not in ('local', 'service', 'remote'):
            logger.critical(
                "Configuration has to define at least one way "
                "of running checkbox."
                "Define 'local' or 'service' and 'remote'.")
            raise SystemExit()
        for decl in config[kind]:
            if not _decl_has_a_valid_origin(config[kind]):
                logger.critical(
                    "Missing or invalid origin for the {} "
                    "declaration in config!", kind)
                raise SystemExit()


def _has_local_or_remote_declaration(config):
    """
    >>> config = {'local': 'something'}
    >>> _has_local_or_remote_declaration(config)
    True
    >>> config = {'local': ['something_else']}
    >>> _has_local_or_remote_declaration(config)
    True
    >>> config = {'local': []}
    >>> _has_local_or_remote_declaration(config)
    False
    >>> config = {'service': 'something'}
    >>> _has_local_or_remote_declaration(config)
    False
    >>> config = {'remote': 'something'}
    >>> _has_local_or_remote_declaration(config)
    False
    >>> config = {'remote': 'something', 'service': 'somethig_else'}
    >>> _has_local_or_remote_declaration(config)
    True
    """

    return bool(config.get('local') or (
        config.get('service') and config.get('remote')))


def _decl_has_a_valid_origin(decl):
    """
    >>> decl = {'origin': 'ppa'}
    >>> _decl_has_a_valid_origin(decl)
    True
    >>> decl = {'origin': 'source'}
    >>> _decl_has_a_valid_origin(decl)
    True
    >>> decl = {'origin': 'snap'}
    >>> _decl_has_a_valid_origin(decl)
    True
    >>> decl = {'origin': 'flatpak'}
    >>> _decl_has_a_valid_origin(decl)
    False
    >>> decl = {}
    >>> _decl_has_a_valid_origin(decl)
    False
    """
    if 'origin' not in decl:
        return False
    if decl['origin'] == 'snap':
        return True
    elif decl['origin'] == 'classic-snap':
        return True
    elif decl['origin'] == 'ppa':
        return True
    elif decl['origin'] == 'source':
        source = Path(decl['uri']).expanduser()
        if not source.is_dir():
            logger.error("{} doesn't look like a directory", source)
            return False
        setup_file = source / 'setup.py'
        if not setup_file.exists():
            logger.error("{} not found", setup_file)
            return False
        try:
            package_name = subprocess.check_output(
                [setup_file, '--name'],
                stderr=subprocess.DEVNULL).decode('utf-8').rstrip()
        except subprocess.CalledProcessError:
            logger.error("{} --name failed", setup_file)
            return False
        if not package_name == 'checkbox-ng':
            logger.error("{} must be a lp:checkbox-ng fork", source)
            return False
        return True
    return False
