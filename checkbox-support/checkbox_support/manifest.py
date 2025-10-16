"""
Support interfaces related manifest.json

Copyright (C) 2025 Canonical Ltd.

Authors: Massimiliano Girardi <massimiliano.girardi@canonical.com>

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License version 3,
as published by the Free Software Foundation.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <http://www.gnu.org/licenses/>.
"""

import json
from contextlib import suppress
from collections import defaultdict


def get_manifest() -> defaultdict:
    to_r = defaultdict(bool)
    with suppress(FileNotFoundError):
        with open("/var/tmp/checkbox-ng/machine-manifest.json") as f:
            to_r.update(json.load(f))
    return to_r
