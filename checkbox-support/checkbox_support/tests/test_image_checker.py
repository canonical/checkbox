# This file is part of Checkbox.
#
# Copyright 2024 Canonical Ltd.
# Written by:
#   Vincent Liao <vincent.liao@canonical.com>
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

import unittest
from unittest.mock import patch, mock_open
from checkbox_support.image_checker import get_type, get_source, main


class ImageCheckerTest(unittest.TestCase):
    def __init__(self, methodName: str = "runTest") -> None:
        super().__init__(methodName)
        self.mock_oem_info = ("Sun, 20 June 1999 66:66:66 +7777\n"
                              "Somethingcool\n"
                              "iot-vincent-core-24-x24-2023-10-31-24\n")
        self.mock_stock_info = "20231031.6"

    @patch("checkbox_support.image_checker.on_ubuntucore")
    def test_get_type(self, mock_on_ubuntu_core):
        mock_on_ubuntu_core.return_value = True
        self.assertEqual(get_type(), "core")

        mock_on_ubuntu_core.return_value = False
        self.assertEqual(get_type(), "classic")

    @patch("checkbox_support.image_checker.exists")
    @patch("checkbox_support.image_checker.get_type")
    def test_get_source(self, mock_get_type, mock_exists):
        # Test when it is core image
        mock_get_type.return_value = "core"
        with patch("builtins.open", mock_open(read_data=self.mock_oem_info)):
            self.assertEqual(get_source(), "oem")

        with patch("builtins.open", mock_open(read_data=self.mock_stock_info)):
            self.assertEqual(get_source(), "stock")

        with patch("builtins.open", side_effect=FileNotFoundError):
            self.assertEqual(get_source(), "unknown")

        # Test when it is classic image
        mock_get_type.return_value = "classic"
        mock_exists.return_value = True
        self.assertEqual(get_source(), "oem")

        mock_exists.return_value = False
        self.assertEqual(get_source(), "stock")

    @patch("sys.argv", ["script_name.py", "--get_type", "--get_source"])
    @patch("checkbox_support.image_checker.get_source")
    @patch("checkbox_support.image_checker.get_type")
    def test_main(self, mock_get_type, mock_get_source):
        main()
        mock_get_type.assert_called_with()
        mock_get_source.assert_called_with()
