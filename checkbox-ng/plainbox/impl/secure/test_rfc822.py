# This file is part of Checkbox.
#
# Copyright 2013 Canonical Ltd.
# Written by:
#   Sylvain Pineau <sylvain.pineau@canonical.com>
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
plainbox.impl.secure.rfc822
===========================

Test definitions for plainbox.impl.secure.rfc822 module
"""

from unittest import TestCase

from plainbox.impl.secure.rfc822 import load_rfc822_records
from plainbox.impl.test_rfc822 import RFC822ParserTestsMixIn


class RFC822ParserTests(TestCase, RFC822ParserTestsMixIn):

    @classmethod
    def setUpClass(cls):
        cls.loader = load_rfc822_records
