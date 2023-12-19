# This file is part of Checkbox.
#
# Copyright 2023 Canonical Ltd.
# Written by:
#   Massimiliano Girardi <massimiliano.girardi@canonical.com>
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

from checkbox_ng.launcher.provider_tools import main


class ProviderToolsTests(TestCase):
    @mock.patch("importlib.util.spec_from_file_location")
    @mock.patch("importlib.util.module_from_spec")
    @mock.patch("os.path.exists")
    def test_ok(self, path_exists_mock, module_fs_mock, spec_from_file_mock):
        # this loads the manage.py from cwd checking before
        # make this check pass
        path_exists_mock.return_value = True
        main()
        # manage.py was loaded as spec
        self.assertTrue(spec_from_file_mock.called)
        spec_mock = spec_from_file_mock.return_value
        # mange.py was turned into a module
        self.assertTrue(module_fs_mock.called)
        module_mock = module_fs_mock.return_value
        # and it was launched
        spec_mock.loader.exec_module.assert_called_with(module_mock)

    @mock.patch("importlib.util.spec_from_file_location")
    @mock.patch("importlib.util.module_from_spec")
    @mock.patch("os.path.exists")
    def test_fail(self, path_exists_mock, module_fs_mock, spec_from_file_mock):
        # this loads the manage.py from cwd checking before
        path_exists_mock.return_value = False
        with self.assertRaises(SystemExit):
            main()
