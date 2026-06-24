# This file is part of Checkbox.
#
# Copyright 2026 Canonical Ltd.
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
# along with Checkbox. If not, see <http://www.gnu.org/licenses/>.

import metabox.core.keys as keys
from metabox.core.actions import Expect, Send, Signal, Start, SelectTestPlan
from metabox.core.scenario import Scenario
from metabox.core.utils import tag


@tag("manual", "resume")
class RemainingTodoJobsLocal(Scenario):
    """
    Test that the remaining_todo_jobs metadata field is correctly displayed
    in the resume menu. When there are still jobs to run, it should show
    "Yes". When all jobs have been completed (only re-run screen remains),
    it should:
        - show "No"
        - resume directly into the re-run screen (instead of asking what to do
        with the last job)
    """

    modes = ["local"]

    steps = [
        # Step 1: Start session with bespoke test plan
        Start(),
        Expect("Select test plan"),
        SelectTestPlan(
            "2021.com.canonical.certification::basic-session-resume-manual"
        ),
        Send(keys.KEY_ENTER),
        Expect("Press (T) to start"),
        Send("t"),
        # Step 2: Wait for manual job
        Expect("Pick an action"),
        # Step 3: Stop the session with Ctrl-C
        Signal(keys.SIGINT),
        # Step 4: Restart and resume - should show "Yes" for remaining jobs
        Start(),
        Expect("Resume session"),
        Send("r"),
        Expect("Incomplete sessions"),
        Expect("Are there still jobs to run?"),
        Expect("Yes"),
        Send(keys.KEY_ENTER),
        Expect("last job?"),
        # Re-run the last job (smoke/manual)
        Send("r"),
        Expect("Pick an action"),
        # Step 5: Set the job to pass - re-run screen is shown
        Send("p" + keys.KEY_ENTER),
        Expect("Select jobs to re-run"),
        # Step 6: Stop the session again with Ctrl-C
        Signal(keys.SIGINT),
        # Resume again - should show "No" for remaining jobs
        Start(),
        Expect("Resume session"),
        Send("r"),
        Expect("Incomplete sessions"),
        Expect("Are there still jobs to run?"),
        Expect("No"),
        Send(keys.KEY_ENTER),
        # No action is shown, resumes directly in re-run screen
        Expect("Select jobs to re-run"),
    ]


@tag("manual", "resume")
class RemainingTodoJobsRemote(Scenario):
    """
    Test that the remaining_todo_jobs metadata field is correctly displayed
    in the resume menu. When there are still jobs to run, it should show
    "Yes". When all jobs have been completed (only re-run screen remains),
    it should:
        - show "No"
        - resume directly into the re-run screen (instead of asking what to do
        with the last job)
    """

    modes = ["remote"]
    launcher = "# no launcher"

    steps = [
        # Step 1: Start session with bespoke test plan
        Start(),
        Expect("Select test plan"),
        SelectTestPlan(
            "2021.com.canonical.certification::basic-session-resume-manual"
        ),
        Send(keys.KEY_ENTER),
        Expect("Press (T) to start"),
        Send("t"),
        # Step 2: Wait for manual job
        Start(),
        Expect("Pick an action"),
        # Step 3: Stop the session with Ctrl-C, then Exit and stop the agent
        Signal(keys.SIGINT),
        Expect("(X) Nothing"),
        Send(keys.KEY_DOWN * 3 + keys.KEY_SPACE + keys.KEY_ENTER),
        # Step 4: Restart and resume - should show "Yes" for remaining jobs
        Start(),
        Expect("Resume session"),
        Send("r"),
        Expect("Incomplete sessions"),
        Expect("Are there still jobs to run?"),
        Expect("Yes"),
        Send(keys.KEY_ENTER),
        Expect("last job?"),
        # Re-run the last job (smoke/manual)
        Send("r"),
        Expect("Pick an action"),
        # Step 5: Set the job to pass - re-run screen is shown
        Send("p" + keys.KEY_ENTER),
        Expect("Select jobs to re-run"),
        # Step 6: Stop the session again with Ctrl-C, then Exit and stop the
        # agent
        Signal(keys.SIGINT),
        Expect("(X) Nothing"),
        Send(keys.KEY_DOWN * 3 + keys.KEY_SPACE + keys.KEY_ENTER),
        # Step 7: Resume again - should show "No" for remaining jobs
        Start(),
        Expect("Resume session"),
        Send("r"),
        Expect("Incomplete sessions"),
        Expect("Are there still jobs to run?"),
        Expect("No"),
        Send(keys.KEY_ENTER),
        # No action is shown, resumes directly in re-run screen
        Expect("Select jobs to re-run"),
    ]
