# This file is part of Checkbox.
#
# Copyright 2013 Canonical Ltd.
# Written by:
#   Zygmunt Krynicki <zygmunt.krynicki@canonical.com>
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
plainbox.impl.providers.test_special
====================================

Test definitions for plainbox.impl.providers.special module
"""

from unittest import TestCase

from plainbox.impl.applogic import WhiteList
from plainbox.impl.providers.special import IHVProvider
from plainbox.impl.providers.v1 import DummyProvider1
from plainbox.impl.providers.v1 import Provider1
from plainbox.impl.testing_utils import make_job


class TestIHVProvider(TestCase):

    def setUp(self):
        self.job_list = [make_job('foo'), make_job('bar')]
        self.whitelist_list = [
            WhiteList([], name='ihv-foo'), WhiteList([], name='other')]
        self.real_provider = DummyProvider1(
            job_list=self.job_list, whitelist_list=self.whitelist_list)
        self.ihv_provider = IHVProvider(self.real_provider)

    def test_default_settings(self):
        provider = IHVProvider()
        # It is either CheckBoxSrcProvider or CheckBoxDebProvider but it's not
        # easy to test that IMHO. This just ensures we got something there.
        self.assertIsInstance(provider._real, Provider1)

    def test_name(self):
        """
        verify IHVProvider.name property
        """
        self.assertEqual(self.ihv_provider.name, "ihv")

    def test_description(self):
        """
        verify IHVProvider.description property
        """
        self.assertEqual(self.ihv_provider.description, "IHV")

    def test_get_builtin_jobs(self):
        """
        verify that IHVProvider.get_builtin_jobs() just returns all jobs
        """
        self.assertEqual(self.ihv_provider.get_builtin_jobs(), self.job_list)

    def test_get_builtin_whitelists(self):
        """
        verify that IHVProvider.get_builtin_whitelists() returns only
        whitelists for which name starts with 'ihv-'.
        """
        self.assertEqual(
            self.ihv_provider.get_builtin_whitelists(),
            [self.whitelist_list[0]])

    def test_CHECKBOX_SHARE(self):
        """
        verify that IHVProvider.CHECKBOX_SHARE property just returns the
        value from the real provider
        """
        self.assertEqual(
            self.ihv_provider.CHECKBOX_SHARE,
            self.real_provider.CHECKBOX_SHARE)

    def test_extra_PYTHONPATH(self):
        """
        verify that IHVProvider.extra_PYTHONPATH property just returns the
        value from the real provider
        """
        self.assertEqual(
            self.ihv_provider.extra_PYTHONPATH,
            self.real_provider.extra_PYTHONPATH)

    def test_extra_PATH(self):
        """
        verify that IHVProvider.extra_PATH property just returns the
        value from the real provider
        """
        self.assertEqual(
            self.ihv_provider.extra_PATH,
            self.real_provider.extra_PATH)
