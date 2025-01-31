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
from metabox.core.actions import Expect, Send, Start, ExpectNot, Put, MkTree
from metabox.core.scenario import Scenario
from metabox.core.utils import tag


@tag("manual", "interact", "manifest")
class ManifestSelectionNoHiddenSetFalse(Scenario):
    launcher = textwrap.dedent(
        """
        [launcher]
        launcher_version = 1
        stock_reports = text
        [test plan]
        unit=2021.com.canonical.certification::hidden_manifest_testplan
        forced = yes
        """
    )
    machine_manifest = textwrap.dedent(
        """
        {
            "2021.com.canonical.certification::_hidden_manifest" : true
        }
        """
    )

    steps = [
        # put in the machine a manifest that sets the hidden_manifest. Given
        # that this is an interactive session, it must be ignored
        MkTree("/var/tmp/checkbox-ng"),
        Put("/var/tmp/checkbox-ng/machine-manifest.json", machine_manifest),
        Start(),
        Expect("Press (T) to start Testing"),
        Send("t"),
        Expect("System Manifest"),
        # contained in the hidden manifest name
        ExpectNot("Failure if shown", timeout=0.1),
        # contained in the shown manifest name
        Expect("non-hidden are shown"),
        Expect("Press (T) to start Testing"),
        Send("yt"),
        Expect("2021.com.canonical.certification::job_requires_hidden"),
        Expect("job cannot be started"),
        Expect("2021.com.canonical.certification::job_requires_not_hidden"),
        Expect("job passed"),
    ]


@tag("manual", "interact", "manifest")
class ManifestSelectionCanSetHiddenLauncher(Scenario):
    launcher = textwrap.dedent(
        """
        [launcher]
        launcher_version = 1
        stock_reports = text
        [test plan]
        unit=2021.com.canonical.certification::hidden_manifest_testplan
        forced = yes
        [manifest]
        2021.com.canonical.certification::_hidden_manifest=True
        """
    )
    machine_manifest = textwrap.dedent(
        """
        {
            "2021.com.canonical.certification::_hidden_manifest" : true
        }
        """
    )

    steps = [
        Start(),
        Expect("Press (T) to start Testing"),
        Send("t"),
        Expect("System Manifest"),
        # contained in the hidden manifest name
        ExpectNot("Failure if shown", timeout=0.1),
        # contained in the shown manifest name
        Expect("non-hidden are shown"),
        Expect("Press (T) to start Testing"),
        Send("yt"),
        Expect("2021.com.canonical.certification::job_requires_hidden"),
        Expect("job passed"),
        Expect("2021.com.canonical.certification::job_requires_not_hidden"),
        Expect("job cannot be started"),
    ]
