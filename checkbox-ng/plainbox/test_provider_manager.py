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
import tarfile
import tempfile
import textwrap

from plainbox.impl.secure.providers.v1 import Provider1Definition
from plainbox.provider_manager import InstallCommand
from plainbox.provider_manager import ManageCommand
from plainbox.provider_manager import ProviderManagerTool
from plainbox.provider_manager import manage_py_extension
from plainbox.testing_utils.io import TestIO
from plainbox.vendor import mock


def inline_output(text):
    return textwrap.dedent(text).lstrip('\n')


class ProviderManagerToolTests(TestCase):
    """
    Unit tests for the ``./manage.py`` tool
    """

    maxDiff = None

    def test_help(self):
        """
        verify that ``manage.py --help`` works.
        """
        with TestIO() as test_io:
            with self.assertRaises(SystemExit):
                self.tool.main(["--help"])
        self.maxDiff = None
        self.assertEqual(
            test_io.stdout, inspect.cleandoc(
                """
                usage: manage.py [--help] [--version] [options]

                Per-provider management script

                positional arguments:
                  {info,validate,develop,install,sdist,i18n,build,clean,packaging}
                    info                display basic information about this provider
                    validate            perform various static analysis and validation
                    develop             install/remove this provider, only for development
                    install             install this provider in the system
                    sdist               create a source tarball
                    i18n                update, merge and build translation catalogs
                    build               build provider specific executables from source
                    clean               clean build results
                    packaging           generate packaging meta-data

                optional arguments:
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
                """) + '\n')

    def assert_common_flat_install(self, prefix="/foo"):
        filename = self.tmpdir + os.path.join(
            prefix, "share", "plainbox-providers-1",
            "2014.com.example.test.provider")
        content = (
            "[PlainBox Provider]\n"
            "description = description\n"
            "gettext_domain = domain\n"
            "location = {prefix}/lib/plainbox-providers-1/2014.com.example:test\n"
            "name = 2014.com.example:test\n"
            "version = 1.0\n"
            "\n".format(prefix=prefix))
        self.assertFileContent(filename, content)
        self.assertFileContent(
            self.tmpdir + os.path.join(
                prefix, "lib", "plainbox-providers-1", "2014.com.example:test",
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
                prefix, "lib", "plainbox-providers-1", "2014.com.example:test",
                "data", "test.dat"),
            "data\n")
        self.assertFileContent(
            self.tmpdir + os.path.join(
                prefix, "lib", "plainbox-providers-1", "2014.com.example:test",
                "bin", "test.sh"),
            "#!/bin/sh\n:\n")

    def test_install__flat(self):
        """
        verify that ``manage.py install --layout=flat`` works
        """
        self.tool.main(
            ["install", "--prefix=/foo", "--root={}".format(self.tmpdir)])
        self.assert_common_flat_install()
        self.assertFileContent(
            self.tmpdir + os.path.join("/foo", "lib", "plainbox-providers-1",
                                       "2014.com.example:test", "jobs",
                                       "jobs.pxu"),
            "id: dummy\n"
            "plugin: shell\n"
            "command: true\n"
            "estimated_duration: 10\n"
            "flags: preserve-locale\n"
            "_description: This job is dummy\n")

    def test_install__flat_partial(self):
        """
        verify that ``manage.py install --layout=flat`` works when some files
        are missing
        """
        shutil.rmtree(os.path.join(self.tmpdir, "jobs"))
        self.tool.main(
            ["install", "--prefix=/foo", "--root={}".format(self.tmpdir)])
        self.assert_common_flat_install()
        self.assertFalse(
            os.path.exists(self.tmpdir + os.path.join(
                "/foo", "lib", "plainbox-providers-1", "2014.com.example:test",
                "jobs", "jobs.pxu")))

    def assert_common_unix_install(self, prefix="/foo"):
        filename = self.tmpdir + os.path.join(
            prefix, "share", "plainbox-providers-1",
            "2014.com.example.test.provider")
        content = (
            "[PlainBox Provider]\n"
            "bin_dir = {prefix}/lib/2014.com.example:test/bin\n"
            "data_dir = {prefix}/share/2014.com.example:test/data\n"
            "description = description\n"
            "gettext_domain = domain\n"
            "jobs_dir = {prefix}/share/2014.com.example:test/jobs\n"
            "name = 2014.com.example:test\n"
            "units_dir = {prefix}/share/2014.com.example:test/units\n"
            "version = 1.0\n"
            "\n".format(prefix=prefix))
        self.assertFileContent(filename, content)
        self.assertFileContent(
            self.tmpdir + os.path.join(
                prefix, "share", "2014.com.example:test", "jobs", "jobs.pxu"),
            "id: dummy\n"
            "plugin: shell\n"
            "command: true\n"
            "estimated_duration: 10\n"
            "flags: preserve-locale\n"
            "_description: This job is dummy\n")
        self.assertFileContent(
            self.tmpdir + os.path.join(
                prefix, "share",  "2014.com.example:test", "units",
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
                prefix, "share", "2014.com.example:test", "data", "test.dat"),
            "data\n")
        self.assertFileContent(
            self.tmpdir + os.path.join(
                prefix, "lib", "2014.com.example:test", "bin", "test.sh"),
            "#!/bin/sh\n:\n")

    def test_install__unix(self):
        """
        verify that ``manage.py install --layout=unix`` works
        """
        self.tool.main(
            ["install", "--prefix=/foo", "--layout=unix",
             "--root={}".format(self.tmpdir)])
        self.assert_common_unix_install()

    def assert_common_sdist(self, tarball):
        self.assertTarballContent(
            tarball, "2014.com.example.test-1.0/units/testplans.pxu", (
                "unit: test plan\n"
                "id: test\n"
                "_name: Dummy Tests\n"
                "_description: All dummy tests\n"
                "estimated_duration: 10\n"
                "include: dummy\n"))
        self.assertTarballContent(
            tarball, "2014.com.example.test-1.0/data/test.dat", "data\n")
        self.assertTarballContent(
            tarball, "2014.com.example.test-1.0/bin/test.sh",
            "#!/bin/sh\n:\n")
        self.assertTarballContent(
            tarball, "2014.com.example.test-1.0/src/hello.c",
            "int main() { return 0; }\n")

    def test_sdist(self):
        """
        verify that ``manage.py sdist`` creates a proper tarball
        """
        self.tool.main(["sdist"])
        tarball = os.path.join(
            self.tmpdir, "dist", "2014.com.example.test-1.0.tar.gz")
        self.assertTarballContent(
            tarball, "2014.com.example.test-1.0/jobs/jobs.pxu",
            "id: dummy\n"
            "plugin: shell\n"
            "command: true\n"
            "estimated_duration: 10\n"
            "flags: preserve-locale\n"
            "_description: This job is dummy\n"
        )
        self.assert_common_sdist(tarball)

    def test_sdist__partial(self):
        """
        verify that ``manage.py sdist`` creates a proper tarball
        even if some files are missing
        """
        shutil.rmtree(os.path.join(self.tmpdir, "jobs"))
        self.tool.main(["sdist"])
        tarball = os.path.join(
            self.tmpdir, "dist", "2014.com.example.test-1.0.tar.gz")
        self.assertNoTarballContent(
            tarball, "2014.com.example.test-1.0/jobs/jobs.pxu")
        self.assert_common_sdist(tarball)

    def test_develop(self):
        """
        verify that ``manage.py develop`` creates a provider file
        """
        xdg_data_home = os.path.join(self.tmpdir, "xdg-data-home")
        filename = os.path.join(xdg_data_home, "plainbox-providers-1",
                                "2014.com.example.test.provider")
        content = (
            "[PlainBox Provider]\n"
            "description = description\n"
            "gettext_domain = domain\n"
            "location = {}\n"
            "name = 2014.com.example:test\n"
            "version = 1.0\n"
            "\n").format(self.tmpdir)
        with mock.patch.dict('os.environ', clear=True,
                             XDG_DATA_HOME=xdg_data_home):
            self.tool.main(["develop"])
        self.assertFileContent(filename, content)

    def test_develop__force(self):
        """
        verify that ``manage.py develop --force`` overwrites existing .provider
        file
        """
        xdg_data_home = os.path.join(self.tmpdir, "xdg-data-home")
        filename = os.path.join(xdg_data_home, "plainbox-providers-1",
                                "2014.com.example.test.provider")
        content = (
            "[PlainBox Provider]\n"
            "description = description\n"
            "gettext_domain = domain\n"
            "location = {}\n"
            "name = 2014.com.example:test\n"
            "version = 1.0\n"
            "\n").format(self.tmpdir)
        os.makedirs(os.path.dirname(filename))
        with open(filename, "wt") as stream:
            stream.write("should have been overwritten")
        with mock.patch.dict('os.environ', clear=True,
                             XDG_DATA_HOME=xdg_data_home):
            self.tool.main(["develop", "--force"])
        self.assertFileContent(filename, content)

    def test_develop__uninstall(self):
        """
        verify that ``manage.py develop --uninstall`` works
        """
        xdg_data_home = os.path.join(self.tmpdir, "xdg-data-home")
        filename = os.path.join(xdg_data_home, "plainbox-providers-1",
                                "2014.com.example.test.provider")
        os.makedirs(os.path.dirname(filename))
        with open(filename, "wt") as stream:
            stream.write("should have been removed")
        with mock.patch.dict('os.environ', clear=True,
                             XDG_DATA_HOME=xdg_data_home):
            self.tool.main(["develop", "--uninstall"])
        self.assertFalse(os.path.exists(filename))

    def test_validate(self):
        """
        verify that ``manage.py validate -N`` says everything is okay when it is
        """
        with TestIO() as test_io:
            self.tool.main(["validate", "-N"])
        self.assertEqual(test_io.stdout, inline_output(
            """
            The provider seems to be valid
            """))

    def test_validate__broken_missing_field(self):
        """
        verify that ./manage.py validate -N shows information about missing fields
        """
        filename = os.path.join(self.tmpdir, "jobs", "broken.pxu")
        with open(filename, "wt", encoding='UTF-8') as stream:
            print("id: broken", file=stream)
            print("plugin: shell", file=stream)
        with TestIO() as test_io:
            self.tool.main(["validate", "-N"])
        self.assertEqual(test_io.stdout, inline_output(
            """
            jobs/broken.pxu:1-2: error: job 'broken', field 'command', command is mandatory for non-manual jobs
            jobs/broken.pxu:1-2: advice: job 'broken', field 'description', all jobs should have a description field, or a set of purpose, steps and verification fields
            jobs/broken.pxu:1-2: advice: job 'broken', field 'estimated_duration', required field missing
            Validation of provider 2014.com.example:test has failed
            """))

    def test_validate__broken_wrong_field(self):
        """
        verify that ./manage.py validate -N shows information about incorrect
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
            jobs/broken.pxu:1-2: error: job 'broken', field 'command', command is mandatory for non-manual jobs
            jobs/broken.pxu:1-2: advice: job 'broken', field 'description', all jobs should have a description field, or a set of purpose, steps and verification fields
            jobs/broken.pxu:1-2: advice: job 'broken', field 'estimated_duration', required field missing
            jobs/broken.pxu:2: error: job 'broken', field 'plugin', valid values are: attachment, local, manual, qml, resource, shell, user-interact, user-interact-verify, user-verify
            Validation of provider 2014.com.example:test has failed
            """))

    def test_validate__broken_useless_field(self):
        """
        verify that ./manage.py validate -N shows information about useless field
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
            jobs/broken.pxu:4: warning: job 'broken', field 'command', command on a manual or qml job makes no sense
            jobs/broken.pxu:3: warning: job 'broken', field 'description', field should be marked as translatable
            jobs/broken.pxu:1-4: advice: job 'broken', field 'estimated_duration', required field missing
            jobs/broken.pxu:1-4: advice: job 'broken', field 'flags', please ensure that the command supports non-C locale then set the preserve-locale flag
            jobs/broken.pxu:1-4: advice: job 'broken', field 'purpose', please use purpose, steps, and verification fields. See http://plainbox.readthedocs.org/en/latest/author/faq.html#faq-2
            jobs/broken.pxu:1-4: advice: job 'broken', field 'steps', please use purpose, steps, and verification fields. See http://plainbox.readthedocs.org/en/latest/author/faq.html#faq-2
            jobs/broken.pxu:1-4: advice: job 'broken', field 'verification', please use purpose, steps, and verification fields. See http://plainbox.readthedocs.org/en/latest/author/faq.html#faq-2
            Validation of provider 2014.com.example:test has failed
            """))

    def test_validate__broken_deprecated_field(self):
        """
        verify that ./manage.py validate -N shows information about deprecated fields
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
            jobs/broken.pxu:4: warning: job 'broken', field 'command', command on a manual or qml job makes no sense
            jobs/broken.pxu:3: warning: job 'broken', field 'description', field should be marked as translatable
            jobs/broken.pxu:1-4: advice: job 'broken', field 'estimated_duration', required field missing
            jobs/broken.pxu:1-4: advice: job 'broken', field 'flags', please ensure that the command supports non-C locale then set the preserve-locale flag
            jobs/broken.pxu:1: advice: job 'broken', field 'name', use 'id' and 'summary' instead of 'name'
            jobs/broken.pxu:1-4: advice: job 'broken', field 'purpose', please use purpose, steps, and verification fields. See http://plainbox.readthedocs.org/en/latest/author/faq.html#faq-2
            jobs/broken.pxu:1-4: advice: job 'broken', field 'steps', please use purpose, steps, and verification fields. See http://plainbox.readthedocs.org/en/latest/author/faq.html#faq-2
            jobs/broken.pxu:1-4: advice: job 'broken', field 'verification', please use purpose, steps, and verification fields. See http://plainbox.readthedocs.org/en/latest/author/faq.html#faq-2
            Validation of provider 2014.com.example:test has failed
            """))

    def test_info(self):
        """
        verify that ./manage.py info shows basic provider information
        """
        with TestIO() as test_io:
            self.tool.main(["info"])
        self.assertEqual(test_io.stdout, (
            "[Provider MetaData]\n"
            "\tname: 2014.com.example:test\n"
            "\tnamespace: 2014.com.example (derived from name)\n"
            "\tdescription: description\n"
            "\tversion: 1.0\n"
            "\tgettext domain: domain\n"
            "[Job Definitions]\n"
            "\tjob 2014.com.example::dummy, from jobs/jobs.pxu:1-6\n"
            "[Test Plans]\n"
            "\ttest plan 2014.com.example::test, from units/testplans.pxu:1-6\n"
            "[Test Plans] (legacy)\n"
            "\ttest from units/testplans.pxu:1-6\n"
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
            print("flags: preserve-locale", file=stream)
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
        definition.name = "2014.com.example:test"
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
