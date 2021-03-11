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
"""Key constants and utilities for Scenarios."""

import signal

KEY_ENTER = "\n"
KEY_UP = "\x1b[A"
KEY_DOWN = "\x1b[B"
KEY_RIGHT = "\x1b[C"
KEY_LEFT = "\x1b[D"
KEY_PAGEUP = "\x1b[5~"
KEY_PAGEDOWN = "\x1b[6~"
KEY_HOME = "\x1b[H"
KEY_END = "\x1b[F"
KEY_SPACE = "\x20"
KEY_ESCAPE = "\x1b"

SIGINT = signal.SIGINT.value
SIGKILL = signal.SIGKILL.value
