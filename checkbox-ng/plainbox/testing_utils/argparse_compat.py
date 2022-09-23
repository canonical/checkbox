# This file is part of Checkbox.
#
# Copyright 2022 Canonical Ltd.
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
"""
Hacks to make testing of argparse prints work on python <= 3.9 and >= 3.10.
"""

import argparse


def optionals_section():
    """
    Return a string that's the default title for the group of optional
    arguments, as returned by argparse.
    """
    try:
        # Let's try pulling the info directly from the ArgumentParser object.
        # This means peekign at private parts of it.
        return argparse.ArgumentParser()._optionals.title
    except Exception:
        # If anything goes south we need to guess the string basing on the
        # pythoon version
        import sys
        vi = sys.version_info
        if vi.major >= 3 and vi.minor >= 10:
            return 'options'
        else:
            return 'optional arguments'


optionals_section = optionals_section()
