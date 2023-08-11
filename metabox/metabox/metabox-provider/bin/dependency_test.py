#!/usr/bin/env python3
# Copyright (C) 2023 Canonical Ltd.
#
# Authors:
#   Massimiliano Girardi <massimiliano.girardi@canonical.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License version 3,
# as published by the Free Software Foundation.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.


"""
This module imports all dependencies of checkbox-ng and checkbox-support.
This allows us to verify that all dependencies are actually installed by
the install process, without this modules checkbox does not work!

If you have updated the dependency list of the following, update this test
as well:
- checkbox-ng/pyproject.toml
- checkbox-support/pyproject.toml
"""

# Core checkbox module
import checkbox_ng

# checkbox-ng dependencies
import packaging
import psutil
import requests
import urwid
import jinja2
import xlsxwriter
import tqdm

try:
    import importlib_metadata
except ModuleNotFoundError:
    import importlib.metadata

# Used by checkbox and providers
import plainbox

# Contains various help functions/scripts
import checkbox_support

# checkbox-support dependencies
import pyparsing
import requests
import distro
import requests
import requests_unixsocket

try:
    import importlib_metadata
except ModuleNotFoundError:
    import importlib.metadata
