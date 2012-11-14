# This file is part of Checkbox.
#
# Copyright 2012 Canonical Ltd.
# Written by:
#   Zygmunt Krynicki <zygmunt.krynicki@canonical.com>
#
# Checkbox is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Checkbox is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Checkbox.  If not, see <http://www.gnu.org/licenses/>.

"""
plainbox.impl.main
==================

Internal implementation of plainbox

 * THIS MODULE DOES NOT HAVE STABLE PUBLIC API *
"""

from argparse import ArgumentParser

from plainbox import __version__ as version
from plainbox.impl.utils import run


def main(argv=None):
    parser = ArgumentParser(prog="plainbox")
    parser.add_argument(
        "-v", "--version", action="version",
        version="{}.{}.{}".format(*version[:3]))
    parser.add_argument(
        "-u", "--ui", action="store",
        default=None, choices=('headless', 'text', 'graphics'),
        help="select the UI front-end (defaults to auto)")
    ns = parser.parse_args(argv)
    return run(ui=ns.ui)
