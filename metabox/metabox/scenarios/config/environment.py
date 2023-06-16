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

from metabox.core.scenario import Scenario
from metabox.core.actions import AssertPrinted, Start, MkTree, Put

from .config_files import environment


class CheckboxConfEnvvarCaseSensitive(Scenario):
    """
    Check that environment variables are case sensitive
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
        CASE = CASE
        Case = Case
        case = case
        """)
    steps = [
        AssertPrinted("CASE"),
        AssertPrinted("Case"),
        AssertPrinted("case"),
    ]


class CheckboxConfXDG(Scenario):
    """
    Check that environment variables are read from the XDG directory when
    nothing else is available.
    """
    checkbox_conf = read_text(environment, "checkbox_etc_xdg.conf")
    launcher = textwrap.dedent("""
        [launcher]
        launcher_version = 1
        stock_reports = text
        [test plan]
        unit = 2021.com.canonical.certification::config-automated
        forced = yes
        [test selection]
        forced = yes
        """)
    steps = [
        Put("/etc/xdg/checkbox.conf", checkbox_conf),
        Start(),
        AssertPrinted("source: XDG"),
    ]


class CheckboxConfLocalHome(Scenario):
    """
    Check that environment variables are read from the $HOME directory when
    nothing else is available.
    """
    modes = ["local"]
    checkbox_conf = read_text(environment, "checkbox_home_dir.conf")
    launcher = textwrap.dedent("""
        [launcher]
        launcher_version = 1
        stock_reports = text
        [test plan]
        unit = 2021.com.canonical.certification::config-automated
        forced = yes
        [test selection]
        forced = yes
        """)
    steps = [
        MkTree("/home/ubuntu/.config/"),
        Put("/home/ubuntu/.config/checkbox.conf", checkbox_conf),
        Start(),
        AssertPrinted("source: HOME"),
    ]


class CheckboxConfRemoteHome(Scenario):
    """
    Check that environment variables are read from the $HOME directory when
    nothing else is available.
    """
    modes = ["remote"]
    checkbox_conf = read_text(environment, "checkbox_home_dir.conf")
    launcher = textwrap.dedent("""
        [launcher]
        launcher_version = 1
        stock_reports = text
        [test plan]
        unit = 2021.com.canonical.certification::config-automated
        forced = yes
        [test selection]
        forced = yes
        """)
    steps = [
        MkTree("/root/.config/", privileged=True),
        Put("/root/.config/checkbox.conf", checkbox_conf),
        Start(),
        AssertPrinted("source: HOME"),
    ]


class CheckboxConfSnap(Scenario):
    """
    Check that environment variables are read from the $SNAP_DATA directory when
    nothing else is available.
    """
    origins = ["snap", "classic-snap"]
    checkbox_conf = read_text(environment, "checkbox_snap_dir.conf")
    launcher = textwrap.dedent("""
        [launcher]
        launcher_version = 1
        stock_reports = text
        [test plan]
        unit = 2021.com.canonical.certification::config-automated
        forced = yes
        [test selection]
        forced = yes
        """)
    steps = [
        MkTree("/var/snap/checkbox/current/"),
        Put("/var/snap/checkbox/current/checkbox.conf", checkbox_conf),
        Start(),
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


class CheckboxConfLocalHomePrecedence(Scenario):
    """
    Check that the environment variables defined in the ~/.config/ directory
    take precedence over the ones defined in /etc/xdg/.
    """
    modes = ["local"]
    checkbox_conf_xdg = read_text(environment, "checkbox_etc_xdg.conf")
    checkbox_conf_home = read_text(environment, "checkbox_home_dir.conf")
    launcher = textwrap.dedent("""
        [launcher]
        launcher_version = 1
        stock_reports = text
        [test plan]
        unit = 2021.com.canonical.certification::config-automated
        forced = yes
        [test selection]
        forced = yes
        """)
    steps = [
        Put("/etc/xdg/checkbox.conf", checkbox_conf_xdg),
        MkTree("/home/ubuntu/.config/"),
        Put("/home/ubuntu/.config/checkbox.conf", checkbox_conf_home),
        Start(),
        AssertPrinted("source: HOME"),
    ]


class CheckboxConfLauncherPrecedence(Scenario):
    """
    Check that the environment variables defined in the launcher take precedence
    over the ones defined in /etc/xdg/.
    """
    modes = ["remote"]
    checkbox_conf_xdg = read_text(environment, "checkbox_etc_xdg.conf")
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
        source = REMOTE LAUNCHER
        """)
    steps = [
        Put("/etc/xdg/checkbox.conf", checkbox_conf_xdg),
        Start(),
        AssertPrinted("source: REMOTE LAUNCHER"),
    ]


class CheckboxConfLocalResolutionOrder(Scenario):
    """
    According to the documentation, resolution order should be:

    1. launcher being invoked
    2. config file from ``~/.config``
    3. config file from ``/etc/xdg``

    This scenario sets 3 environment variables in different config locations
    and checks the resolution order is as defined:

    var1 XDG HOME LAUNCHER
    var2 XDG HOME
    var3 XDG
    --------------------->
    """
    modes = ["local"]
    checkbox_conf_xdg = read_text(environment, "checkbox_etc_xdg.conf")
    checkbox_conf_home = read_text(environment, "checkbox_home_dir.conf")
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
        var1 = LAUNCHER
        """)
    steps = [
        Put("/etc/xdg/checkbox.conf", checkbox_conf_xdg),
        MkTree("/home/ubuntu/.config/"),
        Put("/home/ubuntu/.config/checkbox.conf", checkbox_conf_home),
        Start(),
        AssertPrinted("variables: LAUNCHER HOME XDG"),
    ]


class CheckboxConfRemoteAgentResolutionOrder(Scenario):
    """
    According to the documentation, when the Checkbox Remote starts, it looks
    for config files in the same places that local Checkbox session would look
    (on the Agent side). If the Remote uses a Launcher, then the values from
    that Launcher take precedence over the values from configs on the Agent
    side.

    This scenario sets 3 environment variables in different config locations
    and checks the resolution order is as defined.
    """
    modes = ["remote"]
    checkbox_conf_xdg = read_text(environment, "checkbox_etc_xdg.conf")
    checkbox_conf_home = read_text(environment, "checkbox_home_dir.conf")
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
        var2 = LAUNCHER
        """
    )
    steps = [
        Put("/etc/xdg/checkbox.conf", checkbox_conf_xdg, target="agent"),
        MkTree("/root/.config", privileged=True),
        Put(
            "/root/.config/checkbox.conf", checkbox_conf_home, target="agent"
        ),
        Start(),
        AssertPrinted("variables: HOME LAUNCHER XDG"),
    ]
