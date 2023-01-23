# This file is part of Checkbox.
#
# Copyright 2023 Canonical Ltd.
# Written by:
#   Pierre Equoy <pierre.equoy@canonical.com>
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
import textwrap
from importlib.resources import read_text

from metabox.core.actions import AssertPrinted
from metabox.core.actions import Start
from metabox.core.actions import Put
from metabox.core.scenario import Scenario

from . import config_files


class CheckboxConfXDG(Scenario):
    """
    Check that environment variables are read from the XDG directory when
    nothing else is available.
    """
    checkbox_conf = read_text(config_files, "checkbox_etc_xdg.conf")
    steps = [
        Put("/etc/xdg/checkbox.conf", checkbox_conf),
        Start('run 2021.com.canonical.certification::config-automated',
              timeout=30),
        AssertPrinted("source: XDG"),
    ]


class CheckboxConfHome(Scenario):
    """
    Check that environment variables are read from the $HOME directory when
    nothing else is available.
    """
    checkbox_conf = read_text(config_files, "checkbox_home_dir.conf")
    steps = [
        Put("/home/ubuntu/.config/checkbox.conf", checkbox_conf),
        Start('run 2021.com.canonical.certification::config-automated',
              timeout=30),
        AssertPrinted("source: HOME"),
    ]


class CheckboxConfSnap(Scenario):
    """
    Check that environment variables are read from the $SNAP_DATA directory when
    nothing else is available.
    """
    origins = ["snap", "classic-snap"]
    checkbox_conf = read_text(config_files, "checkbox_snap_dir.conf")
    steps = [
        Put("/var/snap/checkbox/current/checkbox.conf", checkbox_conf),
        Start('run 2021.com.canonical.certification::config-automated',
              timeout=30),
        AssertPrinted("source: SNAP"),
    ]


class CheckboxConfLauncher(Scenario):
    """
    Check that environment variables are read from the launcher when nothing
    else is available.
    """
    launcher = textwrap.dedent("""
        [launcher]
        launcher_version = 1
        stock_reports = text
        [test plan]
        unit = 2021.com.canonical.certification::config-automated
        forced = yes
        [test selection]
        forced = yes
        [environment]
        source = LAUNCHER
        """)
    steps = [
        AssertPrinted("source: LAUNCHER"),
    ]


class CheckboxConfPrecedence(Scenario):
    checkbox_conf_xdg = read_text(config_files, "checkbox_etc_xdg.conf")
    checkbox_conf_home = read_text(config_files, "checkbox_home_dir.conf")
    steps = [
        Put("/etc/xdg/checkbox.conf", checkbox_conf_xdg),
        Put("/home/ubuntu/.config/checkbox.conf", checkbox_conf_home),
        Start('run 2021.com.canonical.certification::config-automated',
              timeout=30),
        AssertPrinted("source: HOME"),
    ]
