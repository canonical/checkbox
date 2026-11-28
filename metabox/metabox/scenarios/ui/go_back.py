# This file is part of Checkbox.
#
# Copyright 2026 Canonical Ltd.
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

from metabox.core import keys
from metabox.core.actions import Expect, ExpectNot, SelectTestPlan, Send
from metabox.core.scenario import Scenario
from metabox.core.utils import tag

TEST_PLAN = "2021.com.canonical.certification::hidden_manifest_testplan"


@tag("manual", "interact", "manifest", "goback")
class GoBackFromEveryScreen(Scenario):
    """
    Go back from the manifest to the test selection, then from the test
    selection to the test plan selection, and check that the previously
    selected test plan is kept and the session can still be run.
    """

    launcher = textwrap.dedent("""
        [launcher]
        launcher_version = 1
        stock_reports = text
        """)
    steps = [
        Expect("Select test plan"),
        SelectTestPlan(TEST_PLAN),
        Send(keys.KEY_ENTER),
        Expect("Choose tests to run on your system"),
        Expect("(B) to go"),
        Send("t"),
        Expect("System Manifest"),
        Expect("(B) to go"),
        # manifest -> test selection
        Send("b"),
        Expect("Choose tests to run on your system"),
        # test selection -> test plan selection
        Send("b"),
        Expect("Select test plan"),
        # the previously selected test plan is still selected, so Enter
        # goes straight to the test selection of that test plan
        Send(keys.KEY_ENTER),
        Expect("Choose tests to run on your system"),
        # Send("t"),
        # Expect("System Manifest"),
        # Send("yt"),
        # Expect("2021.com.canonical.certification::job_requires_not_hidden"),
        # Expect("job passed"),
    ]


@tag("manual", "interact", "manifest", "goback")
class GoBackFromManifestKeepsTestSelection(Scenario):
    """
    Deselect a job, go back from the manifest to the test selection and
    check that the job stays deselected when the session is run.
    """

    launcher = textwrap.dedent(f"""
        [launcher]
        launcher_version = 1
        stock_reports = text
        [test plan]
        unit={TEST_PLAN}
        forced = yes
        """)
    steps = [
        Expect("Choose tests to run on your system"),
        # expand the category and deselect its first job
        # (job_requires_hidden)
        Send(keys.KEY_ENTER),
        Send(keys.KEY_DOWN),
        Send(keys.KEY_SPACE),
        Send("t"),
        Expect("System Manifest"),
        Send("b"),
        Expect("Choose tests to run on your system"),
        Send("t"),
        Expect("System Manifest"),
        Send("yt"),
        Expect("2021.com.canonical.certification::job_requires_not_hidden"),
        Expect("job passed"),
        ExpectNot("2021.com.canonical.certification::job_requires_hidden"),
    ]


@tag("manual", "interact", "goback")
class GoBackFromTestSelectionToTestPlan(Scenario):
    """
    Go back from the test selection to the test plan selection and make sure
    the same test plan is selected
    """

    launcher = textwrap.dedent("""
        [launcher]
        launcher_version = 1
        stock_reports = text
        """)
    steps = [
        Expect("Select test plan"),
        SelectTestPlan(TEST_PLAN),
        Send(keys.KEY_ENTER),
        Expect("Choose tests to run on your system"),
        Send("b"),
        Expect("Select test plan"),
        Send("/"),
        Send("hidden_manifest"),
        Send(keys.KEY_ENTER),
        Send("i"),
        Expect(f"(X) {TEST_PLAN}"),
    ]
