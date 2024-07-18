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
from unittest.mock import MagicMock, patch, mock_open
from checkbox_support.scripts.image_checker import (
    get_type,
    get_source,
    main,
    has_desktop_environment,
)
from io import StringIO
from subprocess import CompletedProcess


class ImageCheckerTest(unittest.TestCase):

    @patch("checkbox_support.scripts.image_checker.on_ubuntucore")
    def test_get_type(self, mock_on_ubuntu_core):
        mock_on_ubuntu_core.return_value = True
        self.assertEqual(get_type(), "core")

        mock_on_ubuntu_core.return_value = False
        self.assertEqual(get_type(), "classic")

    @patch("checkbox_support.scripts.image_checker.exists")
    @patch("checkbox_support.scripts.image_checker.get_type")
    def test_get_source(self, mock_get_type, mock_exists):
        # Test when it is core image
        mock_get_type.return_value = "core"
        mock_oem_info = (
            "Sun, 20 June 1999 66:66:66 +7777\n"
            "Somethingcool\n"
            "iot-vincent-core-24-x24-2023-10-31-24\n"
        )
        with patch("builtins.open", mock_open(read_data=mock_oem_info)):
            self.assertEqual(get_source(), "oem")

        mock_stock_info = "20231031.6"
        with patch("builtins.open", mock_open(read_data=mock_stock_info)):
            self.assertEqual(get_source(), "stock")

        with patch("builtins.open", side_effect=FileNotFoundError):
            self.assertEqual(get_source(), "unknown")

        # Test when it is classic image
        mock_get_type.return_value = "classic"
        mock_exists.return_value = True
        self.assertEqual(get_source(), "oem")

        mock_exists.return_value = False
        self.assertEqual(get_source(), "stock")

    @patch("checkbox_support.scripts.image_checker.run")
    def test_has_desktop_environment(self, mock_run: MagicMock):
        # 'ubuntu-desktop' or 'ubuntu-desktop-minimal'
        # pick one to return true
        def create_dpkg_side_effect(option: str):
            # kwargs are stdout and stderr, not used in this case
            def wrapped(args, **_):
                if args[2] == option:
                    return CompletedProcess(args, 0)
                return CompletedProcess(args, 1)

            return wrapped

        mock_run.side_effect = create_dpkg_side_effect("ubuntu-desktop")
        self.assertTrue(has_desktop_environment())

        mock_run.side_effect = create_dpkg_side_effect(
            "ubuntu-desktop-minimal"
        )
        self.assertTrue(has_desktop_environment())

        mock_run.side_effect = create_dpkg_side_effect("neither")
        self.assertFalse(has_desktop_environment())

    @patch("sys.argv", ["script_name.py", "--type", "--source"])
    @patch("checkbox_support.scripts.image_checker.get_source")
    @patch("checkbox_support.scripts.image_checker.get_type")
    @patch("sys.stdout", new_callable=StringIO)
    def test_main(self, mock_stdout, mock_get_type, mock_get_source):
        main()
        mock_get_type.assert_called_with()
        mock_get_source.assert_called_with()
