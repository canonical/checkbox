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

from collections import namedtuple

# Input event
Event = namedtuple('Event', ['kind', 'data'])

# Data for Event.data
KeyboardData = namedtuple('KeyboardData', ['key'])
MouseData = namedtuple('MouseData', ['x', 'y', 'buttons'])

# Constants for Event.kind
EVENT_KEYBOARD = "keyboard"
EVENT_MOUSE = "mouse"
EVENT_RESIZE = "resize"
