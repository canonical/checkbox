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
import re
from typing import NamedTuple

__all__ = ("tag", "ExecuteResult")


def tag(*tags):
    """Decorator to add tags to a scenario class."""

    def decorator(obj):
        setattr(obj, "tags", set(tags))
        return obj

    return decorator


class ExecuteResult(NamedTuple):
    exit_code: int
    stdout: str
    stderr: str
    outstr_full: str


class _re:
    def __init__(self, pattern, flags=0):
        self._raw_pattern = pattern
        self._pattern = re.compile(pattern, flags)

    def __repr__(self):
        return f"Regex {self._raw_pattern}"

    def search(self, data):
        return bool(self._pattern.search(data))

    def split(self, data):
        return re.split(self._pattern, data, maxsplit=1)[-1]
