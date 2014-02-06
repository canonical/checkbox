# -*- coding: utf-8 -*-
#
# This file is part of Checkbox.
#
# Copyright 2014 Canonical Ltd.
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
#

from unittest import TestCase


class TestSubmissionModuleVersion(TestCase):

    def testVersion(self):
        from checkbox_support import parsers
        ver = getattr(parsers, "__version__")
        self.assertTrue(ver)
