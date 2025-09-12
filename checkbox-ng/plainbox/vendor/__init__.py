# This file is part of Checkbox.
#
# Copyright 2024 Canonical Ltd.
# Written by:
#   Zygmunt Krynicki <zygmunt.krynicki@canonical.com>
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
# along with Checkbox.  If not, see <http://www.gnu.org/licenses/>.

"""
:mod:`plainbox.vendor` -- vendorized packages
=============================================

This module contains external packages that were vendorized (shipped with a
tree of another project) to simplify dependency management. These may
be modules that have to be modified to be compatible with an old python
version or tools that we need but don't want to package for every
redistribution avenue that we currently use.
"""

from pathlib import Path

INXI_PATH = (Path(__file__).parent / "inxi").resolve()
IMAGE_INFO = (Path(__file__).parent / "image_info.py").resolve()
