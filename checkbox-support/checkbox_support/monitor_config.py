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
from typing import Dict, Set

Mode = namedtuple("Mode", ["resolution"])


class MonitorConfig(ABC):
    """Get and modify the current Monitor configuration."""

    @abstractmethod
    def get_connected_monitors(self) -> Set[str]:
        """Get list of connected monitors, even if inactive."""

    @abstractmethod
    def get_current_resolutions(self) -> Dict[str, str]:
        """Get current active resolutions for each monitor."""

    @abstractmethod
    def set_extended_mode(self) -> Dict[str, str]:
        """
        Set to extend mode so that each monitor can be displayed
        at preferred resolution.
        """

    def _get_mode_at_max(self, modes) -> Mode:
        """Get mode with maximum resolution."""

        def mode_area(mode):
            w, h = mode.resolution.split("x")
            return int(w) * int(h)

        try:
            return max(modes, key=mode_area)
        except ValueError as e:
            raise ValueError("Provided modes are empty or invalid.") from e
