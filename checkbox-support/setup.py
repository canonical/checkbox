#!/usr/bin/env python3
# This file is part of Checkbox.
#
# Copyright 2014 Canonical Ltd.
# Written by:
#   Sylvain Pineau <sylvain.pineau@canonical.com>
#
# CloudBox is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# CloudBox is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with CloudBox.  If not, see <http://www.gnu.org/licenses/>.

import os
import sys

from setuptools import setup, find_packages

if "test" in sys.argv:
    # Reset locale for setup.py test
    os.environ["LANG"] = ""
    os.environ["LANGUAGE"] = ""
    os.environ["LC_ALL"] = "C.UTF-8"

base_dir = os.path.dirname(__file__)

# Load the README.rst file relative to the setup file
with open(os.path.join(base_dir, "README.rst"), encoding="UTF-8") as stream:
    long_description = stream.read()

setup(
    name="checkbox-support",
    version="0.4c1",
    url="https://launchpad.net/checkbox/",
    packages=find_packages(),
    test_suite='checkbox_support.tests.test_suite',
    author="Sylvain Pineau",
    author_email="sylvain.pineau@canonical.com",
    license="GPLv3",
    description="CheckBox support library",
    long_description=long_description,
    install_requires=[
        'lxml >= 2.3',
        'pyparsing >= 2.0.0',
    ] + (['configparser'] if sys.version_info.major == 2 else []),
    entry_points={
        'plainbox.parsers': [
            "pactl-list=checkbox_support.parsers.pactl:parse_pactl_output",
            "submission=checkbox_support.parsers.submission:parse_submission_text",
            "udevadm=checkbox_support.parsers.udevadm:parse_udevadm_output",
        ],
    },
)
