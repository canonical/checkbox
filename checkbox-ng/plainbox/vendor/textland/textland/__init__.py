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

"""
Text Land
=========
"""

__version__ = (0, 1, 0, "final", 0)

__all__ = [
    'BLACK',
    'BLUE',
    'BRIGHT_BLACK',
    'BRIGHT_BLUE',
    'BRIGHT_CYAN',
    'BRIGHT_GREEN',
    'BRIGHT_MAGENTA',
    'BRIGHT_RED',
    'BRIGHT_WHITE',
    'BRIGHT_YELLOW',
    'CYAN',
    'Cell',
    'DrawingContext',
    'EVENT_KEYBOARD',
    'EVENT_MOUSE',
    'EVENT_RESIZE',
    'Event',
    'GREEN',
    'IApplication',
    'IDisplay',
    'KeyboardData',
    'MAGENTA',
    'MouseData',
    'NORMAL',
    'RED',
    'REVERSE',
    'Rect',
    'Size',
    'TestDisplay',
    'TextAttributes',
    'TextImage',
    'UNDERLINE',
    'WHITE',
    'YELLOW',
    '__version__',
    'get_display',
]

from .abc import IApplication
from .abc import IDisplay
from .bits import Cell
from .bits import Rect
from .bits import Size
from .display import TestDisplay
from .display import get_display
from .drawing import DrawingContext
from .events import EVENT_KEYBOARD
from .events import EVENT_MOUSE
from .events import EVENT_RESIZE
from .events import Event
from .events import KeyboardData
from .events import MouseData
from .image import BLACK
from .image import BLUE
from .image import BRIGHT_BLACK
from .image import BRIGHT_BLUE
from .image import BRIGHT_CYAN
from .image import BRIGHT_GREEN
from .image import BRIGHT_MAGENTA
from .image import BRIGHT_RED
from .image import BRIGHT_WHITE
from .image import BRIGHT_YELLOW
from .image import CYAN
from .image import GREEN
from .image import MAGENTA
from .image import NORMAL
from .image import RED
from .image import REVERSE
from .image import TextAttributes
from .image import TextImage
from .image import UNDERLINE
from .image import WHITE
from .image import YELLOW
