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
plainbox.test_provider_manager
==============================

Test definitions for plainbox.provider_manager module
"""

from unittest import TestCase
import inspect
import os
import shutil
import sys
import tarfile
import tempfile
import textwrap
import plainbox

from plainbox.impl.providers.v1 import get_universal_PROVIDERPATH_entry
from plainbox.impl.secure.providers.v1 import Provider1Definition
from plainbox.provider_manager import InstallCommand
from plainbox.provider_manager import ManageCommand
from plainbox.provider_manager import ProviderManagerTool
from plainbox.provider_manager import manage_py_extension
from plainbox.testing_utils.argparse_compat import optionals_section
from plainbox.testing_utils.io import TestIO
from plainbox.vendor import mock


def inline_output(text):
    return textwrap.dedent(text).lstrip('\n')


class ProviderManagerToolTests(TestCase):
    """
    Unit tests for provider manager tools
    """

    maxDiff = None

    def test_help(self):
        """
        verify that ``--help`` works.
        """
        with TestIO() as test_io:
            with self.assertRaises(SystemExit):
                self.tool.main(["--help"])
        self.maxDiff = None
        help_str = """
            usage: {} [--help] [--version] [options]

            Per-provider management script

            positional arguments:
              {{info,validate,develop,install,sdist,i18n,build,clean,packaging,test}}
                info                display basic information about this provider
                validate            perform various static analysis and validation
                develop             install/remove this provider, only for development
                install             install this provider in the system
                sdist               create a source tarball
                i18n                update, merge and build translation catalogs
                build               build provider specific executables from source
                clean               clean build results
                packaging           generate packaging meta-data
                test                run tests defined for this provider

            {}:
              -h, --help            show this help message and exit
              --version             show program's version number and exit

            logging and debugging:
              -v, --verbose         be more verbose (same as --log-level=INFO)
              -D, --debug           enable DEBUG messages on the root logger
              -C, --debug-console   display DEBUG messages in the console
              -T LOGGER, --trace LOGGER
                                    enable DEBUG messages on the specified logger (can be
                                    used multiple times)
              -P, --pdb             jump into pdb (python debugger) when a command crashes
              -I, --debug-interrupt
                                    crash on SIGINT/KeyboardInterrupt, useful with --pdb
            """.format(os.path.basename(sys.argv[0]), optionals_section)
        self.assertEqual(test_io.stdout, inspect.cleandoc(help_str) + '\n')

    def assert_common_flat_install(self, prefix="/foo"):
        filename = self.tmpdir + os.path.join(
            prefix, "share", "plainbox-providers-1",
            "com.example.test.provider")
        content = (
            "[PlainBox Provider]\n"
            "description = description\n"
            "gettext_domain = domain\n"
            "location = {prefix}/lib/plainbox-providers-1/com.example:test\n"
            "name = com.example:test\n"
            "version = 1.0\n"
            "\n".format(prefix=prefix))
        self.assertFileContent(filename, content)
        self.assertFileContent(
            self.tmpdir + os.path.join(
                prefix, "lib", "plainbox-providers-1", "com.example:test",
                "units", "testplans.pxu"
            ), (
                "unit: test plan\n"
                "id: test\n"
                "_name: Dummy Tests\n"
                "_description: All dummy tests\n"
                "estimated_duration: 10\n"
                "include: dummy\n"))
        self.assertFileContent(
            self.tmpdir + os.path.join(
                prefix, "lib", "plainbox-providers-1", "com.example:test",
                "data", "test.dat"),
            "data\n")
        self.assertFileContent(
            self.tmpdir + os.path.join(
                prefix, "lib", "plainbox-providers-1", "com.example:test",
                "bin", "test.sh"),
            "#!/bin/sh\n:\n")

    def test_install__flat(self):
        """
        verify that ``install --layout=flat`` works
        """
        self.tool.main(
            ["install", "--prefix=/foo", "--root={}".format(self.tmpdir)])
        self.assert_common_flat_install()
        self.assertFileContent(
            self.tmpdir + os.path.join("/foo", "lib", "plainbox-providers-1",
                                       "com.example:test", "jobs",
                                       "jobs.pxu"),
            "id: dummy\n"
            "plugin: shell\n"
            "command: true\n"
            "estimated_duration: 10\n"
            "_description: This job is dummy\n")

    def test_install__flat_partial(self):
        """
        verify that ``install --layout=flat`` works when some files
        are missing
        """
        shutil.rmtree(os.path.join(self.tmpdir, "jobs"))
        self.tool.main(
            ["install", "--prefix=/foo", "--root={}".format(self.tmpdir)])
        self.assert_common_flat_install()
        self.assertFalse(
            os.path.exists(self.tmpdir + os.path.join(
                "/foo", "lib", "plainbox-providers-1", "com.example:test",
                "jobs", "jobs.pxu")))

    def assert_common_unix_install(self, prefix="/foo"):
        filename = self.tmpdir + os.path.join(
            prefix, "share", "plainbox-providers-1",
            "com.example.test.provider")
        content = (
            "[PlainBox Provider]\n"
            "bin_dir = {prefix}/lib/com.example:test/bin\n"
            "data_dir = {prefix}/share/com.example:test/data\n"
            "description = description\n"
            "gettext_domain = domain\n"
            "jobs_dir = {prefix}/share/com.example:test/jobs\n"
            "name = com.example:test\n"
            "units_dir = {prefix}/share/com.example:test/units\n"
            "version = 1.0\n"
            "\n".format(prefix=prefix))
        self.assertFileContent(filename, content)
        self.assertFileContent(
            self.tmpdir + os.path.join(
                prefix, "share", "com.example:test", "jobs", "jobs.pxu"),
            "id: dummy\n"
            "plugin: shell\n"
            "command: true\n"
            "estimated_duration: 10\n"
            "_description: This job is dummy\n")
        self.assertFileContent(
            self.tmpdir + os.path.join(
                prefix, "share",  "com.example:test", "units",
                "testplans.pxu"
            ), (
                "unit: test plan\n"
                "id: test\n"
                "_name: Dummy Tests\n"
                "_description: All dummy tests\n"
                "estimated_duration: 10\n"
                "include: dummy\n"))
        self.assertFileContent(
            self.tmpdir + os.path.join(
                prefix, "share", "com.example:test", "data", "test.dat"),
            "data\n")
        self.assertFileContent(
            self.tmpdir + os.path.join(
                prefix, "lib", "com.example:test", "bin", "test.sh"),
            "#!/bin/sh\n:\n")

    def test_install__unix(self):
        """
        verify that ``install --layout=unix`` works
        """
        self.tool.main(
            ["install", "--prefix=/foo", "--layout=unix",
             "--root={}".format(self.tmpdir)])
        self.assert_common_unix_install()

    def assert_common_sdist(self, tarball):
        self.assertTarballContent(
            tarball, "com.example.test-1.0/units/testplans.pxu", (
                "unit: test plan\n"
                "id: test\n"
                "_name: Dummy Tests\n"
                "_description: All dummy tests\n"
                "estimated_duration: 10\n"
                "include: dummy\n"))
        self.assertTarballContent(
            tarball, "com.example.test-1.0/data/test.dat", "data\n")
        self.assertTarballContent(
            tarball, "com.example.test-1.0/bin/test.sh",
            "#!/bin/sh\n:\n")
        self.assertTarballContent(
            tarball, "com.example.test-1.0/src/hello.c",
            "int main() { return 0; }\n")

    def test_sdist(self):
        """
        verify that ``sdist`` creates a proper tarball
        """
        self.tool.main(["sdist"])
        tarball = os.path.join(
            self.tmpdir, "dist", "com.example.test-1.0.tar.gz")
        self.assertTarballContent(
            tarball, "com.example.test-1.0/jobs/jobs.pxu",
            "id: dummy\n"
            "plugin: shell\n"
            "command: true\n"
            "estimated_duration: 10\n"
            "_description: This job is dummy\n"
        )
        self.assert_common_sdist(tarball)

    def test_sdist__partial(self):
        """
        verify that ``sdist`` creates a proper tarball
        even if some files are missing
        """
        shutil.rmtree(os.path.join(self.tmpdir, "jobs"))
        self.tool.main(["sdist"])
        tarball = os.path.join(
            self.tmpdir, "dist", "com.example.test-1.0.tar.gz")
        self.assertNoTarballContent(
            tarball, "com.example.test-1.0/jobs/jobs.pxu")
        self.assert_common_sdist(tarball)

    @mock.patch('plainbox.impl.providers.v1.get_universal_PROVIDERPATH_entry')
    def test_develop(self, mock_path_entry):
        """
        verify that ``develop`` creates a provider file
        """
        provider_path = os.path.join(self.tmpdir, "checkbox-providers-develop")
        filename = os.path.join(
            provider_path, "com.example.test.provider")
        mock_path_entry.return_value = provider_path
        content = (
            "[PlainBox Provider]\n"
            "description = description\n"
            "gettext_domain = domain\n"
            "location = {}\n"
            "name = com.example:test\n"
            "version = 1.0\n"
            "\n").format(self.tmpdir)
        self.tool.main(["develop"])
        self.assertFileContent(filename, content)

    @mock.patch('plainbox.impl.providers.v1.get_universal_PROVIDERPATH_entry')
    def test_develop__force(self, mock_path_entry):
        """
        verify that ``develop --force`` overwrites existing .provider
        file
        """
        provider_path = os.path.join(self.tmpdir, "checkbox-providers-develop")
        filename = os.path.join(
            provider_path, "com.example.test.provider")
        mock_path_entry.return_value = provider_path
        content = (
            "[PlainBox Provider]\n"
            "description = description\n"
            "gettext_domain = domain\n"
            "location = {}\n"
            "name = com.example:test\n"
            "version = 1.0\n"
            "\n").format(self.tmpdir)
        os.makedirs(os.path.dirname(filename))
        with open(filename, "wt") as stream:
            stream.write("should have been overwritten")
        self.tool.main(["develop", "--force"])
        self.assertFileContent(filename, content)

    @mock.patch('plainbox.impl.providers.v1.get_universal_PROVIDERPATH_entry')
    def test_develop__uninstall(self, mock_path_entry):
        """
        verify that ``develop --uninstall`` works
        """
        provider_path = os.path.join(self.tmpdir, "checkbox-providers-develop")
        filename = os.path.join(
            provider_path, "com.example.test.provider")
        mock_path_entry.return_value = provider_path
        os.makedirs(os.path.dirname(filename))
        with open(filename, "wt") as stream:
            stream.write("should have been removed")
        self.tool.main(["develop", "--uninstall"])
        self.assertFalse(os.path.exists(filename))

    def test_validate(self):
        """
        verify that ``validate -N`` says everything is okay when it is
        """
        with TestIO() as test_io:
            self.tool.main(["validate", "-N"])
        self.assertEqual(test_io.stdout, inline_output(
            """
            The provider seems to be valid
            """))

    def test_validate__broken_missing_field(self):
        """
        verify that ``validate -N`` shows information about missing fields
        """
        filename = os.path.join(self.tmpdir, "jobs", "broken.pxu")
        with open(filename, "wt", encoding='UTF-8') as stream:
            print("id: broken", file=stream)
            print("plugin: shell", file=stream)
        with TestIO() as test_io:
            self.tool.main(["validate", "-N"])
        self.assertEqual(test_io.stdout, inline_output(
            """
            error: jobs/broken.pxu:1-2: job 'broken', field 'command', command is mandatory for non-manual jobs
            Validation of provider com.example:test has failed
            """))

    def test_validate__broken_wrong_field(self):
        """
        verify that ``validate -N`` shows information about incorrect
        field values
        """
        filename = os.path.join(self.tmpdir, "jobs", "broken.pxu")
        with open(filename, "wt", encoding='UTF-8') as stream:
            print("id: broken", file=stream)
            print("plugin: magic", file=stream)
        with TestIO() as test_io:
            self.tool.main(["validate", "-N"])
        self.assertEqual(test_io.stdout, inline_output(
            """
            error: jobs/broken.pxu:1-2: job 'broken', field 'command', command is mandatory for non-manual jobs
            error: jobs/broken.pxu:2: job 'broken', field 'plugin', valid values are: attachment, manual, resource, shell, user-interact, user-interact-verify, user-verify
            Validation of provider com.example:test has failed
            """))

    def test_validate__broken_useless_field(self):
        """
        verify that ``validate -N`` shows information about useless field
        values
        """
        filename = os.path.join(self.tmpdir, "jobs", "broken.pxu")
        with open(filename, "wt", encoding='UTF-8') as stream:
            print("id: broken", file=stream)
            print("plugin: manual", file=stream)
            print("description: broken job definition", file=stream)
            print("command: true", file=stream)
        with TestIO() as test_io:
            self.tool.main(["validate", "-N"])
        self.assertEqual(test_io.stdout, inline_output(
            """
            warning: jobs/broken.pxu:4: job 'broken', field 'command', command on a manual job makes no sense
            warning: jobs/broken.pxu:3: job 'broken', field 'description', field should be marked as translatable
            Validation of provider com.example:test has failed
            """))

    def test_validate__broken_deprecated_field(self):
        """
        verify that ``validate -N`` shows information about deprecated fields
        """
        filename = os.path.join(self.tmpdir, "jobs", "broken.pxu")
        with open(filename, "wt", encoding='UTF-8') as stream:
            print("name: broken", file=stream)
            print("plugin: manual", file=stream)
            print("description: broken job definition", file=stream)
            print("command: true", file=stream)
        with TestIO() as test_io:
            self.tool.main(["validate", "-N"])
        self.assertEqual(test_io.stdout, inline_output(
            """
            warning: jobs/broken.pxu:4: job 'broken', field 'command', command on a manual job makes no sense
            warning: jobs/broken.pxu:3: job 'broken', field 'description', field should be marked as translatable
            advice: jobs/broken.pxu:1: job 'broken', field 'name', use 'id' and 'summary' instead of 'name'
            Validation of provider com.example:test has failed
            """))

    def test_info(self):
        """
        verify that ``info`` shows basic provider information
        """
        with TestIO() as test_io:
            self.tool.main(["info"])
        self.assertEqual(test_io.stdout, (
            "[Provider MetaData]\n"
            "\tname: com.example:test\n"
            "\tnamespace: com.example (derived from name)\n"
            "\tdescription: description\n"
            "\tversion: 1.0\n"
            "\tgettext domain: domain\n"
            "[Job Definitions]\n"
            "\tjob com.example::dummy, from jobs/jobs.pxu:1-5\n"
            "[Test Plans]\n"
            "\ttest plan com.example::test, from units/testplans.pxu:1-6\n"
            "[Other Units]\n"
            "\tfile bin/test.sh, role script\n"
            "\tfile data/test.dat, role data\n"
            "\tfile jobs/jobs.pxu, role unit-source\n"
            "\tfile units/testplans.pxu, role unit-source\n"
            "[Executables]\n"
            "\t'test.sh'\n"))

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.definition = self._create_definition(self.tmpdir)
        self.tool = ProviderManagerTool(self.definition)

    def _create_definition(self, tmpdir):
        os.mkdir(os.path.join(tmpdir, "jobs"))
        filename = os.path.join(tmpdir, "jobs", "jobs.pxu")
        with open(filename, "wt", encoding='UTF-8') as stream:
            print("id: dummy", file=stream)
            print("plugin: shell", file=stream)
            print("command: true", file=stream)
            print("estimated_duration: 10", file=stream)
            # NOTE: absence of summary is not reported? Bug?
            # print("_summary: A dummy job", file=stream)
            print("_description: This job is dummy", file=stream)
        os.mkdir(os.path.join(tmpdir, "units"))
        filename = os.path.join(tmpdir, "units", "testplans.pxu")
        with open(filename, "wt", encoding='UTF-8') as stream:
            print("unit: test plan", file=stream)
            print("id: test", file=stream)
            print("_name: Dummy Tests", file=stream)
            print("_description: All dummy tests", file=stream)
            print("estimated_duration: 10", file=stream)
            print("include: dummy", file=stream)
        os.mkdir(os.path.join(tmpdir, "data"))
        filename = os.path.join(tmpdir, "data", "test.dat")
        with open(filename, "wt", encoding='UTF-8') as stream:
            print("data", file=stream)
        os.mkdir(os.path.join(tmpdir, "bin"))
        filename = os.path.join(tmpdir, "bin", "test.sh")
        with open(filename, "wt", encoding='UTF-8') as stream:
            print("#!/bin/sh", file=stream)
            print(":", file=stream)
        os.chmod(filename, 0o755)
        os.mkdir(os.path.join(tmpdir, "src"))
        filename = os.path.join(tmpdir, "src", "hello.c")
        with open(filename, "wt", encoding='UTF-8') as stream:
            print("int main() { return 0; }", file=stream)
        definition = Provider1Definition()
        definition.location = tmpdir
        definition.name = "com.example:test"
        definition.version = "1.0"
        definition.description = "description"
        definition.gettext_domain = "domain"
        return definition

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    def assertFileContent(self, filename, content):
        """
        assert that a file has the specified content

        :param filename:
            name of the file to open
        :param content:
            expected text of the file
        """
        if os.path.isfile(filename):
            with open(filename, "rt", encoding="UTF-8") as stream:
                self.assertEqual(stream.read(), content)
        else:
            self.fail("The file {} didn't exist".format(filename))

    def assertTarballContent(self, tarball, member, content):
        """
        assert that a tarball has an entry with the specified content

        :param tarball:
            pathname of a tarball to open
        :param member:
            pathname of a member inside the tarball
        :param content:
            expected text of the extracted member
        """
        with tarfile.open(tarball, "r:*") as tar:
            with tempfile.TemporaryDirectory() as temp:
                tar.extract(member, temp)
                extracted = os.path.join(temp, member)
                with open(extracted, "rt", encoding="UTF-8") as stream:
                    self.assertEqual(stream.read(), content)

    def assertNoTarballContent(self, tarball, member):
        """
        assert that a tarball has no entry with the given name

        :param tarball:
            pathname of a tarball to open
        :param member:
            pathname of a member inside the tarball
        """
        with tarfile.open(tarball, "r:*") as tar:
            with self.assertRaises(KeyError):
                tar.getmember(member)


class ExtensionTests(TestCase):
    """
    Test cases for the manage_py_extension decorator
    """

    def setUp(self):
        self.saved = ProviderManagerTool._SUB_COMMANDS[:]

    def tearDown(self):
        ProviderManagerTool._SUB_COMMANDS[:] = self.saved

    def test_add_new_command(self):
        @manage_py_extension
        class NewCommand(ManageCommand):
            """
            Some new command
            """
        self.assertIn(NewCommand, ProviderManagerTool._SUB_COMMANDS)

    def test_replace_command(self):
        self.assertIn(InstallCommand, ProviderManagerTool._SUB_COMMANDS)

        @manage_py_extension
        class BetterInstallCommand(InstallCommand):
            """
            Improved version of an existing command
            """
        self.assertNotIn(InstallCommand, ProviderManagerTool._SUB_COMMANDS)
        self.assertIn(BetterInstallCommand, ProviderManagerTool._SUB_COMMANDS)
