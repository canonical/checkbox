#!/usr/bin/env python3
#
# This file is part of Checkbox.
#
# Copyright 2022 Canonical Ltd.
#
# Authors:
#     Abdullah (@motjuste) <abdullah.abdullah@canonical.com>
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
#
"""Verify test result from JUnit XML report"""

import argparse
import typing as t

import junitparser


def main(args: t.List[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description="Verify test result from JUnit XML report"
    )
    parser.add_argument("path", type=str, help="Path to JUnit XML report")
    parser.add_argument("test_case", type=str, help="Test case/classname")
    parser.add_argument("test_name", type=str, help="Test name")
    given = parser.parse_args(args)

    xml = junitparser.JUnitXml.fromfile(str(given.path))
    test_case = given.test_case.removesuffix(".py").replace("/", ".")
    test_name = given.test_name

    info = f"'{given.path}' : '{test_case}::{test_name}'"

    for suite in xml:
        for case in suite:
            if case.classname == test_case and case.name == test_name:
                if len(case.result) == 0:
                    print(f"{info}: PASSED")
                    return
                msg = f"{info}: FAILED"
                for failure in case.result:
                    msg = f"{failure.text}\n\n{msg}"
                raise AssertionError(msg)
    else:
        raise KeyError(f"{info}: NOT FOUND")


if __name__ == "__main__":  # pragma: no cover
    main()
