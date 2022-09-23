# This file is part of Checkbox.
#
# Copyright 2018 Canonical Ltd.
# Written by:
#   Maciej Kisielewski <maciej.kisielewski@canonical.com>
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

import gettext
import logging
import os

from collections import OrderedDict

from plainbox.impl.providers import get_providers

import checkbox_ng

_ = gettext.gettext
_logger = logging.getLogger("checkbox-ng.launcher.subcommands")


def get_version_info():
    info = OrderedDict()
    if os.environ.get("SNAP"):
        return get_parts_info()
    else:
        return get_stack_version()


def get_stack_version():
    """
    Generate version information of Checkbox stack components as understood
    by Checkbox.
    """
    info = OrderedDict()
    info['checkbox-ng'] = checkbox_ng.__version__
    try:
        import checkbox_support
        support_ver = checkbox_support.__version__
    except AttributeError:
        import pkg_resources
        support_ver = pkg_resources.get_distribution(
            "checkbox-support").version
    except ModuleNotFoundError:
        support_ver = 'not available'
    info['checkbox-support'] = support_ver
    ignored_providers = [
        'com.canonical.plainbox:manifest',
        'com.canonical.plainbox:exporters',
        'com.canonical.plainbox:categories',
    ]
    # maybe filter-out the built-in providers (exporters, categories, etc.)
    for provider in get_providers():
        if provider.name not in ignored_providers:
            info[provider.name] = provider.version
    return info


def get_parts_info():
    """
    Generate information about the revisions of all the parts that were used
    to build the snap Checkbox is running from.
    """
    info = OrderedDict()
    parts_info_path = os.path.join(
        os.path.expandvars("$SNAP"), 'parts_meta_info')
    if not os.path.exists(parts_info_path):
        _logger.warning(_('Missing parts_meta_info file.'))
        return info
    with open(parts_info_path, 'rt') as f:
        content = f.read().splitlines()
    while(len(content) >= 4):
        part_name = content[0]
        # trim trailing ':'
        part_name = part_name[:-1]
        commit = content[1].split(' ')[0]
        content = content[4:]
        info[part_name] = commit
    if len(content) > 0:
        # XXX: soft-assert here that nothing's left to read
        _logger.warning(_('Found trailing data in parts_meta_info.'))
    return info
