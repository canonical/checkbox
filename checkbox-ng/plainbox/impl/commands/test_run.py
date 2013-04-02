# This file is part of Checkbox.
#
# Copyright 2013 Canonical Ltd.
# Written by:
#   Zygmunt Krynicki <zygmunt.krynicki@canonical.com>
#   Daniel Manrique  <roadmr@ubuntu.com>
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
plainbox.impl.commands.test_run
===============================

Test definitions for plainbox.impl.run module
"""

from unittest import TestCase
from io import StringIO, BytesIO

from plainbox.impl.commands.run import ByteStringStreamTranslator


class TestRun(TestCase):

    def test_byte_string_translator(self):
        dest_stream = StringIO()
        source_stream = BytesIO(b'This is a bytes literal')
        encoding = 'utf-8'

        translator = ByteStringStreamTranslator(dest_stream, encoding)
        translator.write(source_stream.getvalue())

        self.assertEqual('This is a bytes literal', dest_stream.getvalue())
