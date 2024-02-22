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

from metabox.core.actions import AssertPrinted, AssertNotPrinted, Expect,\
        Start, Put, Send, MkTree
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
        #unit = 2021.com.canonical.certification::config-automated
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
        unit = 2021.com.canonical.certification::config-automated
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
        unit = 2021.com.canonical.certification::config-automated
        forced = yes
        [test selection]
        exclude =
        forced = yes
        """)
    steps = [
        MkTree("/home/ubuntu/.config"),
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
        unit = 2021.com.canonical.certification::config-automated
        forced = yes
        [test selection]
        exclude =
        forced = yes
        """)
    steps = [
        MkTree("/home/ubuntu/.config", target="agent"),
        Put("/home/ubuntu/.config/checkbox.conf", checkbox_conf_home,
            target="agent"),
        Put("/etc/xdg/checkbox.conf", checkbox_conf_etc,
            target="agent"),
        Start(),
        AssertPrinted(".*config-environ-source.*"),
    ]

class TestPlanSelectionSkip(Scenario):
    """
    If the launcher file lists a unit and forces the selection
    the test selection screen should be skipped and the unit
    should be selected automatically.

    This scenario has to work locally and remotely
    """
    # the conf file should be overwritten by the launcher,
    # if it is not, this will make the test fail intentionally
    checkbox_conf = read_text(
        test_selection, "checkbox_testplan_unit_forced.conf"
    )
    launcher = textwrap.dedent("""
        [launcher]
        launcher_version = 1
        stock_reports = text
        [test plan]
        unit = com.canonical.certification::smoke
        forced = yes
        """)
    steps = [
        MkTree("/home/ubuntu/.config", target="agent"),
        Put("/home/ubuntu/.config/checkbox.conf",
            checkbox_conf, target="agent"),
        Put("/etc/xdg/checkbox.conf", checkbox_conf,
            target = "agent"),
        Start(),
        # Assert that we have reached test selection
        Expect("Choose tests to run on your system")
    ]

class TestPlanPreselected(Scenario):
    """
    If the launcher selects a unit, it should be selected
    in the plan selection screen

    This scenario has to work locally and remotely
    """
    # the conf file should be overwritten by the launcher,
    # if it is not, this will make the test fail intentionally
    checkbox_conf = read_text(
        test_selection, "checkbox_testplan_unit_forced.conf"
    )
    launcher = textwrap.dedent("""
        [launcher]
        launcher_version = 1
        stock_reports = text
        [test plan]
        forced = no
        # filtering to avoid the test being out of bound
        filter = *smoke*
        unit = com.canonical.certification::smoke
        """)
    steps = [
        MkTree("/home/ubuntu/.config", target="agent"),
        Put("/home/ubuntu/.config/checkbox.conf",
            checkbox_conf, target="agent"),
        Put("/etc/xdg/checkbox.conf", checkbox_conf,
            target = "agent"),
        Start(),
        #( ) Some other test
        #(X) All Smoke Tests
        #( ) Some other test
        Expect("(X)")
    ]

class TestPlanSelectionPreselectFailWrongName(Scenario):
    """
    If a test with an unknown name is selected via unit
    checkbox should exit providing an error explaining
    that it did not find the test plan.
    """
    launcher = textwrap.dedent("""
        [launcher]
        launcher_version = 1
        stock_reports = text
        [test plan]
        # This name has to be wrong, if this is failing
        # this may be no longer the case
        unit = this_unit_does_not_exist
        # This forces to continue but nothing is selected
        forced = yes
        """)
    steps = [
        AssertPrinted(".*The test plan .+ is not available!.*")
    ]

class TestPlanSelectionPreselectNothing(Scenario):
    """
    If no unit is provided to checkbox, when prompted to continue
    or forced to do so in the test plan selection screen it should
    quit given that no test plan was selected.
    """
    launcher = textwrap.dedent("""
        [launcher]
        launcher_version = 1
        stock_reports = text
        [test plan]
        # This forces to continue but nothing is selected
        forced = yes
        """)
    steps = [
        AssertPrinted(".*The test plan selection was forced but no unit was provided")
    ]

class TestPlanSelectionFilterEmpty(Scenario):
    """
    If a filter excludes every test, checkbox should exit
    printing an error.
    """
    launcher = textwrap.dedent("""
        [launcher]
        launcher_version = 1
        stock_reports = text
        [test plan]
        # This should not match any valid test name (no word, no digit)
        filter = [^\w\d]
        """)
    steps = [
        Expect("There were no test plans to select from"),
    ]

class TestPlanSelectionFilter(Scenario):
    """
    Test plan selection should be filtered from the launcher
    """
    launcher = textwrap.dedent("""
        [launcher]
        launcher_version = 1
        stock_reports = text
        [test plan]
        filter = com.canonical.certification::[!s]*
    """)
    steps = [
        Send("i"),
        AssertNotPrinted("smoke")
    ]
