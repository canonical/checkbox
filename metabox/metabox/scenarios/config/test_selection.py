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
from metabox.core.actions import AssertNotPrinted
from metabox.core.actions import Expect
from metabox.core.actions import Start
from metabox.core.actions import Put
from metabox.core.scenario import Scenario

from .config_files import test_selection


class TestSelectionDefault(Scenario):
    """
    Check that by default, the list of tests to run is displayed.
    """
    launcher = textwrap.dedent("""
        [launcher]
        launcher_version = 1
        stock_reports = text
        [test plan]
        unit = com.canonical.certification::smoke
        forced = yes
        """)
    steps = [
        Start(),
        Expect("Choose tests to run on your system:"),
    ]


class TestSelectionForced(Scenario):
    """
    If test selection is forced, Checkbox should start testing right away.
    """
    launcher = textwrap.dedent("""
        [launcher]
        launcher_version = 1
        stock_reports = text
        [test plan]
        unit = com.canonical.certification::smoke
        forced = yes
        [test selection]
        forced = yes
        """)
    steps = [
        Start(),
        # Jobs are started right away without test selection screen, e.g.
        # --------------[ Running job 1 / 20. Estimated time left: unknown ]--------------
        Expect("Running job"),
    ]


class TestSelectionExcludedJob(Scenario):
    """
    If some jobs are excluded from the launcher, they should not be run.
    """
    launcher = textwrap.dedent("""
        [launcher]
        launcher_version = 1
        stock_reports = text
        [test plan]
        unit = com.canonical.certification::config-automated
        forced = yes
        [test selection]
        forced = yes
        exclude = .*config-environ-source
        """)
    steps = [
        Start(),
        AssertNotPrinted(".*config-environ-source.*"),
    ]


class LocalTestSelectionResolution(Scenario):
    """
    According to Checkbox documentation, the resolution order is:

    1. launcher being invoked
    2. config file from ~/.config
    3. config file from /etc/xdg

    If a test is excluded from 2 and 3, but the exclusion list is cleaned in 1,
    the test should be run.

    This scenario tests this in local mode.
    """
    modes = ["local"]
    checkbox_conf_etc = read_text(test_selection, "checkbox_etc_xdg.conf")
    checkbox_conf_home = read_text(test_selection, "checkbox_home_dir.conf")
    launcher = textwrap.dedent("""
        [launcher]
        launcher_version = 1
        stock_reports = text
        [test plan]
        unit = com.canonical.certification::config-automated
        forced = yes
        [test selection]
        exclude =
        forced = yes
        """)
    steps = [
        Put("/home/ubuntu/.config/checkbox.conf", checkbox_conf_home),
        Put("/etc/xdg/checkbox.conf", checkbox_conf_etc),
        Start(),
        AssertPrinted(".*config-environ-source.*"),
    ]


class RemoteTestSelectionResolution(Scenario):
    """
    According to Checkbox documentation, the resolution order is:

    1. launcher being invoked
    2. config file from ~/.config
    3. config file from /etc/xdg

    If a test is excluded from 2 and 3, but the exclusion list is cleaned in 1,
    the test should be run.

    This scenario tests this in remote mode.
    """
    modes = ["remote"]
    checkbox_conf_etc = read_text(test_selection, "checkbox_etc_xdg.conf")
    checkbox_conf_home = read_text(test_selection, "checkbox_home_dir.conf")
    launcher = textwrap.dedent("""
        [launcher]
        launcher_version = 1
        stock_reports = text
        [test plan]
        unit = com.canonical.certification::config-automated
        forced = yes
        [test selection]
        exclude =
        forced = yes
        """)
    steps = [
        Put("/home/ubuntu/.config/checkbox.conf", checkbox_conf_home,
            target="service"),
        Put("/etc/xdg/checkbox.conf", checkbox_conf_etc,
            target="service"),
        Start(),
        AssertPrinted(".*config-environ-source.*"),
    ]
