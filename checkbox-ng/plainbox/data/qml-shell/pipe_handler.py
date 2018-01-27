# This file is part of Checkbox.
#
# Copyright 2012-2014 Canonical Ltd.
# Written by:
#   Maciej Kisielewski <maciej.kisielewski@canonical.com>
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

import os


def write_and_close(s, fd: str) -> None:
    """
    Write ``s`` to file descriptor ``fd`` and close ``fd`` afterwards.

    fd is of type str because calling code is written in javascript that
    doesn't support notion of ints.
    """
    with os.fdopen(int(fd), 'wt', encoding='utf-8') as stream:
        stream.write(s)


def read_and_close(fd: str) -> str:
    """
    Read from ``fd`` file descriptor and close ``fd`` afterwards.
    returns read string

    fd is of type str because calling code is written in javascript that
    doesn't support notion of ints.
    """
    with os.fdopen(int(fd), 'rt', encoding='utf-8') as stream:
        return stream.read()
