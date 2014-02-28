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

from plainbox.impl.job import JobDefinition
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

    DEF_TEXT = (
        "[PlainBox Provider]\n"
        "location = /some/directory/\n"
        "name = 2013.org.example:smoke-test\n"
        "version = 1.0\n"
        "description = A provider for smoke testing\n"
        "gettext_domain = plainbox\n")

    def setUp(self):
        self.definition = Provider1Definition()

    def test_smoke(self):
        with mock.patch('os.path.isdir') as mock_isdir:
            # Mock os.path.isdir so that we can validate location
            mock_isdir.return_value = True
            self.definition.read_string(self.DEF_TEXT)
        self.assertEqual(self.definition.location, "/some/directory/")
        self.assertEqual(self.definition.name, "2013.org.example:smoke-test")
        self.assertEqual(self.definition.version, "1.0")
        self.assertEqual(
            self.definition.description, "A provider for smoke testing")
        self.assertEqual(self.definition.gettext_domain, "plainbox")


class Provider1PlugInTests(TestCase):

    def test_plugin_name(self):
        with mock.patch('os.path.isdir') as mock_isdir:
            # Mock os.path.isdir so that we can validate location
            mock_isdir.return_value = True
            plugin = Provider1PlugIn(
                "foo.provider", Provider1DefinitionTests.DEF_TEXT)
        self.assertEqual(
            plugin.plugin_name, "2013.org.example:smoke-test")

    def test_plugin_object(self):
        with mock.patch('os.path.isdir') as mock_isdir:
            # Mock os.path.isdir so that we can validate location
            mock_isdir.return_value = True
            plugin = Provider1PlugIn(
                "foo.provider", Provider1DefinitionTests.DEF_TEXT)
        self.assertIsInstance(plugin.plugin_object, Provider1)

    def test_provider_data(self):
        with mock.patch('os.path.isdir') as mock_isdir:
            # Mock os.path.isdir so that we can validate location
            mock_isdir.return_value = True
            plugin = Provider1PlugIn(
                "foo.provider", Provider1DefinitionTests.DEF_TEXT)
        provider = plugin.plugin_object
        self.assertEqual(provider.base_dir, "/some/directory/")
        self.assertEqual(provider.name, "2013.org.example:smoke-test")
        self.assertEqual(provider.version, "1.0")
        self.assertEqual(provider.description, "A provider for smoke testing")

    def test_init_validation__no_name(self):
        """
        verify how Provider1PlugIn validates missing name field
        """
        with self.assertRaises(PlugInError) as boom:
            with mock.patch('os.path.isdir') as mock_isdir:
                # Mock os.path.isdir so that we can validate location
                mock_isdir.return_value = True
                Provider1PlugIn("broken.provider", (
                    "[PlainBox Provider]\n"
                    # NOTE: no name set, we should see that being caught
                    # "name = 2014.example.org:name\n"
                    "version = 1.0\n"
                    "location = /some/place\n"
                ))
        self.assertEqual(
            str(boom.exception), (
                "Problem in provider definition, "
                "field 'name': must be set to something"))

    def test_init_validation__empty_name(self):
        """
        verify how Provider1PlugIn validates missing name field
        """
        with self.assertRaises(PlugInError) as boom:
            with mock.patch('os.path.isdir') as mock_isdir:
                # Mock os.path.isdir so that we can validate location
                mock_isdir.return_value = True
                Provider1PlugIn("broken.provider", (
                    "[PlainBox Provider]\n"
                    "name =\n"
                    "version = 1.0\n"
                    "location = /some/place\n"
                ))
        self.assertEqual(
            str(boom.exception), (
                "Problem in provider definition, "
                "field 'name': cannot be empty"))

    def test_init_validation__non_iqn_name(self):
        """
        verify how Provider1PlugIn validates missing name field
        """
        with self.assertRaises(PlugInError) as boom:
            with mock.patch('os.path.isdir') as mock_isdir:
                # Mock os.path.isdir so that we can validate location
                mock_isdir.return_value = True
                Provider1PlugIn("broken.provider", (
                    "[PlainBox Provider]\n"
                    "name = my pretty name\n"
                    "version = 1.0\n"
                    "location = /some/place\n"
                ))
        self.assertEqual(
            str(boom.exception), (
                "Problem in provider definition, "
                "field 'name': must look like RFC3720 IQN"))

    def test_init_validation__no_version(self):
        """
        verify how Provider1PlugIn validates missing version field
        """
        with self.assertRaises(PlugInError) as boom:
            with mock.patch('os.path.isdir') as mock_isdir:
                # Mock os.path.isdir so that we can validate location
                mock_isdir.return_value = True
                Provider1PlugIn("broken.provider", (
                    "[PlainBox Provider]\n"
                    "name = 2014.example.org:name\n"
                    # NOTE: no version set, we should see that being caught
                    # "version = 1.0\n"
                    "location = /some/place\n"
                ))
        self.assertEqual(
            str(boom.exception), (
                "Problem in provider definition, "
                "field 'version': must be set to something"))

    def test_init_validation__no_location(self):
        """
        verify how Provider1PlugIn validates missing location field
        """
        with self.assertRaises(PlugInError) as boom:
            with mock.patch('os.path.isdir') as mock_isdir:
                # Mock os.path.isdir so that we can validate location
                mock_isdir.return_value = True
                Provider1PlugIn("broken.provider", (
                    "[PlainBox Provider]\n"
                    "name = 2014.example.org:name\n"
                    "version = 1.0\n"
                    # NOTE: no location set, we should see that being caught
                    # "location = /some/place\n"
                ))
        self.assertEqual(
            str(boom.exception), (
                "Problem in provider definition, "
                "field 'location': must be set to something"))

    def test_init_validation__location_is_empty(self):
        """
        verify how Provider1PlugIn validates missing location field
        """
        with self.assertRaises(PlugInError) as boom:
            with mock.patch('os.path.isdir') as mock_isdir:
                # Mock os.path.isdir so that we can validate location
                mock_isdir.return_value = True
                Provider1PlugIn("broken.provider", (
                    "[PlainBox Provider]\n"
                    "name = 2014.example.org:name\n"
                    "version = 1.0\n"
                    "location =\n"
                ))
        self.assertEqual(
            str(boom.exception), (
                "Problem in provider definition, "
                "field 'location': cannot be empty"))

    def test_init_validation__location_relative(self):
        """
        verify how Provider1PlugIn validates location field
        having a relative value
        """
        with self.assertRaises(PlugInError) as boom:
            with mock.patch('os.path.isdir') as mock_isdir:
                # Mock os.path.isdir so that we can validate location
                mock_isdir.return_value = True
                Provider1PlugIn("broken.provider", (
                    "[PlainBox Provider]\n"
                    "name = 2014.example.org:name\n"
                    "version = 1.0\n"
                    "location = some/place\n"
                ))
        self.assertEqual(
            str(boom.exception), (
                "Problem in provider definition, "
                "field 'location': cannot be relative"))

    def test_init_validation__location_doesnt_exist(self):
        """
        verify how Provider1PlugIn validates location field pointing to a
        directory that does not exist
        """
        with self.assertRaises(PlugInError) as boom:
            with mock.patch('os.path.isdir') as mock_isdir:
                # Mock os.path.isdir the *other* way around, so that this
                # directory doesn't exist, even if it does somehow
                mock_isdir.return_value = False
                Provider1PlugIn("broken.provider", (
                    "[PlainBox Provider]\n"
                    "name = 2014.example.org:name\n"
                    "version = 1.0\n"
                    "location = /some/place\n"
                ))
        self.assertEqual(
            str(boom.exception), (
                "Problem in provider definition, "
                "field 'location': no such directory"))

    def test_init_validation__gettext_domain_can_be_unset(self):
        """
        verify how Provider1PlugIn validates the lack of gettext_domain field
        (it should be allowed not to exist)
        """
        with mock.patch('os.path.isdir') as mock_isdir:
            # Mock os.path.isdir so that we can validate location
            mock_isdir.return_value = True
            plugin = Provider1PlugIn("text.provider", (
                "[PlainBox Provider]\n"
                "name = 2014.example.org:name\n"
                "version = 1.0\n"
                "location = /some/place\n"
            ))
        # NOTE: the Unset value is translated by Provider1PlugIn
        self.assertIs(plugin.plugin_object.gettext_domain, None)

    def test_init_validation__gettext_domain_can_be_defined(self):
        """
        verify how Provider1PlugIn validates the lack of gettext_domain field
        (it should be allowed not to exist)
        """
        with mock.patch('os.path.isdir') as mock_isdir:
            # Mock os.path.isdir so that we can validate location
            mock_isdir.return_value = True
            plugin = Provider1PlugIn("text.provider", (
                "[PlainBox Provider]\n"
                "name = 2014.example.org:name\n"
                "version = 1.0\n"
                "location = /some/place\n"
                "gettext_domain = some-id-6\n"
            ))
        self.assertEqual(plugin.plugin_object.gettext_domain, "some-id-6")


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

    BASE_DIR = "base-dir"
    NAME = "2013.org.example:name"
    VERSION = "1.0"
    DESCRIPTION = "description"
    SECURE = True
    GETTEXT_DOMAIN = "domain"

    def setUp(self):
        self.provider = Provider1(
            self.BASE_DIR, self.NAME, self.VERSION, self.DESCRIPTION,
            self.SECURE, self.GETTEXT_DOMAIN)

    def test_repr(self):
        self.assertEqual(
            repr(self.provider),
            "<Provider1 name:'2013.org.example:name' base_dir:'base-dir'>")

    def test_base_dir(self):
        """
        Verify that Provider1.base_dir attribute is set correctly
        """
        self.assertEqual(self.provider.base_dir, self.BASE_DIR)

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

    def test_jobs_dir(self):
        """
        Verify that Provider1.jobs_dir attribute is set correctly
        """
        self.assertEqual(self.provider.jobs_dir, "base-dir/jobs")

    def test_bin_dir(self):
        """
        Verify that Provider1.bin_dir attribute is set correctly
        """
        self.assertEqual(self.provider.bin_dir, "base-dir/bin")

    def test_whitelists_dir(self):
        """
        Verify that Provider1.whitelists_dir attribute is set correctly
        """
        self.assertEqual(self.provider.whitelists_dir, "base-dir/whitelists")

    def test_CHECKBOX_SHARE(self):
        """
        Verify that Provider1.CHECKBOX_SHARE is always equal to base_dir
        """
        self.assertEqual(self.provider.CHECKBOX_SHARE, self.provider.base_dir)

    def test_extra_PYTHONPATH(self):
        """
        Verify that Provider1.extra_PYTHONPATH is always None
        """
        self.assertIsNone(self.provider.extra_PYTHONPATH)

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
