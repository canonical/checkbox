# This file is part of Checkbox.
#
# Copyright 2013 Canonical Ltd.
# Written by:
#   Zygmunt Krynicki <zygmunt.krynicki@canonical.com>
#
# Checkbox is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
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

import os
import itertools

from plainbox.impl.applogic import PlainBoxConfig


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
