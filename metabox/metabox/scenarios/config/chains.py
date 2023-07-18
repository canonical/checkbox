# This file is part of Checkbox.
#
# Copyright 2023 Canonical Ltd.
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
import os
import textwrap
from importlib.resources import read_text

from metabox.core.actions import (
    AssertPrinted,
    AssertNotPrinted,
    Expect,
    Start,
    Put,
    Send,
    RunCmd
)
from metabox.core.scenario import Scenario
from metabox.core.utils import tag

from .config_files import chains


class ConfigChainsPriority(Scenario):
    etc_checkbox = read_text(chains, "etc_checkbox.conf")
    etc_checkbox_includes_includes = read_text(
        chains, "etc_checkbox_includes_includes.conf"
    )
    home_checkbox_includes = read_text(chains, "home_checkbox_includes.conf")
    etc_checkbox_includes = read_text(chains, "etc_checkbox_includes.conf")
    home_checkbox = read_text(chains, "home_checkbox.conf")
    modes = ['local']
    steps = [
        Put("/etc/xdg/checkbox.conf", etc_checkbox),
        Put("/etc/xdg/includes.conf", etc_checkbox_includes),
        Put("/etc/xdg/includes_includes.conf", etc_checkbox_includes_includes),
        RunCmd("mkdir -p /home/ubuntu/.config"),
        Put("/home/ubuntu/.config/checkbox.conf", home_checkbox),
        Put("/home/ubuntu/.config/includes.conf", home_checkbox_includes),
        Start(cmd="check-config"),
        AssertPrinted("a=0"),
        AssertPrinted("b=0"),
        AssertPrinted("c=0"),
        AssertPrinted("d=0"),
        AssertPrinted("e=0"),
    ]
