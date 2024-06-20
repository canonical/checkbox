# Copyright 2024 Canonical Ltd.
# Written by:
#   Paolo Gentili <paolo.gentili@canonical.com>
#
# This is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License version 3,
# as published by the Free Software Foundation.
#
# This file is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this file.  If not, see <http://www.gnu.org/licenses/>.
"""
This modules includes an abstract class to get display information and
set a new logical monitor configuration.
"""

from abc import ABC, abstractmethod
from collections import namedtuple
from typing import Dict

Mode = namedtuple(
    "Mode", ["resolution", "refresh_rate", "is_preferred", "is_current"]
)


class MonitorConfig(ABC):
    """Get and modify the current Monitor configuration."""

    @abstractmethod
    def get_current_resolutions(self) -> Dict[str, str]:
        """Get current active resolutions for each monitor."""
        pass

    @abstractmethod
    def set_extended_mode(self):
        """
        Set to extend mode so that each monitor can be displayed
        at max resolution.
        """
        pass
