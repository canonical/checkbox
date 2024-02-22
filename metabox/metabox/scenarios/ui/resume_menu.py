# This file is part of Checkbox.
#
# Copyright 2024 Canonical Ltd.
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
# along with Checkbox. If not, see <http://www.gnu.org/licenses/>.
import textwrap

import metabox.core.keys as keys
from metabox.core.actions import Expect, Send, Start, SelectTestPlan
from metabox.core.scenario import Scenario
from metabox.core.utils import tag


@tag("manual", "resume")
class ResumeMenuMultipleDelete(Scenario):
    modes = ["remote"]
    launcher = textwrap.dedent(
        """
        [launcher]
        launcher_version = 1
        stock_reports = text
        [test selection]
        forced = yes
        """
    )

    steps = [
        # Generate 2 resume candidates
        Start(),
        Expect("Select test plan"),
        SelectTestPlan(
            "2021.com.canonical.certification::cert-blocker-manual-resume"
        ),
        Send(keys.KEY_ENTER),
        Expect("Pick an action"),
        Send("p" + keys.KEY_ENTER),
        Expect("Pick an action"),
        Send("q" + keys.KEY_ENTER),
        Expect("Session saved"),
        Start(),
        Expect("Select test plan"),
        SelectTestPlan(
            "2021.com.canonical.certification::cert-blocker-manual-resume"
        ),
        Send(keys.KEY_ENTER),
        Expect("Pick an action"),
        Send("p" + keys.KEY_ENTER),
        Expect("Pick an action"),
        Send("q" + keys.KEY_ENTER),
        Expect("Session saved"),
        Start(),
        Expect("Resume session"),
        # Enter the resume menu
        Send("r"),
        Expect("Incomplete sessions"),
        # Delete first
        Send("d"),
        # More session available, remain in the resume menun
        Expect("Incomplete sessions"),
        # Delete second
        Send("d"),
        # No more sessions available, go back to test plan selection
        Expect("Select test plan"),
        # Now we still have to be able to run test plans
        SelectTestPlan("2021.com.canonical.certification::whoami_as_user_tp "),
        Send(keys.KEY_ENTER),
        Expect("Results"),
    ]


@tag("manual", "resume")
class ResumeMenuMarkSkip(Scenario):
    modes = ["remote"]
    launcher = textwrap.dedent(
        """
        [launcher]
        launcher_version = 1
        stock_reports = text
        [test selection]
        forced = yes
        """
    )

    steps = [
        # Generate 1 resume candidates
        Start(),
        Expect("Select test plan"),
        SelectTestPlan(
            "2021.com.canonical.certification::cert-blocker-manual-resume"
        ),
        Send(keys.KEY_ENTER),
        Expect("Pick an action"),
        Send("p" + keys.KEY_ENTER),
        Expect("Pick an action"),
        Send("q" + keys.KEY_ENTER),
        Expect("Session saved"),
        Start(),
        Expect("Resume session"),
        # Enter the resume menu
        Send("r"),
        Expect("Incomplete sessions"),
        Send(keys.KEY_ENTER),
        Expect("last job?"),
        # select Skip
        Send(keys.KEY_DOWN * 1),
        Send(keys.KEY_ENTER),
        # Job is a cert blocker, it must ask for a comment
        Expect("Please enter your comments"),
        Send("Comment" + keys.KEY_ENTER),
        Expect("Skipped Jobs"),
        Expect("Finish"),
        Send("f"),
        Expect("Result"),
    ]


@tag("manual", "resume")
class ResumeMenuMarkFail(Scenario):
    modes = ["remote"]
    launcher = textwrap.dedent(
        """
        [launcher]
        launcher_version = 1
        stock_reports = text
        [test selection]
        forced = yes
        """
    )

    steps = [
        # Generate 1 resume candidates
        Start(),
        Expect("Select test plan"),
        SelectTestPlan(
            "2021.com.canonical.certification::cert-blocker-manual-resume"
        ),
        Send(keys.KEY_ENTER),
        Expect("Pick an action"),
        Send("p" + keys.KEY_ENTER),
        Expect("Pick an action"),
        Send("q" + keys.KEY_ENTER),
        Expect("Session saved"),
        Start(),
        Expect("Resume session"),
        # Enter the resume menu
        Send("r"),
        Expect("Incomplete sessions"),
        Send(keys.KEY_ENTER),
        Expect("last job?"),
        # select Skip
        Send(keys.KEY_DOWN),
        Send(keys.KEY_DOWN),
        Send(keys.KEY_DOWN),
        Send(keys.KEY_ENTER),
        # Job is a cert blocker, it must ask for a comment
        Expect("Please enter your comments"),
        Send("Comment" + keys.KEY_ENTER),
        # Now we still have to be able to run test plans
        Expect("Failed Jobs"),
        Expect("Finish"),
        Send("f"),
        Expect("Result"),
    ]

@tag("manual", "resume")
class ResumeMenuMarkPreCommentFail(Scenario):
    modes = ["remote"]
    launcher = textwrap.dedent(
        """
        [launcher]
        launcher_version = 1
        stock_reports = text
        [test selection]
        forced = yes
        """
    )

    steps = [
        # Generate 1 resume candidates
        Start(),
        Expect("Select test plan"),
        SelectTestPlan(
            "2021.com.canonical.certification::cert-blocker-manual-resume"
        ),
        Send(keys.KEY_ENTER),
        Expect("Pick an action"),
        Send("p" + keys.KEY_ENTER),
        Expect("Pick an action"),
        Send("q" + keys.KEY_ENTER),
        Expect("Session saved"),
        Start(),
        Expect("Resume session"),
        # Enter the resume menu
        Send("r"),
        Expect("Incomplete sessions"),
        Send(keys.KEY_ENTER),
        Expect("last job?"),
        # select Comment
        Send(keys.KEY_ENTER),
        Expect("Enter comment"),
        Send("Job failed due to reason" + keys.KEY_ENTER),
        # select Skip
        Send("f"),
        # Job is a cert blocker, but it should not ask for a comment as it was
        # provided from the resume menu
        Expect("Failed Jobs"),
        Expect("Finish"),
        Send("f"),
        Expect("Result"),
    ]

@tag("manual", "resume")
class ResumeMenuMarkPassed(Scenario):
    modes = ["remote"]
    launcher = textwrap.dedent(
        """
        [launcher]
        launcher_version = 1
        stock_reports = text
        [test selection]
        forced = yes
        """
    )

    steps = [
        # Generate 1 resume candidates
        Start(),
        Expect("Select test plan"),
        SelectTestPlan(
            "2021.com.canonical.certification::cert-blocker-manual-resume"
        ),
        Send(keys.KEY_ENTER),
        Expect("Pick an action"),
        Send("p" + keys.KEY_ENTER),
        Expect("Pick an action"),
        Send("q" + keys.KEY_ENTER),
        Expect("Session saved"),
        Start(),
        Expect("Resume session"),
        # Enter the resume menu
        Send("r"),
        Expect("Incomplete sessions"),
        Send(keys.KEY_ENTER),
        Expect("last job?"),
        # Select Mark as Pass
        Send("p"),
        Expect("Result"),
    ]

@tag("manual", "resume")
class ResumeMenuResumeLastJob(Scenario):
    modes = ["remote"]
    launcher = textwrap.dedent(
        """
        [launcher]
        launcher_version = 1
        stock_reports = text
        [test selection]
        forced = yes
        """
    )

    steps = [
        # Generate 1 resume candidates
        Start(),
        Expect("Select test plan"),
        SelectTestPlan(
            "2021.com.canonical.certification::cert-blocker-manual-resume"
        ),
        Send(keys.KEY_ENTER),
        Expect("Pick an action"),
        Send("p" + keys.KEY_ENTER),
        Expect("Pick an action"),
        Send("q" + keys.KEY_ENTER),
        Expect("Session saved"),
        Start(),
        Expect("Resume session"),
        # Enter the resume menu
        Send("r"),
        Expect("Incomplete sessions"),
        Send(keys.KEY_ENTER),
        Expect("last job?"),
        # select Resume and run the job again
        Send("R"),
        Expect("press ENTER to continue"),
        Send(keys.KEY_ENTER),
        Expect("Result"),
    ]
