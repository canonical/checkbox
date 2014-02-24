#!/usr/bin/env python3
# This file is part of textland.
#
# Copyright 2014 Canonical Ltd.
# Written by:
#   Zygmunt Krynicki <zygmunt.krynicki@canonical.com>
#
# Textland is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License version 3,
# as published by the Free Software Foundation.
#
# Textland is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Textland.  If not, see <http://www.gnu.org/licenses/>.

import os

from setuptools import setup, find_packages

base_dir = os.path.dirname(__file__)

# Load the README.rst file relative to the setup file
with open(os.path.join(base_dir, "README.md"), encoding="UTF-8") as stream:
    long_description = stream.read()


setup(
    name="textland",
    version="0.1",
    url="https://github.com/zyga/textland",
    packages=find_packages(),
    author="Zygmunt Krynicki",
    author_email="zygmunt.krynicki@canonical.com",
    license="GPLv3",
    description="Like wayland, for text apps",
    long_description=long_description)
