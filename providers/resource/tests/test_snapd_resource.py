#!/usr/bin/env python3
#
# This file is part of Checkbox.
#
# Copyright 2024 Canonical Ltd.
#    Authors: Pierre Equoy <pierre.equoy@canonical.com>
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

from io import StringIO
from unittest import TestCase
from unittest.mock import patch, Mock

import snapd_resource


class FeaturesTests(TestCase):
    def setUp(self):
        self.features = snapd_resource.Features()

    @patch("snapd_resource.get_kernel_snap", return_value="test-snap")
    @patch("snapd_resource.on_ubuntucore", return_value=False)
    def test_has_kernel_extraction_feature__not_core(
        self,
        mock_on_ubuntucore,
        mock_kernel_snap,
    ):
        self.assertEqual(
            self.features._has_kernel_extraction_feature(),
            False
        )

    @patch("snapd_resource.get_kernel_snap", return_value="")
    @patch("snapd_resource.on_ubuntucore", return_value=True)
    def test_has_kernel_extraction_feature__no_kernel_snap(
        self,
        mock_on_ubuntucore,
        mock_kernel_snap,
    ):
        self.assertEqual(
            self.features._has_kernel_extraction_feature(),
            False
        )

    @patch("snapd_resource.get_kernel_snap", return_value="test-snap")
    @patch("snapd_resource.on_ubuntucore", return_value=True)
    @patch("snapd_resource.get_series", return_value="22")
    def test_has_kernel_extraction_feature__series22(
        self,
        mock_get_series,
        mock_on_ubuntucore,
        mock_kernel_snap,
    ):
        self.assertEqual(
            self.features._has_kernel_extraction_feature(),
            True
        )

    @patch("snapd_resource.get_kernel_snap", return_value="test-snap")
    @patch("snapd_resource.on_ubuntucore", return_value=True)
    @patch("snapd_resource.get_series", return_value="18")
    @patch("os.path.exists", return_value=True)
    def test_has_kernel_extraction_feature__series18_ok(
        self,
        mock_path_exists,
        mock_get_series,
        mock_on_ubuntucore,
        mock_kernel_snap,
    ):
        self.assertEqual(
            self.features._has_kernel_extraction_feature(),
            True
        )

    @patch("snapd_resource.get_kernel_snap", return_value="test-snap")
    @patch("snapd_resource.on_ubuntucore", return_value=True)
    @patch("snapd_resource.get_series", return_value="18")
    @patch("os.path.exists", return_value=False)
    def test_has_kernel_extraction_feature__series18_not_ok(
        self,
        mock_path_exists,
        mock_get_series,
        mock_on_ubuntucore,
        mock_kernel_snap,
    ):
        self.assertEqual(
            self.features._has_kernel_extraction_feature(),
            False
        )

    @patch("sys.stdout", new_callable=StringIO)
    def test_invoked(self, mock_stdout):
        self.features._has_kernel_extraction_feature = Mock(return_value=True)
        self.features.invoked()
        self.assertIn(
            "force_kernel_extraction: True\n\n",
            mock_stdout.getvalue()
        )
