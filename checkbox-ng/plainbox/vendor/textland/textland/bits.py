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

# Various sizing structs
Cell = namedtuple('Cell', ['char', 'attributes'])
Size = namedtuple('Size', ['width', 'height'])
Offset = namedtuple('Offset', ['x', 'y'])
Rect = namedtuple('Rect', ['x1', 'y1', 'x2', 'y2'])
