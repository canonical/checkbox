# This file is part of Checkbox.
#
# Copyright 2014 Canonical Ltd.
# Written by:
#   Zygmunt Krynicki <zygmunt.krynicki@canonical.com>
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

"""
plainbox.impl.test_buildsystems
===============================

Test definitions for plainbox.impl.buildsystems module
"""

from unittest import TestCase

from plainbox.impl.buildsystems import GoBuildSystem
from plainbox.impl.buildsystems import MakefileBuildSystem
from plainbox.vendor import mock


class GoBuildSystemTests(TestCase):
    """
    Unit tests for the GoBuildSystem class
    """

    def setUp(self):
        self.buildsystem = GoBuildSystem()

    @mock.patch('plainbox.impl.buildsystems.glob.glob')
    def test_probe__go_sources(self, mock_glob):
        """
        Ensure that if we have some go sources then the build system finds them
        and signals suitability
        """
        mock_glob.return_value = ['src/foo.go']
        self.assertEqual(self.buildsystem.probe("src"), 50)

    @mock.patch('plainbox.impl.buildsystems.glob.glob')
    def test_probe__no_go_sources(self, mock_glob):
        """
        Ensure that if we don't have any go sources the build system is not
        suitable
        """
        mock_glob.return_value = []
        self.assertEqual(self.buildsystem.probe("src"), 0)

    def test_get_build_command(self):
        """
        Ensure that the build command is correct
        """
        self.assertEqual(
            self.buildsystem.get_build_command(
                "/path/to/src", "/path/to/build/bin"),
            "go build ../../src/*.go")


class MakefileBuildSystemTests(TestCase):
    """
    Unit tests for the MakefileBuildSystem class
    """

    def setUp(self):
        self.buildsystem = MakefileBuildSystem()

    @mock.patch('plainbox.impl.buildsystems.os.path.isfile')
    def test_probe__Makefile(self, mock_isfile):
        """
        Ensure that if we have a Makefile then the build system finds it and
        signals suitability
        """
        mock_isfile.side_effect = lambda path: path == 'src/Makefile'
        self.assertEqual(self.buildsystem.probe("src"), 90)

    @mock.patch('plainbox.impl.buildsystems.os.path.isfile')
    def test_probe__no_Makefile(self, mock_isfile):
        """
        Ensure that if we don't have a Makefile then the build system is not
        suitable
        """
        mock_isfile.side_effect = lambda path: False
        self.assertEqual(self.buildsystem.probe("src"), 0)

    @mock.patch('plainbox.impl.buildsystems.os.path.isfile')
    def test_probe__configure_and_Makefile(self, mock_isfile):
        """
        Ensure that if we have a configure script then the build system finds
        it and signals lack of suitability, we want developers to specifically
        tell us how to build with a configure script around.
        """
        mock_isfile.side_effect = lambda path: path in ('src/Makefile',
                                                        'src/configure')
        self.assertEqual(self.buildsystem.probe("src"), 0)

    def test_get_build_command(self):
        """
        Ensure that the build command is correct
        """
        self.assertEqual(
            self.buildsystem.get_build_command(
                "/path/to/src", "/path/to/build/bin"),
            "VPATH=../../src make -f ../../src/Makefile")
