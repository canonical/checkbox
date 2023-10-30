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
import metabox.core.keys as keys
from metabox.core.actions import Expect
from metabox.core.actions import Send
from metabox.core.actions import Start
from metabox.core.scenario import Scenario
from metabox.core.utils import _re, tag


class ManualJobFailed(Scenario):
    """
    Run a test plan with a manual job with a certification-status set to
    "blocker" and make sure it can only be marked as failed if a comment is
    entered.
    """

    modes = ['local']
    launcher = textwrap.dedent("""
        [launcher]
        launcher_version = 1
        stock_reports = text
        [test plan]
        unit = 2021.com.canonical.certification::cert-blocker-manual
        forced = yes
        [test selection]
        forced = yes
        """)
    steps = [
        Start(),
        Expect('Pick an action'),
        Send('f' + keys.KEY_ENTER),
        Expect('Please add a comment to explain why it failed.', timeout=30),
        Send('c' + keys.KEY_ENTER),
        Expect('Please enter your comments:'),
        Send('This is a comment' + keys.KEY_ENTER),
        Expect('Pick an action'),
        Send('f' + keys.KEY_ENTER),
        Expect('Select jobs to re-run'),
        Send('f' + keys.KEY_ENTER),
        Expect(_re('(☒|job failed).*A simple manual job')),
    ]


class ManualJobSkipped(Scenario):
    """
    Run a test plan with a manual job with a certification-status set to
    "blocker" and make sure it can only be skipped if a comment is entered.
    """

    modes = ['local']
    launcher = textwrap.dedent("""
        [launcher]
        launcher_version = 1
        stock_reports = text
        [test plan]
        unit = 2021.com.canonical.certification::cert-blocker-manual
        forced = yes
        [test selection]
        forced = yes
        """)
    steps = [
        Start(),
        Expect('Pick an action'),
        Send('s' + keys.KEY_ENTER),
        Expect('Please add a comment to explain why you want to skip it.', timeout=30),
        Send('c' + keys.KEY_ENTER),
        Expect('Please enter your comments:'),
        Send('This is a comment' + keys.KEY_ENTER),
        Expect('Pick an action'),
        Send('s' + keys.KEY_ENTER),
        Expect('Select jobs to re-run'),
        Send('f' + keys.KEY_ENTER),
        Expect(_re('(☐|job skipped).*A simple manual job')),
    ]


class UserInteractVerifyJobFailed(Scenario):
    """
    Run a test plan with a user-interact-verify job with a certification-status
    set to "blocker" and make sure it can only be marked as failed if a comment
    is entered.
    """

    modes = ['local']
    launcher = textwrap.dedent("""
        [launcher]
        launcher_version = 1
        stock_reports = text
        [test plan]
        unit = 2021.com.canonical.certification::cert-blocker-user-interact-verify
        forced = yes
        [test selection]
        forced = yes
        """)
    steps = [
        Start(),
        Expect('Pick an action'),
        Send(keys.KEY_ENTER),
        Expect('job needs verification', timeout=30),
        Send('f' + keys.KEY_ENTER),
        Expect('Please add a comment to explain why it failed.', timeout=30),
        Send('c' + keys.KEY_ENTER),
        Expect('Please enter your comments:'),
        Send('This is a comment' + keys.KEY_ENTER),
        Expect('Pick an action'),
        Send('f' + keys.KEY_ENTER),
        Expect('Select jobs to re-run'),
        Send('f' + keys.KEY_ENTER),
        Expect(_re('(☒|job failed).*user interaction and verification job')),
    ]


class UserInteractVerifyJobSkippedAfterRun(Scenario):
    """
    Run a test plan with a user-interact-verify job with a certification-status
    set to "blocker" and make sure it can only be skipped if a comment is
    entered after actually running it.
    """

    modes = ['local']
    launcher = textwrap.dedent("""
        [launcher]
        launcher_version = 1
        stock_reports = text
        [test plan]
        unit = 2021.com.canonical.certification::cert-blocker-user-interact-verify
        forced = yes
        [test selection]
        forced = yes
        """)
    steps = [
        Start(),
        Expect('Pick an action'),
        Send(keys.KEY_ENTER),
        Expect('job needs verification', timeout=30),
        Send('s' + keys.KEY_ENTER),
        Expect('Please add a comment to explain why you want to skip it.', timeout=30),
        Send('c' + keys.KEY_ENTER),
        Expect('Please enter your comments:'),
        Send('This is a comment' + keys.KEY_ENTER),
        Expect('Pick an action'),
        Send('s' + keys.KEY_ENTER),
        Expect('Select jobs to re-run'),
        Send('f' + keys.KEY_ENTER),
        Expect(_re('(☐|job skipped).*user interaction and verification job')),
    ]


class UserInteractVerifyJobSkippedBeforeRun(Scenario):
    """
    Run a test plan with a user-interact-verify job with a certification-status
    set to "blocker" and make sure it can only be skipped if a comment is
    entered before actually running it.
    """

    modes = ['local']
    launcher = textwrap.dedent("""
        [launcher]
        launcher_version = 1
        stock_reports = text
        [test plan]
        unit = 2021.com.canonical.certification::cert-blocker-user-interact-verify
        forced = yes
        [test selection]
        forced = yes
        """)
    steps = [
        Start(),
        Expect('Pick an action'),
        Send('s' + keys.KEY_ENTER),
        Expect('Please add a comment to explain why you want to skip it.', timeout=30),
        Send('c' + keys.KEY_ENTER),
        Expect('Please enter your comments:'),
        Send('This is a comment' + keys.KEY_ENTER),
        Expect('Pick an action'),
        Send('s' + keys.KEY_ENTER),
        Expect('Select jobs to re-run'),
        Send('f' + keys.KEY_ENTER),
        Expect(_re('(☐|job skipped).*user interaction and verification job')),
    ]


class UserInteractJobSkippedBeforeRun(Scenario):
    """
    Run a test plan with a user-interact job with a certification-status set to
    "blocker" and make sure it can only be skipped if a comment is entered
    before actually running it.
    """

    modes = ['local']
    launcher = textwrap.dedent("""
        [launcher]
        launcher_version = 1
        stock_reports = text
        [test plan]
        unit = 2021.com.canonical.certification::cert-blocker-user-interact
        forced = yes
        [test selection]
        forced = yes
        """)
    steps = [
        Start(),
        Expect('Pick an action'),
        Send('s' + keys.KEY_ENTER),
        Expect('Please add a comment to explain why you want to skip it.', timeout=30),
        Send('c' + keys.KEY_ENTER),
        Expect('Please enter your comments:'),
        Send('This is a comment' + keys.KEY_ENTER),
        Expect('Pick an action'),
        Send('s' + keys.KEY_ENTER),
        Expect('Select jobs to re-run'),
        Send('f' + keys.KEY_ENTER),
        Expect(_re('(☐|job skipped).*User-interact job')),
    ]


@tag("resume")
class ManualJobSkippedWhenResumingSession(Scenario):
    """
    Run a test plan with a manual job set to cert-blocker. Save and quit the
    session, resume it and make sure it cannot be skipped until a comment is
    added.
    """

    modes = ["local"]
    launcher = textwrap.dedent(
        """
        [launcher]
        launcher_version = 1
        stock_reports = text
        [test plan]
        unit = 2021.com.canonical.certification::cert-blocker-manual-resume
        [test selection]
        forced = yes
        """
    )
    steps = [
        Start(),
        Expect("Select test plan"),
        Send(keys.KEY_ENTER),
        Expect("Pick an action"),
        Send("p" + keys.KEY_ENTER),
        Expect("save the session and quit"),
        Send("q" + keys.KEY_ENTER),
        Start(),
        Expect("(R) Resume session"),
        Send("r"),
        Expect("blocker-manual-resume"),
        Send(keys.KEY_ENTER),
        Send(keys.KEY_DOWN + keys.KEY_ENTER),
        Expect(
            "Please add a comment to explain why you want to skip it.",
            timeout=30,
        ),
        Expect("Please enter your comments:"),
        Send("This is a comment" + keys.KEY_ENTER),
        Expect("Pick an action"),
        Send(keys.KEY_ENTER),
        Expect("Select jobs to re-run"),
        Send("f" + keys.KEY_ENTER),
        Expect(_re("(☐|job skipped).*A simple manual job")),
    ]