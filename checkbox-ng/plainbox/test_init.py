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

from unittest import TestCase, mock

import os
import plainbox


class PlainboxInitTests(TestCase):
    @mock.patch.dict(os.environ, {"VIRTUAL_ENV": "test"})
    def test_get_origin_venv(self):
        origin = plainbox.get_origin()
        self.assertEqual(origin["packaging"]["type"], "source")

    @mock.patch.dict(os.environ, {"SNAP_NAME": "test"})
    def test_get_origin_snap(self):
        origin = plainbox.get_origin()
        self.assertEqual(origin["packaging"]["type"], "snap")

    @mock.patch.dict(os.environ, {}, clear=True)
    @mock.patch("subprocess.check_output")
    def test_get_origin_debian(self, mock_sp_check_output):
        mock_sp_check_output.return_value = (
            "python3-checkbox-ng: /usr/lib/python3/dist-packages/plainbox\n"
        )
        origin = plainbox.get_origin()
        self.assertEqual(origin["packaging"]["type"], "debian")
