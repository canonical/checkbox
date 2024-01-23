#!/usr/bin/env python3
# Copyright (C) 2023 Canonical Ltd.
#
# Authors:
#   Fernando Bravo <fernando.bravo.hernandez@canonical.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License version 3,
# as published by the Free Software Foundation.
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

from pathlib import Path

from metabox.core.scenario import Scenario
from metabox.core.actions import (
    Put,
    RunManage,
    AssertInFile,
    RunCmd,
)
from metabox.core.utils import tag

provider_path = Path("/home/ubuntu/checkbox/metabox/metabox/metabox-provider")
packaging_pxu_path = provider_path / "units/packaging.pxu"
substvar_path = provider_path / "debian/metabox-provider.substvars"

pxu_path = Path(__file__).parent / "packaging.pxu"
with pxu_path.open("r") as file:
    packaging_pxu = file.read()


@tag("packaging")
class DebPackagingJammy(Scenario):
    """
    Verifies that the deb-packaging test pass on jammy (22.04).
    """

    modes = ["local"]
    # Run the scenario without starting a session.
    start_session = False
    config_override = {"local": {"releases": ["jammy"]}}
    steps = [
        Put(packaging_pxu_path, packaging_pxu),
        RunManage(args="packaging"),
        AssertInFile("dep-pack-gt-20", substvar_path),
        AssertInFile("rec-pack-gt-20", substvar_path),
        AssertInFile("sug-pack-gt-20", substvar_path),
    ]


@tag("packaging")
class DebPackagingFocal(Scenario):
    """
    Verifies that the deb-packaging test pass on focal (20.04).
    """

    modes = ["local"]
    start_session = False
    config_override = {"local": {"releases": ["focal"]}}
    steps = [
        Put(packaging_pxu_path, packaging_pxu),
        RunManage(args="packaging"),
        AssertInFile("dep-pack-le-20", substvar_path),
        AssertInFile("rec-pack-le-20", substvar_path),
        AssertInFile("sug-pack-le-20", substvar_path),
    ]


@tag("packaging")
class DebPackagingBionic(Scenario):
    """
    Verifies that the deb-packaging test pass on bionic (18.04).
    """

    modes = ["local"]
    config_override = {"local": {"releases": ["bionic"]}}
    steps = [
        Put(packaging_pxu_path, packaging_pxu),
        RunManage(args="packaging"),
        AssertInFile("dep-pack-le-20", substvar_path),
        AssertInFile("rec-pack-le-20", substvar_path),
        AssertInFile("sug-pack-le-20", substvar_path),
    ]
