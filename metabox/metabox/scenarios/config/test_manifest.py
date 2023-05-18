# This file is part of Checkbox.
#
# Copyright 2023 Canonical Ltd.
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
import os
import textwrap
from importlib.resources import read_text

from metabox.core.actions import (
    AssertPrinted,
    AssertNotPrinted,
    Expect,
    Start,
    Put,
    Send,
    RunCmd,
)
from metabox.core.scenario import Scenario

from .config_files import test_manifest

MANIFEST_CACHE_LOCATION = "/var/tmp/checkbox-ng/machine-manifest.json"
MANIFEST_DISK_LOCATION = "/home/ubuntu/.local/share/plainbox/machine-manifest.json"

conf_wrong = read_text(test_manifest, "wrong.json")

class ManifestLauncherAuto(Scenario):
    """
    When provided with a manifest in the launcher
    checkbox reads it correctly regardless if
    tests selection was skipped or not
    """

    launcher = textwrap.dedent("""
        [launcher]
        launcher_version = 1
        [test plan]
        # filtering to avoid the test being out of bound
        unit = 2021.com.canonical.certification::manifest_test_support
        forced = yes
        [test selection]
        forced = yes
        [manifest]
        2021.com.canonical.certification::manifest_location = 0
    """)

    steps = [AssertPrinted(".*Outcome: job passed.*")]


class ManifestLauncherManual(Scenario):
    """
    When provided with a manifest in the launcher
    checkbox reads it correctly regardless if
    tests selection was skipped or not
    """

    launcher = textwrap.dedent("""
        [launcher]
        launcher_version = 1
        [test plan]
        # filtering to avoid the test being out of bound
        forced = yes
        unit = 2021.com.canonical.certification::manifest_test_support
        [manifest]
        2021.com.canonical.certification::manifest_location = 0
    """)

    steps = [
        Expect("testing with metabox"),
        Send("T"),
        Expect("Location where the manifest"),
        Send("T"),
        Expect("Outcome: job passed"),
    ]


class ManifestConfigCacheAuto(Scenario):
    """
    The manifest value is correctly loaded from
    the cache in manual tests
    """

    conf_correct = read_text(test_manifest, "correct.json")

    launcher = textwrap.dedent("""
        [launcher]
        launcher_version = 1
        [test plan]
        # filtering to avoid the test being out of bound
        unit = 2021.com.canonical.certification::manifest_test_support
        forced = yes
        [test selection]
        forced = yes
    """)

    steps = [
        Put(MANIFEST_CACHE_LOCATION, conf_correct),
        Start(),
        AssertPrinted(".*Outcome: job passed.*"),
    ]


class ManifestConfigCacheManual(Scenario):
    """
    The manifest value is correctly loaded from
    the cache in auto tests
    """

    conf_correct = read_text(test_manifest, "correct.json")

    launcher = textwrap.dedent("""
        [launcher]
        launcher_version = 1
        [test plan]
        # filtering to avoid the test being out of bound
        forced = yes
        unit = 2021.com.canonical.certification::manifest_test_support
    """)

    steps = [
        Put(MANIFEST_CACHE_LOCATION, conf_correct),
        Start(),
        Expect("testing with metabox"),
        Send("T"),
        Expect("Location where the manifest"),
        Send("T"),
        Expect("Outcome: job passed"),
    ]


class ManifestConfigDiskAuto(Scenario):
    """
    The manifest value is correctly loaded from
    the documented disk location in auto test runs
    """

    conf_correct = read_text(test_manifest, "correct.json")

    launcher = textwrap.dedent("""
        [launcher]
        launcher_version = 1
        [test plan]
        # filtering to avoid the test being out of bound
        unit = 2021.com.canonical.certification::manifest_test_support
        forced = yes
        [test selection]
        forced = yes
    """)

    steps = [
        RunCmd("mkdir {}".format(os.path.dirname(MANIFEST_DISK_LOCATION))),
        Put(MANIFEST_DISK_LOCATION, conf_correct),
        Start(),
        AssertPrinted(".*Outcome: job passed.*"),
    ]


class ManifestConfigDiskManual(Scenario):
    """
    The manifest value is correctly loaded from
    the documented disk location in manual test runs
    """

    conf_correct = read_text(test_manifest, "correct.json")

    launcher = textwrap.dedent("""
        [launcher]
        launcher_version = 1
        [test plan]
        # filtering to avoid the test being out of bound
        forced = yes
        unit = 2021.com.canonical.certification::manifest_test_support
    """)

    steps = [
        RunCmd("mkdir {}".format(os.path.dirname(MANIFEST_DISK_LOCATION))),
        Put(MANIFEST_DISK_LOCATION, conf_correct),
        Start(),
        Expect("testing with metabox"),
        Send("T"),
        Expect("Location where the manifest"),
        Send("T"),
        Expect("Outcome: job passed"),
    ]
