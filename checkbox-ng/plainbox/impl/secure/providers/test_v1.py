# This file is part of Checkbox.
#
# Copyright 2013 Canonical Ltd.
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
plainbox.impl.secure.providers.test_v1
======================================

Test definitions for plainbox.impl.secure.providers.v1 module
"""

from unittest import TestCase
import os

from plainbox.impl.job import JobDefinition
from plainbox.impl.secure.config import Unset
from plainbox.impl.secure.plugins import PlugInError
from plainbox.impl.secure.providers.v1 import AbsolutePathValidator
from plainbox.impl.secure.providers.v1 import ExistingDirectoryValidator
from plainbox.impl.secure.providers.v1 import IQNValidator
from plainbox.impl.secure.providers.v1 import JobDefinitionPlugIn
from plainbox.impl.secure.providers.v1 import Provider1
from plainbox.impl.secure.providers.v1 import Provider1Definition
from plainbox.impl.secure.providers.v1 import Provider1PlugIn
from plainbox.impl.secure.providers.v1 import VersionValidator
from plainbox.impl.secure.providers.v1 import WhiteListPlugIn
from plainbox.impl.secure.qualifiers import WhiteList
from plainbox.impl.secure.rfc822 import FileTextSource
from plainbox.impl.secure.rfc822 import Origin
from plainbox.vendor import mock


class IQNValidatorTests(TestCase):

    def setUp(self):
        self.validator = IQNValidator()
        self.variable = None

    def test_good_values_work(self):
        name = "2013.com.canonical:certification-resources-server"
        self.assertEqual(self.validator(self.variable, name), None)

    def test_must_match_whole_string(self):
        name = "2013.com.canonical:certification-resources-server BOGUS"
        self.assertNotEqual(self.validator(self.variable, name), None)

    def test_bad_values_dont(self):
        self.assertEqual(
            self.validator(self.variable, ""),
            "must look like RFC3720 IQN")


class VersionValidatorTests(TestCase):

    def setUp(self):
        self.validator = VersionValidator()
        self.variable = None

    def test_typical_versions_work(self):
        version = "1.10.7"
        self.assertEqual(self.validator(self.variable, version), None)

    def test_single_digit_versions_work(self):
        version = "5"
        self.assertEqual(self.validator(self.variable, version), None)

    def test_bad_values_dont(self):
        version = "1.5a7"
        self.assertEqual(
            self.validator(self.variable, version),
            "must be a sequence of digits separated by dots")


class ExistingDirectoryValidatorTests(TestCase):

    _PATH = "/some/directory"

    def setUp(self):
        self.validator = ExistingDirectoryValidator()
        self.variable = None

    @mock.patch('os.path.isdir')
    def test_existing_directories_work(self, mock_isdir):
        mock_isdir.return_value = True
        self.assertEqual(self.validator(self.variable, self._PATH), None)
        mock_isdir.assertCalledWith(self._PATH)

    @mock.patch('os.path.isdir')
    def test_missing_directories_dont(self, mock_isdir):
        mock_isdir.return_value = False
        self.assertEqual(
            self.validator(self.variable, self._PATH),
            "no such directory")
        mock_isdir.assertCalledWith(self._PATH)


class AbsolutePathValidatorTests(TestCase):

    def setUp(self):
        self.validator = AbsolutePathValidator()
        self.variable = None

    def test_absolute_values_work(self):
        self.assertEqual(self.validator(self.variable, '/path'), None)

    def test_relative_values_dont(self):
        self.assertEqual(
            self.validator(self.variable, 'path'),
            "cannot be relative")


class Provider1DefinitionTests(TestCase):

    def test_definition_without_location(self):
        """
        Smoke test to ensure we can load a typical provider definition that is
        not using the location field. Those are similar to what a packaged
        provider would look like.
        """
        def_ = Provider1Definition()
        with mock.patch('os.path.isdir') as mock_isdir:
            # Mock os.path.isdir so that we can validate all of the directory
            # variables.
            mock_isdir.return_value = True
            def_.read_string(
                "[PlainBox Provider]\n"
                "name = 2013.org.example:smoke-test\n"
                "version = 1.0\n"
                "description = a description\n"
                "gettext_domain = domain\n"
                "jobs_dir = /some/directory/jobs\n"
                "whitelists_dir = /some/directory/whitelists\n"
                "data_dir = /some/directory/data\n"
                "bin_dir = /some/directory/bin\n"
                "locale_dir = /some/directory/locale\n"
            )
        self.assertEqual(def_.name, "2013.org.example:smoke-test")
        self.assertEqual(def_.version, "1.0")
        self.assertEqual(def_.description, "a description")
        self.assertEqual(def_.gettext_domain, "domain")
        self.assertEqual(def_.location, Unset)
        self.assertEqual(def_.jobs_dir, "/some/directory/jobs")
        self.assertEqual(def_.whitelists_dir, "/some/directory/whitelists")
        self.assertEqual(def_.data_dir, "/some/directory/data")
        self.assertEqual(def_.bin_dir, "/some/directory/bin")
        self.assertEqual(def_.locale_dir, "/some/directory/locale")

    def test_definition_with_location(self):
        """
        Smoke test to ensure we can load a typical provider definition that is
        using the location field and is not using any other directory fields.
        Those are similar to what a unpackaged, under development provider
        would look like.
        """
        def_ = Provider1Definition()
        with mock.patch('os.path.isdir') as mock_isdir:
            # Mock os.path.isdir so that we can validate all of the directory
            # variables.
            mock_isdir.return_value = True
            def_.read_string(
                "[PlainBox Provider]\n"
                "name = 2013.org.example:smoke-test\n"
                "version = 1.0\n"
                "description = a description\n"
                "gettext_domain = domain\n"
                "location = /some/directory"
            )
        self.assertEqual(def_.name, "2013.org.example:smoke-test")
        self.assertEqual(def_.version, "1.0")
        self.assertEqual(def_.description, "a description")
        self.assertEqual(def_.gettext_domain, "domain")
        self.assertEqual(def_.location, "/some/directory")
        self.assertEqual(def_.jobs_dir, Unset)
        self.assertEqual(def_.whitelists_dir, Unset)
        self.assertEqual(def_.data_dir, Unset)
        self.assertEqual(def_.bin_dir, Unset)
        self.assertEqual(def_.locale_dir, Unset)

    def test_init_validation__location_unset(self):
        """
        verify that Provider1Definition allows 'location' field to be unset
        """
        def_ = Provider1Definition()
        def_.location = Unset
        self.assertEqual(def_.location, Unset)

    def test_init_validation__location_is_empty(self):
        """
        verify that Provider1Definition ensures that 'location' field is not
        empty
        """
        def_ = Provider1Definition()
        with self.assertRaises(ValidationError) as boom:
            def_.location = ''
        self.assertEqual(str(boom.exception), "cannot be empty")

    def test_init_validation__location_relative(self):
        """
        verify that Provider1Definition ensures that 'location' is not a
        relative pathname
        """
        def_ = Provider1Definition()
        with self.assertRaises(ValidationError) as boom:
            def_.location = 'some/place'
        self.assertEqual(str(boom.exception), "cannot be relative")

    def test_init_validation__location_doesnt_exist(self):
        """
        verify that Provider1Definition ensures that 'location' field is not
        pointing to an non-existing directory
        """
        def_ = Provider1Definition()
        with self.assertRaises(ValidationError) as boom:
            with mock.patch('os.path.isdir') as mock_isdir:
                mock_isdir.return_value = False
                def_.location = '/some/place'
        self.assertEqual(str(boom.exception), "no such directory")

    def test_init_validation__no_name(self):
        """
        verify that Provider1Definition ensures that 'name' field is not unset
        """
        def_ = Provider1Definition()
        with self.assertRaises(ValidationError) as boom:
            def_.name = Unset
        self.assertEqual(str(boom.exception), "must be set to something")

    def test_init_validation__empty_name(self):
        """
        verify that Provider1Definition ensures that 'name' field is not empty
        """
        def_ = Provider1Definition()
        with self.assertRaises(ValidationError) as boom:
            def_.name = ""
        self.assertEqual(str(boom.exception), "cannot be empty")

    def test_init_validation__non_iqn_name(self):
        """
        verify that Provider1Definition ensures that 'name' field rejects names
        that don't look like RFC3720 IQN
        """
        def_ = Provider1Definition()
        with self.assertRaises(ValidationError) as boom:
            def_.name = "name = my pretty name\n"
        self.assertEqual(str(boom.exception), "must look like RFC3720 IQN")

    def test_init_validation__typical_name(self):
        """
        verify that Provider1Definition allows typical values for 'name' field
        """
        def_ = Provider1Definition()
        for name in ('2013.org.example:tests',
                     '2013.com.canonical.certification:usb-testing'):
            def_.name = name
            self.assertEqual(def_.name, name)

    def test_init_validation__no_version(self):
        """
        verify that Provider1Definition ensures that 'version' field is not
        unset
        """
        def_ = Provider1Definition()
        with self.assertRaises(ValidationError) as boom:
            def_.version = Unset
        self.assertEqual(str(boom.exception), "must be set to something")

    def test_init_validation__empty_version(self):
        """
        verify that Provider1Definition ensures that 'version' field is not
        empty
        """
        def_ = Provider1Definition()
        with self.assertRaises(ValidationError) as boom:
            def_.version = ''
        self.assertEqual(str(boom.exception), "cannot be empty")

    def test_init_validation__incorrect_looking_version(self):
        """
        verify that Provider1Definition ensures that 'version' field rejects
        values that don't look like a typical version
        """
        def_ = Provider1Definition()
        with self.assertRaises(ValidationError) as boom:
            def_.version = "2014.4+bzr46"
        self.assertEqual(
            str(boom.exception),
            "must be a sequence of digits separated by dots")

    def test_init_validation__typical_version(self):
        """
        verify that Provider1Definition allows typical values for the 'version'
        field
        """
        for ver in ('0.7.1', '0.7', '0', '2014.4', '12.04.5'):
            def_ = Provider1Definition()
            def_.version = ver
            self.assertEqual(def_.version, ver)

    def test_init_validation__any_description(self):
        """
        verify that Provider1Definition allows any value for the 'description'
        field
        """
        for desc in (Unset, "", "description"):
            def_ = Provider1Definition()
            def_.description = desc
            self.assertEqual(def_.description, desc)

    def test_init_validation__gettext_domain_can_be_unset(self):
        """
        verify that Provider1Definition allows 'gettext_domain' field to be
        unset
        """
        def_ = Provider1Definition()
        def_.gettext_domain = Unset
        self.assertEqual(def_.gettext_domain, Unset)

    def test_init_validation__typical_gettext_domain(self):
        """
        verify that Provider1Definition allows 'gettext_domain' field to have
        typical values
        """
        for gettext_domain in ("plainbox", "checkbox",
                               "2014_com_canonical_provider_name",
                               "2014-com-canonical-provider-name"):
            def_ = Provider1Definition()
            def_.gettext_domain = gettext_domain
            self.assertEqual(def_.gettext_domain, gettext_domain)

    def test_init_validation__foo_dir_unset(self):
        """
        verify that Provider1Definition allows 'jobs_dir', 'whitelists_dir',
        'data_dir', 'bin_dir' and 'locale_dir'  fields to be unset
        """
        for attr in ('jobs_dir', 'whitelists_dir', 'data_dir', 'bin_dir',
                     'locale_dir'):
            def_ = Provider1Definition()
            setattr(def_, attr, Unset)
            self.assertEqual(getattr(def_, attr), Unset)

    def test_init_validation__foo_dir_is_empty(self):
        """
        verify that Provider1Definition ensures that 'jobs_dir',
        'whitelists_dir', 'data_dir', 'bin_dir' and 'locale_dir' fields are not
        empty
        """
        for attr in ('jobs_dir', 'whitelists_dir', 'data_dir', 'bin_dir',
                     'locale_dir'):
            def_ = Provider1Definition()
            with self.assertRaises(ValidationError) as boom:
                setattr(def_, attr, '')
            self.assertEqual(str(boom.exception), "cannot be empty")

    def test_init_validation__foo_dir_relative(self):
        """
        verify that Provider1Definition ensures that 'jobs_dir',
        'whitelists_dir', 'data_dir', 'bin_dir' and 'locale_dir' fields are not
        a relative pathname
        """
        for attr in ('jobs_dir', 'whitelists_dir', 'data_dir', 'bin_dir',
                     'locale_dir'):
            def_ = Provider1Definition()
            with self.assertRaises(ValidationError) as boom:
                setattr(def_, attr, 'some/place')
            self.assertEqual(str(boom.exception), "cannot be relative")

    def test_init_validation__foo_dir_doesnt_exist(self):
        """
        verify that Provider1Definition ensures that 'jobs_dir',
        'whitelists_dir', 'data_dir', 'bin_dir' and 'locale_dir' fields are not
        pointing to a non-existing directory
        """
        for attr in ('jobs_dir', 'whitelists_dir', 'data_dir', 'bin_dir',
                     'locale_dir'):
            def_ = Provider1Definition()
            with self.assertRaises(ValidationError) as boom:
                with mock.patch('os.path.isdir') as mock_isdir:
                    mock_isdir.return_value = False
                    setattr(def_, attr, '/some/place')
            self.assertEqual(str(boom.exception), "no such directory")


class WhiteListPlugInTests(TestCase):
    """
    Tests for WhiteListPlugIn
    """

    def setUp(self):
        self.plugin = WhiteListPlugIn("/path/to/some.whitelist", "foo\nbar\n")

    def test_plugin_name(self):
        """
        verify that the WhiteListPlugIn.plugin_name property returns
        WhiteList.name
        """
        self.assertEqual(self.plugin.plugin_name, "some")

    def test_plugin_object(self):
        """
        verify that the WhiteListPlugIn.plugin_object property returns a
        WhiteList
        """
        self.assertIsInstance(self.plugin.plugin_object, WhiteList)

    def test_whitelist_data(self):
        """
        verify the contents of the loaded whitelist object
        """
        self.assertEqual(
            self.plugin.plugin_object.qualifier_list[0].pattern_text, "^foo$")
        self.assertEqual(
            self.plugin.plugin_object.qualifier_list[1].pattern_text, "^bar$")
        self.assertEqual(self.plugin.plugin_object.name, 'some')
        self.assertEqual(
            self.plugin.plugin_object.origin,
            Origin(FileTextSource('/path/to/some.whitelist'), 1, 2))

    def test_init_failing(self):
        """
        verify how WhiteList() initializer works if something is wrong
        """
        # The pattern is purposefully invalid
        with self.assertRaises(PlugInError) as boom:
            WhiteListPlugIn("/path/to/some.whitelist", "*")
        # NOTE: we should have syntax error for whitelists that keeps track or
        # line we're at to help developers figure out where errors such as this
        # are coming from.
        self.assertEqual(
            str(boom.exception),
            ("Cannot load whitelist '/path/to/some.whitelist': "
             "nothing to repeat"))


class JobDefintionPlugInTests(TestCase):
    """
    Tests for JobDefinitionPlugIn
    """

    def setUp(self):
        self.provider = mock.Mock(name="provider", spec=Provider1)
        self.plugin = JobDefinitionPlugIn(
            "/path/to/jobs.txt", (
                "id: test/job\n"
                "plugin: shell\n"
                "command: true\n"),
            self.provider)

    def test_plugin_name(self):
        """
        verify that the JobDefinitionPlugIn.plugin_name property returns
        pathname of the job definition file
        """
        self.assertEqual(self.plugin.plugin_name, "/path/to/jobs.txt")

    def test_plugin_object(self):
        """
        verify that the JobDefinitionPlugIn.plugin_object property returns a
        list of JobDefintion instances
        """
        self.assertEqual(len(self.plugin.plugin_object), 1)
        self.assertIsInstance(self.plugin.plugin_object[0], JobDefinition)

    def test_job_data(self):
        """
        verify the contents of the loaded JobDefinition object
        """
        job = self.plugin.plugin_object[0]
        self.assertEqual(job.id, "test/job")
        self.assertEqual(job.plugin, "shell")
        self.assertEqual(job.command, "true")
        self.assertEqual(
            job.origin, Origin(FileTextSource("/path/to/jobs.txt"), 1, 3))

    def test_job_provider(self):
        """
        verify the loaded job got the provider from the plugin
        """
        job = self.plugin.plugin_object[0]
        self.assertIs(job.provider, self.provider)

    def test_init_failing(self):
        """
        verify how JobDefinitionPlugIn() initializer works if something is
        wrong
        """
        # The pattern is purposefully invalid
        with self.assertRaises(PlugInError) as boom:
            JobDefinitionPlugIn("/path/to/jobs.txt", "broken", self.provider)
        self.assertEqual(
            str(boom.exception),
            ("Cannot load job definitions from '/path/to/jobs.txt': "
             "Unexpected non-empty line: 'broken' (line 1)"))


class Provider1Tests(TestCase):

    NAME = "2013.org.example:name"
    VERSION = "1.0"
    DESCRIPTION = "description"
    SECURE = True
    GETTEXT_DOMAIN = "domain"
    JOBS_DIR = "jobs-dir"
    WHITELISTS_DIR = "whitelists-dir"
    DATA_DIR = "data-dir"
    BIN_DIR = "bin-dir"
    LOCALE_DIR = "locale-dir"

    def setUp(self):
        self.provider = Provider1(
            self.NAME, self.VERSION, self.DESCRIPTION, self.SECURE,
            self.GETTEXT_DOMAIN, self.JOBS_DIR, self.WHITELISTS_DIR,
            self.DATA_DIR, self.BIN_DIR, self.LOCALE_DIR)

    def test_repr(self):
        self.assertEqual(
            repr(self.provider),
            "<Provider1 name:'2013.org.example:name'>")

    def test_name(self):
        """
        Verify that Provider1.name attribute is set correctly
        """
        self.assertEqual(self.provider.name, self.NAME)

    def test_version(self):
        """
        Verify that Provider1.version attribute is set correctly
        """
        self.assertEqual(self.provider.version, self.VERSION)

    def test_description(self):
        """
        Verify that Provider1.description attribute is set correctly
        """
        self.assertEqual(self.provider.description, self.DESCRIPTION)

    def test_secure(self):
        """
        Verify that Provider1.secure attribute is set correctly
        """
        self.assertEqual(self.provider.secure, self.SECURE)

    def test_gettext_domain(self):
        """
        Verify that Provider1.gettext_domain attribute is set correctly
        """
        self.assertEqual(self.provider.gettext_domain, self.GETTEXT_DOMAIN)

    def test_jobs_dir(self):
        """
        Verify that Provider1.jobs_dir attribute is set correctly
        """
        self.assertEqual(self.provider.jobs_dir, self.JOBS_DIR)

    def test_whitelists_dir(self):
        """
        Verify that Provider1.whitelists_dir attribute is set correctly
        """
        self.assertEqual(self.provider.whitelists_dir, self.WHITELISTS_DIR)

    def test_data_dir(self):
        """
        Verify that Provider1.data_dir attribute is set correctly
        """
        self.assertEqual(self.provider.data_dir, self.DATA_DIR)

    def test_bin_dir(self):
        """
        Verify that Provider1.bin_dir attribute is set correctly
        """
        self.assertEqual(self.provider.bin_dir, self.BIN_DIR)

    def test_locale_dir(self):
        """
        Verify that Provider1.locale_dir attribute is set correctly
        """
        self.assertEqual(self.provider.locale_dir, self.LOCALE_DIR)

    def test_CHECKBOX_SHARE(self):
        """
        Verify that Provider1.CHECKBOX_SHARE is defined as the parent directory
        of data_dir
        """
        self.assertEqual(self.provider.CHECKBOX_SHARE,
                         os.path.join(self.DATA_DIR, ".."))

    def test_extra_PYTHONPATH(self):
        """
        Verify that Provider1.extra_PYTHONPATH is always None
        """
        self.assertIsNone(self.provider.extra_PYTHONPATH)

    def test_get_builtin_whitelists__normal(self):
        """
        verify that Provider1.get_builtin_whitelist() loads and returns all of
        the whitelists
        """
        fake_plugins = [WhiteListPlugIn("/path/to/some.whitelist", "foo")]
        with self.provider._whitelist_collection.fake_plugins(fake_plugins):
            whitelist_list = self.provider.get_builtin_whitelists()
        self.assertEqual(len(whitelist_list), 1)
        self.assertEqual(repr(whitelist_list[0]), "<WhiteList name:'some'>")

    def test_get_builtin_whitelists__failing(self):
        """
        verify that Provider1.get_builtin_whitelist() raises the first
        exception that happens during the load process
        """
        fake_plugins = [WhiteListPlugIn("/path/to/some.whitelist", "foo")]
        fake_problems = [IOError("first problem"), OSError("second problem")]
        with self.assertRaises(IOError):
            with self.provider._whitelist_collection.fake_plugins(
                    fake_plugins, fake_problems):
                self.provider.get_builtin_whitelists()

    def test_get_builtin_whitelists__without_whitelists_dir(self):
        """
        verify that Provider1.get_builtin_whitelist() returns an empty list if
        the whitelists_dir is None
        """
        provider = Provider1(
            self.NAME, self.VERSION, self.DESCRIPTION, self.SECURE,
            self.GETTEXT_DOMAIN, self.JOBS_DIR, None,
            self.DATA_DIR, self.BIN_DIR, self.LOCALE_DIR)
        self.assertEqual(provider.get_builtin_whitelists(), [])

    def test_get_builtin_jobs__normal(self):
        """
        verify that Provider1.get_builtin_jobs() loads and returns all of
        the job definitions (and that they are in the right order)
        """
        # Create unsorted job definitions that define a1, a2, a3 and a4
        fake_plugins = [
            JobDefinitionPlugIn("/path/to/jobs1.txt", (
                "id: a2\n"
                "\n"
                "id: a1\n"), self.provider),
            JobDefinitionPlugIn("/path/to/jobs2.txt", (
                "id: a3\n"
                "\n"
                "id: a4\n"), self.provider)
        ]
        with self.provider._job_collection.fake_plugins(fake_plugins):
            job_list = self.provider.get_builtin_jobs()
        self.assertEqual(len(job_list), 4)
        self.assertEqual(job_list[0].id, "a1")
        self.assertEqual(job_list[1].id, "a2")
        self.assertEqual(job_list[2].id, "a3")
        self.assertEqual(job_list[3].id, "a4")

    def test_get_builtin_jobs__failing(self):
        """
        verify that Provider1.get_builtin_jobs() raises the first
        exception that happens during the load process
        """
        fake_plugins = [JobDefinitionPlugIn(
            "/path/to/jobs.txt", "", self.provider)]
        fake_problems = [IOError("first problem"), OSError("second problem")]
        with self.assertRaises(IOError):
            with self.provider._job_collection.fake_plugins(
                    fake_plugins, fake_problems):
                self.provider.get_builtin_jobs()

    def test_get_builtin_jobs__without_jobs_dir(self):
        """
        verify that Provider1.get_builtin_jobs() returns an empty list if there
        the jobs_dir is None.
        """
        provider = Provider1(
            self.NAME, self.VERSION, self.DESCRIPTION, self.SECURE,
            self.GETTEXT_DOMAIN, None, self.WHITELISTS_DIR,
            self.DATA_DIR, self.BIN_DIR, self.LOCALE_DIR)
        self.assertEqual(provider.get_builtin_jobs(), [])

    def test_load_all_jobs__normal(self):
        """
        verify that Provider1.load_all_jobs() loads and returns all of
        the job definitions (and that they are in the right order)
        """
        # Create unsorted job definitions that define a1, a2, a3 and a4
        fake_plugins = [
            JobDefinitionPlugIn("/path/to/jobs1.txt", (
                "id: a2\n"
                "\n"
                "id: a1\n"), self.provider),
            JobDefinitionPlugIn("/path/to/jobs2.txt", (
                "id: a3\n"
                "\n"
                "id: a4\n"), self.provider)
        ]
        with self.provider._job_collection.fake_plugins(fake_plugins):
            job_list, problem_list = self.provider.load_all_jobs()
        self.assertEqual(len(job_list), 4)
        self.assertEqual(job_list[0].id, "a1")
        self.assertEqual(job_list[1].id, "a2")
        self.assertEqual(job_list[2].id, "a3")
        self.assertEqual(job_list[3].id, "a4")
        self.assertEqual(len(problem_list), 0)

    def test_load_all_jobs__failing(self):
        """
        verify that Provider1.load_all_jobs() returns all of the problems
        without raising an exception that happens during the load process
        """
        fake_plugins = [
            JobDefinitionPlugIn(
                "/path/to/jobs1.txt", "id: working\n", self.provider)
        ]
        fake_problems = [
            PlugInError("some problem"),
        ]
        with self.provider._job_collection.fake_plugins(
                fake_plugins, fake_problems):
            job_list, problem_list = self.provider.load_all_jobs()
        self.assertEqual(len(job_list), 1)
        self.assertEqual(job_list[0].id, "working")
        self.assertEqual(problem_list, fake_problems)

    def test_get_all_executables(self):
        self.skipTest("not implemented")

    def test_get_all_executables__without_bin_dir(self):
        """
        verify that Provider1.get_all_executables() returns an empty list if
        there the bin_dir is None.
        """
        provider = Provider1(
            self.NAME, self.VERSION, self.DESCRIPTION, self.SECURE,
            self.GETTEXT_DOMAIN, self.JOBS_DIR, self.WHITELISTS_DIR,
            self.DATA_DIR, None, self.LOCALE_DIR)
        self.assertEqual(provider.get_all_executables(), [])
