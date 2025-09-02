# This file is part of Checkbox.
#
# Copyright 2025 Canonical Ltd.
# Written by:
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

import textwrap

from metabox.core.actions import Expect, ExpectNot, Start, Send
from metabox.core.scenario import Scenario
from metabox.core.utils import tag, _re
from metabox.core import keys


@tag("setup_include")
class SetupIncludeBasicManual(Scenario):
    launcher = textwrap.dedent(
        """
        [launcher]
        stock_reports = text
        [test plan]
        unit = 2021.com.canonical.certification::basic_setup_include_works
        """
    )
    steps = [
        Start(),
        Expect("Press <Enter> to continue"),
        Send(keys.KEY_ENTER),
        Expect("simple_setup_guard"),
        Expect("simple_bootstrap_guard"),
        Expect("Press (T) to start Testing"),
        Send("t"),
        Expect("verify_simple_guards"),
        Expect("job passed"),
        # Note: the "guards" will catch if setup jobs or bootstrap jobs didn't
        #       run
    ]


@tag("setup_include")
class SetupIncludeBasicAutomated(Scenario):
    launcher = textwrap.dedent(
        """
        [launcher]
        stock_reports = text
        [test plan]
        unit = 2021.com.canonical.certification::basic_setup_include_works
        forced = yes
        [test selection]
        forced = yes
        [ui]
        type = silent
        """
    )
    steps = [
        Start(),
        Expect("simple_setup_guard"),
        Expect("job passed"),
        Expect("verify_simple_guards"),
        Expect("job passed"),
        # Note: the "guards" will catch if setup jobs or bootstrap jobs didn't
        #       run
    ]


@tag("setup_include")
class SetupIncludeResumeAutomated(Scenario):
    launcher = textwrap.dedent(
        """
        [launcher]
        stock_reports = text
        [test plan]
        unit = 2021.com.canonical.certification::resume_setup_include_works
        forced = yes
        [test selection]
        forced = yes
        """
    )
    steps = [
        Start(),
        Expect("simple_setup_guard"),
        Expect("job passed"),
        ExpectNot("setup_restart_guard"),
        # simple_restart is noreturn, trying to catch its output will fail
        # most times because it is a race between it killing checkbox and the
        # expect
        Start(),
        Expect("setup_restart_guard"),
        Expect("job passed"),
        Expect("verify_simple_guards"),
        Expect("job passed"),
        Expect("verify_resume_guards"),
        Expect("job passed"),
        # Note: the "guards" will catch if setup jobs or bootstrap jobs didn't
        #       run
    ]
