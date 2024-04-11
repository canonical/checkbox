# This file is part of Checkbox.
#
# Copyright 2013-2015 Canonical Ltd.
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
from plainbox.impl.secure.config import Unset
from plainbox.impl.secure.config import ValidationError
from plainbox.impl.secure.plugins import PlugIn
from plainbox.impl.secure.plugins import PlugInError
from plainbox.impl.secure.providers.v1 import AbsolutePathValidator
from plainbox.impl.secure.providers.v1 import ExistingDirectoryValidator
from plainbox.impl.secure.providers.v1 import IQNValidator
from plainbox.impl.secure.providers.v1 import Provider1
from plainbox.impl.secure.providers.v1 import Provider1Definition
from plainbox.impl.secure.providers.v1 import Provider1PlugIn
from plainbox.impl.secure.providers.v1 import UnitPlugIn
from plainbox.impl.secure.providers.v1 import VersionValidator
from plainbox.impl.secure.rfc822 import FileTextSource
from plainbox.impl.secure.rfc822 import Origin
from plainbox.impl.unit.file import FileUnit
from plainbox.vendor import mock


class IQNValidatorTests(TestCase):

    def setUp(self):
        self.validator = IQNValidator()
        self.variable = None

    def test_good_values_work(self):
        name = "com.canonical:certification-resources-server"
        self.assertEqual(self.validator(self.variable, name), None)

    def test_yearless_namespace_work(self):
        name = "com.canonical:certification"

    def test_must_match_whole_string(self):
        name = "com.canonical:certification-resources-server BOGUS"
        self.assertNotEqual(self.validator(self.variable, name), None)

    def test_bad_values_dont(self):
        self.assertEqual(
            self.validator(self.variable, ""), "must look like RFC3720 IQN"
        )


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

    def test_PEP440_rc_versions_work(self):
        version = "1.20rc6"
        self.assertEqual(self.validator(self.variable, version), None)

    def test_PEP440_dev_versions_work(self):
        version = "1.20.6.dev0"
        self.assertEqual(self.validator(self.variable, version), None)

    def test_bad_values_dont(self):
        version = "FOOBAR"
        self.assertEqual(
            self.validator(self.variable, version),
            "must be a PEP440 compatible version",
        )


class ExistingDirectoryValidatorTests(TestCase):

    _PATH = "/some/directory"

    def setUp(self):
        self.validator = ExistingDirectoryValidator()
        self.variable = None

    @mock.patch("os.path.isdir")
    def test_existing_directories_work(self, mock_isdir):
        mock_isdir.return_value = True
        self.assertEqual(self.validator(self.variable, self._PATH), None)
        mock_isdir.assert_called_with(self._PATH)

    @mock.patch("os.path.isdir")
    def test_missing_directories_dont(self, mock_isdir):
        mock_isdir.return_value = False
        self.assertEqual(
            self.validator(self.variable, self._PATH), "no such directory"
        )
        mock_isdir.assert_called_with(self._PATH)


class AbsolutePathValidatorTests(TestCase):

    def setUp(self):
        self.validator = AbsolutePathValidator()
        self.variable = None

    def test_absolute_values_work(self):
        self.assertEqual(self.validator(self.variable, "/path"), None)

    def test_relative_values_dont(self):
        self.assertEqual(
            self.validator(self.variable, "path"), "cannot be relative"
        )


class Provider1DefinitionTests(TestCase):

    def test_definition_without_location(self):
        """
        Smoke test to ensure we can load a typical provider definition that is
        not using the location field. Those are similar to what a packaged
        provider would look like.
        """
        def_ = Provider1Definition()
        with mock.patch("os.path.isdir") as mock_isdir:
            # Mock os.path.isdir so that we can validate all of the directory
            # variables.
            mock_isdir.return_value = True
            def_.read_string(
                "[PlainBox Provider]\n"
                "name = org.example:smoke-test\n"
                "version = 1.0\n"
                "description = a description\n"
                "gettext_domain = domain\n"
                "units_dir = /some/directory/units\n"
                "jobs_dir = /some/directory/jobs\n"
                "data_dir = /some/directory/data\n"
                "bin_dir = /some/directory/bin\n"
                "locale_dir = /some/directory/locale\n"
            )
        self.assertEqual(def_.name, "org.example:smoke-test")
        self.assertEqual(def_.version, "1.0")
        self.assertEqual(def_.description, "a description")
        self.assertEqual(def_.gettext_domain, "domain")
        self.assertEqual(def_.location, Unset)
        self.assertEqual(def_.units_dir, "/some/directory/units")
        self.assertEqual(def_.jobs_dir, "/some/directory/jobs")
        self.assertEqual(def_.data_dir, "/some/directory/data")
        self.assertEqual(def_.bin_dir, "/some/directory/bin")
        self.assertEqual(def_.locale_dir, "/some/directory/locale")

    def test_name_without_colon(self):
        """
        Verify that the property Provider1Definition.name_without_colon
        is computed correctly
        """
        def_ = Provider1Definition()
        def_.name = "org.example:smoke-test"
        self.assertEqual(def_.name, "org.example:smoke-test")
        self.assertEqual(def_.name_without_colon, "org.example.smoke-test")

    def test_definition_with_location(self):
        """
        Smoke test to ensure we can load a typical provider definition that is
        using the location field and is not using any other directory fields.
        Those are similar to what a unpackaged, under development provider
        would look like.
        """
        def_ = Provider1Definition()
        with mock.patch("os.path.isdir") as mock_isdir:
            # Mock os.path.isdir so that we can validate all of the directory
            # variables.
            mock_isdir.return_value = True
            def_.read_string(
                "[PlainBox Provider]\n"
                "name = org.example:smoke-test\n"
                "version = 1.0\n"
                "description = a description\n"
                "gettext_domain = domain\n"
                "location = /some/directory"
            )
        self.assertEqual(def_.name, "org.example:smoke-test")
        self.assertEqual(def_.version, "1.0")
        self.assertEqual(def_.description, "a description")
        self.assertEqual(def_.gettext_domain, "domain")
        self.assertEqual(def_.location, "/some/directory")
        self.assertEqual(def_.units_dir, Unset)
        self.assertEqual(def_.jobs_dir, Unset)
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
            def_.location = ""
        self.assertEqual(str(boom.exception), "cannot be empty")

    def test_init_validation__location_relative(self):
        """
        verify that Provider1Definition ensures that 'location' is not a
        relative pathname
        """
        def_ = Provider1Definition()
        with self.assertRaises(ValidationError) as boom:
            def_.location = "some/place"
        self.assertEqual(str(boom.exception), "cannot be relative")

    def test_init_validation__location_doesnt_exist(self):
        """
        verify that Provider1Definition ensures that 'location' field is not
        pointing to an non-existing directory
        """
        def_ = Provider1Definition()
        with self.assertRaises(ValidationError) as boom:
            with mock.patch("os.path.isdir") as mock_isdir:
                mock_isdir.return_value = False
                def_.location = "/some/place"
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
        for name in (
            "org.example:tests",
            "com.canonical.certification:usb-testing",
        ):
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
            def_.version = ""
        self.assertEqual(str(boom.exception), "cannot be empty")

    def test_init_validation__incorrect_looking_version(self):
        """
        verify that Provider1Definition ensures that 'version' field rejects
        values that don't look like a typical version
        """
        def_ = Provider1Definition()
        with self.assertRaises(ValidationError) as boom:
            def_.version = "FOOBAR+git4654654654"
        self.assertEqual(
            str(boom.exception), "must be a PEP440 compatible version"
        )

    def test_init_validation__typical_version(self):
        """
        verify that Provider1Definition allows typical values for the 'version'
        field
        """
        for ver in ("0.7.1", "0.7", "0", "2014.4", "12.04.5", "2014.4+bzr46"):
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
        for gettext_domain in (
            "plainbox",
            "checkbox",
            "2014_com_canonical_provider_name",
            "2014-com-canonical-provider-name",
        ):
            def_ = Provider1Definition()
            def_.gettext_domain = gettext_domain
            self.assertEqual(def_.gettext_domain, gettext_domain)

    def test_init_validation__foo_dir_unset(self):
        """
        verify that Provider1Definition allows 'jobs_dir', 'data_dir',
        'bin_dir' and 'locale_dir'  fields to be unset
        """
        for attr in (
            "units_dir",
            "jobs_dir",
            "data_dir",
            "bin_dir",
            "locale_dir",
        ):
            def_ = Provider1Definition()
            setattr(def_, attr, Unset)
            self.assertEqual(getattr(def_, attr), Unset)

    def test_init_validation__foo_dir_is_empty(self):
        """
        verify that Provider1Definition ensures that 'jobs_dir',
        'data_dir', 'bin_dir' and 'locale_dir' fields are not empty
        """
        for attr in (
            "units_dir",
            "jobs_dir",
            "data_dir",
            "bin_dir",
            "locale_dir",
        ):
            def_ = Provider1Definition()
            with self.assertRaises(ValidationError) as boom:
                setattr(def_, attr, "")
            self.assertEqual(str(boom.exception), "cannot be empty")

    def test_init_validation__foo_dir_relative(self):
        """
        verify that Provider1Definition ensures that 'jobs_dir',
        'data_dir', 'bin_dir' and 'locale_dir' fields are not a relative
        pathname
        """
        for attr in (
            "units_dir",
            "jobs_dir",
            "data_dir",
            "bin_dir",
            "locale_dir",
        ):
            def_ = Provider1Definition()
            with self.assertRaises(ValidationError) as boom:
                setattr(def_, attr, "some/place")
            self.assertEqual(str(boom.exception), "cannot be relative")

    def test_init_validation__foo_dir_doesnt_exist(self):
        """
        verify that Provider1Definition ensures that 'jobs_dir',
        'data_dir', 'bin_dir' and 'locale_dir' fields are not pointing to a
        non-existing directory
        """
        for attr in (
            "units_dir",
            "jobs_dir",
            "data_dir",
            "bin_dir",
            "locale_dir",
        ):
            def_ = Provider1Definition()
            with self.assertRaises(ValidationError) as boom:
                with mock.patch("os.path.isdir") as mock_isdir:
                    mock_isdir.return_value = False
                    setattr(def_, attr, "/some/place")
            self.assertEqual(str(boom.exception), "no such directory")


class Provider1PlugInTests(TestCase):

    DEF_TEXT = (
        "[PlainBox Provider]\n"
        "name = org.example:smoke-test\n"
        "version = 1.0\n"
        "description = a description\n"
        "gettext_domain = domain\n"
    )

    DEF_TEXT_w_location = DEF_TEXT + ("location = /some/directory\n")

    DEF_TEXT_w_dirs = DEF_TEXT + (
        "units_dir = /some/directory/units\n"
        "jobs_dir = /some/directory/jobs\n"
        "data_dir = /some/directory/data\n"
        "bin_dir = /some/directory/bin\n"
        "locale_dir = /some/directory/locale\n"
    )

    LOAD_TIME = 42

    def setUp(self):
        with mock.patch("os.path.isdir") as mock_isdir:
            # Mock os.path.isdir so that we can validate location
            mock_isdir.return_value = True
            self.plugin = Provider1PlugIn(
                "a.provider", self.DEF_TEXT, self.LOAD_TIME
            )
            self.plugin_w_location = Provider1PlugIn(
                "a.provider", self.DEF_TEXT_w_location, self.LOAD_TIME
            )
            self.plugin_w_dirs = Provider1PlugIn(
                "a.provider", self.DEF_TEXT_w_dirs, self.LOAD_TIME
            )
            # Mock os.path.isdir so that none of the sub-directories of the
            # location directory seem to exist. This is essential for
            # Provider1.from_definition()'s special behavior.
            mock_isdir.side_effect = lambda dn: dn == "/some/directory"
            self.plugin_w_location_w_no_dirs = Provider1PlugIn(
                "a.provider", self.DEF_TEXT_w_location, self.LOAD_TIME
            )

    def test_plugin_name(self):
        self.assertEqual(self.plugin.plugin_name, "org.example:smoke-test")

    def test_plugin_object(self):
        self.assertIsInstance(self.plugin.plugin_object, Provider1)

    def test_plugin_load_time(self):
        self.assertEqual(self.plugin.plugin_load_time, self.LOAD_TIME)

    def test_provider_metadata(self):
        provider = self.plugin.plugin_object
        self.assertEqual(provider.name, "org.example:smoke-test")
        self.assertEqual(provider.version, "1.0")
        self.assertEqual(provider.description, "a description")
        self.assertEqual(provider.gettext_domain, "domain")

    def test_provider_directories__no_location_no_dirs(self):
        """
        verify that none of the provider directories are set when loading a
        provider definition devoid of actual entries and the base location
        entry.
        """
        provider = self.plugin.plugin_object
        self.assertEqual(provider.units_dir, None)
        self.assertEqual(provider.jobs_dir, None)
        self.assertEqual(provider.data_dir, None)
        self.assertEqual(provider.bin_dir, None)
        self.assertEqual(provider.build_bin_dir, None)
        self.assertEqual(provider.src_dir, None)
        self.assertEqual(provider.locale_dir, None)
        self.assertEqual(provider.base_dir, None)

    def test_provider_directories__w_location(self):
        """
        verify that all of the provider directories are set when loading a
        provider definition devoid of actual entries but the base location
        entry.
        """
        provider = self.plugin_w_location.plugin_object
        self.assertEqual(provider.units_dir, "/some/directory/units")
        self.assertEqual(provider.jobs_dir, "/some/directory/jobs")
        self.assertEqual(provider.data_dir, "/some/directory/data")
        self.assertEqual(provider.bin_dir, "/some/directory/bin")
        self.assertEqual(provider.build_bin_dir, "/some/directory/build/bin")
        self.assertEqual(provider.src_dir, "/some/directory/src")
        self.assertEqual(provider.locale_dir, "/some/directory/locale")
        self.assertEqual(provider.base_dir, "/some/directory")

    def test_provider_directories__w_location_w_no_dirs(self):
        """
        verify that all of the provider directories are set to None when
        loading a provider definition devoid of actual entries but the base
        location entry *and* the filesystem reporting that those directories
        don't exist.
        """
        provider = self.plugin_w_location_w_no_dirs.plugin_object
        self.assertEqual(provider.units_dir, None)
        self.assertEqual(provider.jobs_dir, None)
        self.assertEqual(provider.data_dir, None)
        self.assertEqual(provider.bin_dir, None)
        self.assertEqual(provider.build_bin_dir, "/some/directory/build/bin")
        self.assertEqual(provider.src_dir, "/some/directory/src")
        self.assertEqual(provider.locale_dir, None)
        self.assertEqual(provider.base_dir, "/some/directory")

    def test_provider_directories__w_dirs(self):
        """
        verify that all of the provider directories are set when loading a
        provider definition with a specific entry for each directory
        """
        provider = self.plugin_w_dirs.plugin_object
        self.assertEqual(provider.units_dir, "/some/directory/units")
        self.assertEqual(provider.jobs_dir, "/some/directory/jobs")
        self.assertEqual(provider.data_dir, "/some/directory/data")
        self.assertEqual(provider.bin_dir, "/some/directory/bin")
        self.assertEqual(provider.build_bin_dir, None)
        self.assertEqual(provider.src_dir, None)
        self.assertEqual(provider.locale_dir, "/some/directory/locale")
        self.assertEqual(provider.base_dir, None)


class UnitPlugInTests(TestCase):
    """
    Tests for UnitPlugIn
    """

    LOAD_TIME = 42

    def setUp(self):
        self.provider = mock.Mock(name="provider", spec=Provider1)
        self.provider.classify.return_value = (
            mock.Mock("role"),
            mock.Mock("base"),
            mock.Mock("plugin_cls"),
        )
        self.provider.namespace = "com.canonical.plainbox"
        self.plugin = UnitPlugIn(
            "/path/to/jobs.txt",
            ("id: test/job\n" "plugin: shell\n" "command: true\n"),
            self.LOAD_TIME,
            self.provider,
        )

    def test_plugin_name(self):
        """
        verify that the UnitPlugIn.plugin_name property returns
        pathname of the job definition file
        """
        self.assertEqual(self.plugin.plugin_name, "/path/to/jobs.txt")

    def test_plugin_object(self):
        """
        verify that the UnitPlugIn.plugin_object property returns a
        list of JobDefintion instances
        """
        self.assertEqual(len(self.plugin.plugin_object), 2)
        self.assertIsInstance(self.plugin.plugin_object[0], JobDefinition)
        self.assertIsInstance(self.plugin.plugin_object[1], FileUnit)

    def test_plugin_load_time(self):
        self.assertEqual(self.plugin.plugin_load_time, self.LOAD_TIME)

    def test_job_data(self):
        """
        verify the contents of the loaded JobDefinition object
        """
        job = self.plugin.plugin_object[0]
        self.assertEqual(job.partial_id, "test/job")
        self.assertEqual(job.id, "com.canonical.plainbox::test/job")
        self.assertEqual(job.plugin, "shell")
        self.assertEqual(job.command, "true")
        self.assertEqual(
            job.origin, Origin(FileTextSource("/path/to/jobs.txt"), 1, 3)
        )

    def test_job_provider(self):
        """
        verify the loaded job got the provider from the plugin
        """
        job = self.plugin.plugin_object[0]
        self.assertIs(job.provider, self.provider)

    def test_init_failing(self):
        """
        verify how UnitPlugIn() initializer works if something is
        wrong
        """
        # The pattern is purposefully invalid
        with self.assertRaises(PlugInError) as boom:
            UnitPlugIn(
                "/path/to/jobs.txt", "broken", self.LOAD_TIME, self.provider
            )
        self.assertEqual(
            str(boom.exception),
            (
                "Cannot load job definitions from '/path/to/jobs.txt': "
                "Unexpected non-empty line: 'broken' (line 1)"
            ),
        )


class Provider1Tests(TestCase):

    NAME = "name"
    NAMESPACE = "org.example"
    VERSION = "1.0"
    DESCRIPTION = "description"
    SECURE = True
    GETTEXT_DOMAIN = "domain"
    UNITS_DIR = "units-dir"
    JOBS_DIR = "jobs-dir"
    DATA_DIR = "data-dir"
    BIN_DIR = "bin-dir"
    LOCALE_DIR = "locale-dir"
    BASE_DIR = "base-dir"

    LOAD_TIME = 42

    def setUp(self):
        self.provider = Provider1(
            self.NAME,
            self.NAMESPACE,
            self.VERSION,
            self.DESCRIPTION,
            self.SECURE,
            self.GETTEXT_DOMAIN,
            self.UNITS_DIR,
            self.JOBS_DIR,
            self.DATA_DIR,
            self.BIN_DIR,
            self.LOCALE_DIR,
            self.BASE_DIR,
            # We are using dummy job definitions so let's not shout about those
            # being invalid in each test
            validate=False,
        )
        self.fake_context = self.provider.fake([])
        self.fake_context.__enter__()

    def tearDown(self):
        self.fake_context.__exit__(None, None, None)

    def test_repr(self):
        self.assertEqual(repr(self.provider), "<Provider1 name:'name'>")

    def test_name(self):
        """
        Verify that Provider1.name attribute is set correctly
        """
        self.assertEqual(self.provider.name, self.NAME)

    def test_namespace(self):
        """
        Verify that Provider1.namespace is computed correctly
        """
        self.assertEqual(self.provider.namespace, self.NAMESPACE)

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

    def test_units_dir(self):
        """
        Verify that Provider1.jobs_dir attribute is set correctly
        """
        self.assertEqual(self.provider.units_dir, self.UNITS_DIR)

    def test_jobs_dir(self):
        """
        Verify that Provider1.jobs_dir attribute is set correctly
        """
        self.assertEqual(self.provider.jobs_dir, self.JOBS_DIR)

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

    def test_base_dir(self):
        """
        Verify that Provider1.base_dir attribute is set correctly
        """
        self.assertEqual(self.provider.base_dir, self.BASE_DIR)

    def test_CHECKBOX_SHARE(self):
        """
        Verify that Provider1.CHECKBOX_SHARE is defined as the parent directory
        of data_dir
        """
        self.assertEqual(self.provider.CHECKBOX_SHARE, self.BASE_DIR)

    def test_CHECKBOX_SHARE__without_base_dir(self):
        """
        Verify that Provider1.CHECKBOX_SHARE is None without base_dir
        """
        self.provider._base_dir = None
        self.assertEqual(self.provider.CHECKBOX_SHARE, None)

    def test_extra_PYTHONPATH(self):
        """
        Verify that Provider1.extra_PYTHONPATH is always None
        """
        self.assertIsNone(self.provider.extra_PYTHONPATH)

    def test_fake(self):
        """
        Verify that fake() redirects the provider to look for fake content.
        """
        # Create unsorted job definitions that define a1, a2, a3 and a4
        fake_content = [
            PlugIn(
                self.JOBS_DIR + "/path/to/jobs1.txt",
                (
                    "id: a2\n"
                    "plugin: shell\n"
                    "command: true\n"
                    "\n"
                    "id: a1\n"
                    "plugin: shell\n"
                    "command: true\n"
                ),
            ),
            PlugIn(
                self.JOBS_DIR + "/path/to/jobs2.txt",
                (
                    "id: a3\n"
                    "plugin: shell\n"
                    "command: true\n"
                    "\n"
                    "id: a4\n"
                    "plugin: shell\n"
                    "command: true\n"
                ),
            ),
        ]
        fake_problems = [IOError("first problem"), OSError("second problem")]
        with self.provider.fake(fake_content, fake_problems):
            job_list = self.provider.job_list
            problem_list = self.provider.problem_list
        self.assertEqual(len(job_list), 4)
        self.assertEqual(job_list[0].partial_id, "a1")
        self.assertEqual(job_list[1].partial_id, "a2")
        self.assertEqual(job_list[2].partial_id, "a3")
        self.assertEqual(job_list[3].partial_id, "a4")
        self.assertEqual(problem_list, fake_problems)

    @mock.patch("plainbox.impl.secure.providers.v1.gettext")
    def test_get_translated_data__typical(self, mock_gettext):
        """
        Verify the runtime behavior of get_translated_data()
        """
        self.provider._gettext_domain = "some-fake-domain"
        retval = self.provider.get_translated_data("foo")
        mock_gettext.dgettext.assert_called_with("some-fake-domain", "foo")
        self.assertEqual(retval, mock_gettext.dgettext())

    @mock.patch("plainbox.impl.secure.providers.v1.gettext")
    def test_get_translated_data__empty_string(self, mock_gettext):
        """
        Verify the runtime behavior of get_translated_data()
        """
        self.provider._gettext_domain = "some-fake-domain"
        retval = self.provider.get_translated_data("")
        # This should never go through gettext
        self.assertEqual(retval, "")
        # And dgettext should never be called
        self.assertEqual(mock_gettext.dgettext.call_args_list, [])

    @mock.patch("plainbox.impl.secure.providers.v1.gettext")
    def test_get_translated_data__None(self, mock_gettext):
        """
        Verify the runtime behavior of get_translated_data()
        """
        self.provider._gettext_domain = "some-fake-domain"
        retval = self.provider.get_translated_data(None)
        # This should never go through gettext
        self.assertEqual(retval, None)
        # And dgettext should never be called
        self.assertEqual(mock_gettext.dgettext.call_args_list, [])

    def test_tr_description(self):
        """
        Verify that Provider1.tr_description() works as expected
        """
        with mock.patch.object(self.provider, "get_translated_data") as mgtd:
            retval = self.provider.tr_description()
        # Ensure that get_translated_data() was called
        mgtd.assert_called_once_with(self.provider.description)
        # Ensure tr_description() returned its return value
        self.assertEqual(retval, mgtd())

    @mock.patch("plainbox.impl.secure.providers.v1.gettext")
    def test_init_bindtextdomain__called(self, mock_gettext):
        """
        Verify that Provider1() calls bindtextdomain under certain
        circumstances
        """
        Provider1(
            self.NAME,
            self.NAMESPACE,
            self.VERSION,
            self.DESCRIPTION,
            self.SECURE,
            self.GETTEXT_DOMAIN,
            self.UNITS_DIR,
            self.JOBS_DIR,
            self.DATA_DIR,
            self.BIN_DIR,
            self.LOCALE_DIR,
            self.BASE_DIR,
        )
        mock_gettext.bindtextdomain.assert_called_once_with(
            self.GETTEXT_DOMAIN, self.LOCALE_DIR
        )

    @mock.patch("plainbox.impl.secure.providers.v1.gettext")
    def test_init_bindtextdomain__not_called(self, mock_gettext):
        """
        Verify that Provider1() calls bindtextdomain under certain
        circumstances
        """
        Provider1(
            self.NAME,
            self.NAMESPACE,
            self.VERSION,
            self.DESCRIPTION,
            self.SECURE,
            self.GETTEXT_DOMAIN,
            self.UNITS_DIR,
            self.JOBS_DIR,
            self.DATA_DIR,
            self.BIN_DIR,
            locale_dir=None,
            base_dir=self.BASE_DIR,
        )
        self.assertEqual(mock_gettext.bindtextdomain.call_args_list, [])
