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
    """
    Generate version information of Checkbox stack components as understood
    by Checkbox.
    """
    info = OrderedDict()
    info["checkbox-ng"] = checkbox_ng.__version__
    try:
        import checkbox_support

        support_ver = checkbox_support.__version__
    except AttributeError:
        import pkg_resources

        support_ver = pkg_resources.get_distribution("checkbox-support").version
    except ModuleNotFoundError:
        support_ver = "not available"
    info["checkbox-support"] = support_ver
    ignored_providers = [
        "com.canonical.plainbox:manifest",
        "com.canonical.plainbox:exporters",
        "com.canonical.plainbox:categories",
    ]
    # maybe filter-out the built-in providers (exporters, categories, etc.)
    for provider in get_providers():
        if provider.name not in ignored_providers:
            info[provider.name] = provider.version
    return info
