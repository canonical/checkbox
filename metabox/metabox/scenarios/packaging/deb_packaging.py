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

from importlib.resources import read_text

from metabox.core.scenario import Scenario
from metabox.core.actions import (
    AssertRetCode,
    Start,
    Put,
    AssertPrinted,
    RunManage,
    AssertInFile,
    RunCmd,
)
from metabox.core.utils import tag
from . import units

provider_path = "/home/ubuntu/checkbox/metabox/metabox/metabox-provider"
packaging_pxu_path = f"{provider_path}/units/packaging.pxu"
substvar_path = f"{provider_path}/debian/metabox-provider.substvars"


@tag("packaging")
class DebPackagingJammy(Scenario):
    """
    Verifies that the deb-packaging test pass on jammy (22.04).
    """

    modes = ["local"]
    start_session = False
    config_override = {"local": {"releases": ["jammy"]}}
    packaging_pxu = read_text(units, "packaging.pxu")

    steps = [
        Put(f"{provider_path}/units/packaging.pxu", packaging_pxu),
        RunManage(args="packaging"),
        AssertInFile("dep-pack-gt-20", substvar_path),
        AssertInFile("rec-pack-gt-20", substvar_path),
        AssertInFile("sug-pack-gt-20", substvar_path),
        RunCmd(f"rm -f {substvar_path}"),
    ]


@tag("packaging")
class DebPackagingFocal(Scenario):
    """
    Verifies that the deb-packaging test pass on focal (20.04).
    """

    modes = ["local"]
    start_session = False
    config_override = {"local": {"releases": ["focal"]}}
    packaging_pxu = read_text(units, "packaging.pxu")

    steps = [
        Put(f"{provider_path}/units/packaging.pxu", packaging_pxu),
        RunManage(args="packaging"),
        AssertInFile("dep-pack-le-20", substvar_path),
        AssertInFile("rec-pack-le-20", substvar_path),
        AssertInFile("sug-pack-le-20", substvar_path),
        RunCmd(f"rm -f {substvar_path}"),
    ]


@tag("packaging")
class DebPackagingBionic(Scenario):
    """
    Verifies that the deb-packaging test pass on bionic (18.04).
    """

    modes = ["local"]
    config_override = {"local": {"releases": ["bionic"]}}
    packaging_pxu = read_text(units, "packaging.pxu")

    steps = [
        Put(f"{provider_path}/units/packaging.pxu", packaging_pxu),
        RunManage(args="packaging"),
        AssertInFile("dep-pack-le-20", substvar_path),
        AssertInFile("rec-pack-le-20", substvar_path),
        AssertInFile("sug-pack-le-20", substvar_path),
        RunCmd(f"rm -f {substvar_path}"),
    ]
