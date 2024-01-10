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
)
from metabox.core.utils import tag
from . import units

path = "/home/ubuntu/checkbox/metabox/metabox/metabox-provider/units/packaging.pxu"


@tag("packaging")
class DebPackagingJammy(Scenario):
    """
    Verifies that the deb-packaging test pass on jammy (22.04).
    """

    modes = ["local"]
    config_override = {"local": {"releases": ["jammy"]}}
    packaging_pxu = read_text(units, "packaging.pxu")

    steps = [
        Put(path, packaging_pxu),
        RunManage(command="packaging"),
        AssertRetCode(0),
    ]


@tag("packaging")
class DebPackagingJammy2(Scenario):
    """
    Verifies that the deb-packaging test pass on jammy (22.04).
    """

    modes = ["local"]
    config_override = {"local": {"releases": ["jammy"]}}
    packaging_pxu = read_text(units, "packaging.pxu")

    steps = [
        Put(path, packaging_pxu),
        Start("run 2021.com.canonical.certification::deb-packaging"),
        AssertRetCode(0),
        AssertPrinted("dep-pack-gt-20"),
        AssertPrinted("rec-pack-gt-20"),
        AssertPrinted("sug-pack-gt-20"),
    ]


# @tag("packaging")
# class DebPackagingFocal(Scenario):
#     """
#     Verifies that the deb-packaging test pass on focal (20.04).
#     """

#     modes = ["local"]
#     config_override = {"local": {"releases": ["focal"]}}
#     packaging_pxu = read_text(units, "packaging.pxu")

#     steps = [
#         Put(path, packaging_pxu),
#         Start("run 2021.com.canonical.certification::deb-packaging"),
#         AssertRetCode(0),
#         AssertPrinted("dep-pack-le-20"),
#         AssertPrinted("rec-pack-le-20"),
#         AssertPrinted("sug-pack-le-20"),
#     ]


# @tag("packaging")
# class DebPackagingBionic(Scenario):
#     """
#     Verifies that the deb-packaging test pass on bionic (18.04).
#     """

#     modes = ["local"]
#     config_override = {"local": {"releases": ["bionic"]}}
#     packaging_pxu = read_text(units, "packaging.pxu")

#     steps = [
#         Put(path, packaging_pxu),
#         Start("run 2021.com.canonical.certification::deb-packaging"),
#         AssertRetCode(0),
#         AssertPrinted("dep-pack-le-20"),
#         AssertPrinted("rec-pack-le-20"),
#         AssertPrinted("sug-pack-le-20"),
#     ]
