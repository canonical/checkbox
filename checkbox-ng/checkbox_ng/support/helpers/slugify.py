# This file is part of Checkbox.
#
# Copyright 2024 Canonical Ltd.
# Written by:
#   Pierre Equoy <pierre.equoy@canonical.com>
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

import string


def slugify(_string):
    """
    Slugify a string

    Transform any string to one that can be used in filenames and Python
    identifers.
    """
    if not _string:
        return _string

    valid_chars = frozenset(
        "_{}{}".format(string.ascii_letters, string.digits)
    )
    # Python identifiers cannot start with a digit
    if _string[0].isdigit():
        _string = "_" + _string
    return "".join(c if c in valid_chars else "_" for c in _string)
