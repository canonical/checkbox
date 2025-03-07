#!/usr/bin/env bash
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

# IMPORTANT NOTE:@motjuste:
#
#   This wrapper is needed to call `dss` with the Python env vars
#   from checkbox / snap removed from the shell, so that it uses
#   system's Python.
#
#   Furthermore, the working directory needs to be changed to, e.g.
#   /tmp, because `dss` writes logs out to the working directory,
#   and it won't have permission inside checkbox / snap directory.
set -eo pipefail

export -n PYTHONHOME PYTHONPATH PYTHONUSERBASE

env -C /tmp dss "$@"
