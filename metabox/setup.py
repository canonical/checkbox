#!/usr/bin/env python3
# This file is part of Checkbox.
#
# Copyright 2021 Canonical Ltd.
# Written by:
#   Maciej Kisielewski <maciej.kisielewski@canonical.com>
#   Sylvain Pineau <sylvain.pineau@canonical.com>
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

from setuptools import find_packages, setup

setup(
    name="metabox",
    version="0.3",
    packages=find_packages(),
    install_requires=[
        "importlib-resources",
        "loguru",
        "pylxd",
        "pyyaml",
        "urllib3 >= 1.26.0, < 2.0.0",
    ],
    entry_points={
        "console_scripts": [
            "metabox = metabox.main:main",
        ]
    },
    include_package_data=True,
    package_data={
        "": ["metabox/metabox-provider/*"],
    },
)
