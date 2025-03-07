#!/usr/bin/env python3
# This file is part of Checkbox.
#
# Copyright 2025 Canonical Ltd.
# Authors:
#   Fernando Bravo <fernando.bravo.hernandez@canonical.com>
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

from unittest import TestCase
from unittest.mock import patch, MagicMock, mock_open, call

from kernel_config import (
    get_kernel_config_path,
    get_configuration,
    check_flag,
    parse_args,
    main,
)


class TestKernelConfig(TestCase):

    @patch("kernel_config.os.uname")
    @patch("kernel_config.decode")
    @patch("kernel_config.os.path.exists")
    def test_get_kernel_config_path_snap(
        self, exists_mock, decode_mock, uname_mock
    ):
        uname_mock.return_value = MagicMock(release="5.4.0-42-generic")
        decode_mock.return_value = [{"kernel": "pc-kernel"}]
        exists_mock.side_effect = (
            lambda x: x == "/snap/pc-kernel/current/config-5.4.0-42-generic"
        )
        self.assertEqual(
            get_kernel_config_path(),
            "/snap/pc-kernel/current/config-5.4.0-42-generic",
        )

    @patch("kernel_config.os.uname")
    @patch("kernel_config.decode")
    @patch("kernel_config.os.path.exists")
    def test_get_kernel_config_path_host(
        self, exists_mock, decode_mock, uname_mock
    ):
        uname_mock.return_value = MagicMock(release="5.4.0-42-generic")
        decode_mock.return_value = []
        exists_mock.side_effect = (
            lambda x: x == "/var/lib/snapd/hostfs/boot/config-5.4.0-42-generic"
        )
        self.assertEqual(
            get_kernel_config_path(),
            "/var/lib/snapd/hostfs/boot/config-5.4.0-42-generic",
        )

    @patch("kernel_config.os.uname")
    @patch("kernel_config.decode")
    @patch("kernel_config.os.path.exists")
    def test_get_kernel_config_path_classic(
        self, exists_mock, decode_mock, uname_mock
    ):
        uname_mock.return_value = MagicMock(release="5.4.0-42-generic")
        decode_mock.return_value = []
        exists_mock.side_effect = (
            lambda x: x == "/boot/config-5.4.0-42-generic"
        )
        self.assertEqual(
            get_kernel_config_path(), "/boot/config-5.4.0-42-generic"
        )

    @patch("kernel_config.os.uname")
    @patch("kernel_config.decode")
    @patch("kernel_config.os.path.exists")
    def test_get_kernel_config_path_not_found(
        self, exists_mock, decode_mock, uname_mock
    ):
        uname_mock.return_value = MagicMock(release="5.4.0-42-generic")
        decode_mock.return_value = []
        exists_mock.return_value = False

        with self.assertRaises(SystemExit) as context:
            get_kernel_config_path()
        self.assertEqual(
            str(context.exception), "Kernel configuration not found."
        )

    @patch("kernel_config.get_kernel_config_path")
    @patch("kernel_config.shutil.copy2")
    @patch("kernel_config.open", MagicMock())
    @patch("kernel_config.print", MagicMock())
    def test_get_configuration_output(self, copy2_mock, get_path_mock):
        get_path_mock.return_value = "/boot/config-5.4.0-42-generic"
        get_configuration("/tmp/config")
        copy2_mock.assert_called_once_with(
            "/boot/config-5.4.0-42-generic", "/tmp/config"
        )

    @patch("kernel_config.get_kernel_config_path")
    @patch("kernel_config.print")
    @patch("kernel_config.shutil.copy2", MagicMock())
    def test_get_configuration_print(self, print_mock, get_path_mock):
        get_path_mock.return_value = "/boot/config-5.4.0-42-generic"
        data = "CONFIG_INTEL_IOMMU=y\nCONFIG_INTEL_IOMMU_DEFAULT_ON=y"
        with patch("builtins.open", mock_open(read_data=data)):
            get_configuration()
        print_mock.assert_called_once_with(data)

    @patch("kernel_config.os.uname")
    @patch("kernel_config.print")
    def test_check_flag_lower_version(self, print_mock, uname_mock):
        uname_mock.return_value = MagicMock(release="5.4.0-42-generic")
        check_flag("CONFIG_INTEL_IOMMU_DEFAULT_ON", "6.8.0-20")

        uname_mock.return_value = MagicMock(release="5.4.0-42-intel-iotg")
        check_flag("CONFIG_INTEL_IOMMU_DEFAULT_ON", "6.8.0-20")

        uname_mock.return_value = MagicMock(release="6.8.0-11-generic")
        check_flag("CONFIG_INTEL_IOMMU_DEFAULT_ON", "6.8.0-20")

        print_mock.assert_has_calls(
            [
                call(
                    "Kernel version is 5.4.0-42.",
                    "Versions lower than 6.8.0-20 don't require ",
                    "the flag CONFIG_INTEL_IOMMU_DEFAULT_ON to be set.",
                ),
                call(
                    "Kernel version is 5.4.0-42.",
                    "Versions lower than 6.8.0-20 don't require ",
                    "the flag CONFIG_INTEL_IOMMU_DEFAULT_ON to be set.",
                ),
                call(
                    "Kernel version is 6.8.0-11.",
                    "Versions lower than 6.8.0-20 don't require ",
                    "the flag CONFIG_INTEL_IOMMU_DEFAULT_ON to be set.",
                ),
            ]
        )

    @patch("kernel_config.os.uname")
    @patch("kernel_config.print")
    @patch("kernel_config.get_kernel_config_path", MagicMock())
    def test_check_flag_present(self, print_mock, uname_mock):
        uname_mock.return_value = MagicMock(release="6.8.0-45-generic")
        data = (
            "#\n"
            "# Automatically generated file; DO NOT EDIT.\n"
            "# Linux/x86 6.8.12 Kernel Configuration\n"
            "#\n"
            "CONFIG_INTEL_IOMMU=y\n"
            "CONFIG_INTEL_IOMMU_DEFAULT_ON=y\n"
        )
        with patch("builtins.open", mock_open(read_data=data)):
            check_flag("CONFIG_INTEL_IOMMU_DEFAULT_ON", "6.8.0-20")
        print_mock.assert_called_once_with(
            "Flag CONFIG_INTEL_IOMMU_DEFAULT_ON is present and set to 'y'."
        )

    @patch("kernel_config.os.uname")
    @patch("kernel_config.print", MagicMock())
    @patch("kernel_config.get_kernel_config_path", MagicMock())
    def test_check_flag_not_present(self, uname_mock):
        uname_mock.return_value = MagicMock(release="6.8.0-45-generic")
        data = (
            "#\n"
            "# Automatically generated file; DO NOT EDIT.\n"
            "# Linux/x86 6.8.12 Kernel Configuration\n"
            "#\n"
            "CONFIG_INTEL_IOMMU=y\n"
        )
        with patch("builtins.open", mock_open(read_data=data)):
            with self.assertRaises(SystemExit) as context:
                check_flag("CONFIG_INTEL_IOMMU_DEFAULT_ON", "6.8.0-20")
        self.assertEqual(
            str(context.exception),
            "Flag CONFIG_INTEL_IOMMU_DEFAULT_ON not found in the kernel config.",
        )

    @patch("kernel_config.os.uname")
    @patch("kernel_config.print", MagicMock())
    @patch("kernel_config.get_kernel_config_path", MagicMock())
    def test_check_flag_commented(self, uname_mock):
        uname_mock.return_value = MagicMock(release="6.8.0-45-generic")
        data = (
            "#\n"
            "# Automatically generated file; DO NOT EDIT.\n"
            "# Linux/x86 6.8.12 Kernel Configuration\n"
            "#\n"
            "# CONFIG_INTEL_IOMMU_DEFAULT_ON=y\n"
        )
        with patch("builtins.open", mock_open(read_data=data)):
            with self.assertRaises(SystemExit) as context:
                check_flag("CONFIG_INTEL_IOMMU_DEFAULT_ON", "6.8.0-20")
        self.assertEqual(
            str(context.exception),
            "Flag CONFIG_INTEL_IOMMU_DEFAULT_ON not found in the kernel config.",
        )

    @patch("kernel_config.argparse.ArgumentParser.parse_args")
    def test_parse_args(self, parse_args_mock):
        parse_args_mock.return_value = MagicMock(
            output="/tmp/config",
            config_flag="CONFIG_INTEL_IOMMU",
            min_version="6.8.0-20",
        )

        args = parse_args()
        self.assertEqual(args.output, "/tmp/config")
        self.assertEqual(args.config_flag, "CONFIG_INTEL_IOMMU")
        self.assertEqual(args.min_version, "6.8.0-20")

    @patch("kernel_config.get_configuration")
    @patch("kernel_config.check_flag")
    @patch("kernel_config.parse_args")
    def test_main_check_flag(
        self, parse_args_mock, check_flag_mock, get_config_mock
    ):
        parse_args_mock.return_value = MagicMock(
            output=None,
            config_flag="CONFIG_INTEL_IOMMU",
            min_version="6.8.0-20",
        )

        main()
        check_flag_mock.assert_called_once_with(
            "CONFIG_INTEL_IOMMU", "6.8.0-20"
        )
        get_config_mock.assert_not_called()

    @patch("kernel_config.get_configuration")
    @patch("kernel_config.check_flag")
    @patch("kernel_config.parse_args")
    def test_main_get_configuration(
        self, parse_args_mock, check_flag_mock, get_config_mock
    ):
        parse_args_mock.return_value = MagicMock(
            output="/tmp/config",
            config_flag=None,
            min_version=None,
        )

        main()
        get_config_mock.assert_called_once_with("/tmp/config")
        check_flag_mock.assert_not_called()
