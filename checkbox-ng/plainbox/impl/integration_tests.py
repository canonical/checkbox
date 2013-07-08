# This file is part of Checkbox.
#
# Copyright 2012 Canonical Ltd.
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
:mod:`plainbox.impl.integration_tests` -- integration tests
===========================================================

.. warning::

    THIS MODULE DOES NOT HAVE STABLE PUBLIC API
"""

from tempfile import TemporaryDirectory
import json
import os
import shutil
import tempfile

from pkg_resources import resource_filename, resource_isdir, resource_listdir

from plainbox.impl.box import main
from plainbox.testing_utils.cwd import TestCwd
from plainbox.testing_utils.io import TestIO
from plainbox.testing_utils.testcases import TestCaseWithParameters
from plainbox.testing_utils.resource import ResourceCache


class IntegrationTests(TestCaseWithParameters):
    """
    Test cases for checking execution and outcome of checkbox jobs.
    Each test case is parametrized by the job name and execution "profile".

    The profile is simply a string that somehow characterizes where this test
    is applicable.
    """

    # XXX: we cannot use weak resource cache here because test parameters
    # iterate over methods first and then over actual scenarios so our cache
    # would constantly loose data. This might be fixable with a different
    # implementation of test parameters but that's not a low hanging fruit.
    cache = ResourceCache(weak=False)

    parameter_names = ('scenario_pathname',)

    def setUp(self):
        # session data are kept in XDG_CACHE_HOME/plainbox/.session
        # To avoid resuming a real session, we have to select a temporary
        # location instead
        self._sandbox = tempfile.mkdtemp()
        self._env = os.environ
        os.environ['XDG_CACHE_HOME'] = self._sandbox
        # Load the expected results and keep them in memory
        self.scenario_data = self.cache.get(
            key=('scenario_data', self.parameters.scenario_pathname),
            operation=lambda: load_scenario_data(
                self.parameters.scenario_pathname))
        # Skip tests that are not applicable for the current system
        self.skip_if_incompatible()
        # Execute the job and remember the results.
        (self.job_result, self.job_return_code, self.job_stdout,
         self.job_stderr) = self.cache.get(
             key=('job-run-artifacts', self.parameters.scenario_pathname),
             operation=lambda: execute_job(self.scenario_data['job_name']))

    def test_job_result(self):
        # Check that results match expected values
        self.assertEqual(self.job_result, self.scenario_data.get("result"))

    def test_job_return_code(self):
        # Check the return code for correctness
        self.assertEqual(self.job_return_code,
                         self.scenario_data.get("return_code", 0))

    def skip_if_incompatible(self):
        """
        Skip a job if it is incompatible with the current environment
        """
        if self.scenario_data.get('profile') != 'default':
            self.skipTest("not applicable for current profile")

    @classmethod
    def _discover_test_scenarios(cls, package='plainbox',
                                 dirname="/test-data/integration-tests/",
                                 extension=".json"):
        """
        Discover test scenarios.

        Generates special absolute pathnames to scenario files. All those paths
        are really relative to the plainbox package. Those pathnames are
        suitable for pkg_resources.resource_ functions.

        All reference data should be dropped to
        ``plainbox/test-data/integration-tests/`` as a json file
        """
        for name in resource_listdir(package, dirname):
            resource_pathname = os.path.join(dirname, name)
            if resource_isdir(package, resource_pathname):
                for item in cls._discover_test_scenarios(package,
                                                         resource_pathname,
                                                         extension):
                    yield item
            elif resource_pathname.endswith(extension):
                yield resource_pathname

    @classmethod
    def get_parameter_values(cls):
        """
        Implementation detail of TestCaseWithParameters

        Creates subsequent tuples for each job that has reference data
        """
        for scenario_pathname in cls._discover_test_scenarios():
            yield (scenario_pathname,)

    def tearDown(self):
        shutil.rmtree(self._sandbox)
        os.environ = self._env


def load_scenario_data(scenario_pathname):
    """
    Load and return scenario data.

    Data is loaded from a .json file located in the plainbox package
    directory. Individual files are named after the jobs they describe.
    """
    pathname = resource_filename("plainbox", scenario_pathname)
    with open(pathname, encoding='UTF-8') as stream:
        return json.load(stream)


def execute_job(job_name):
    """
    Execute the specified job.

    The job is invoked using a high-level interface from box so the test will
    actually execute the same way as the UI would execute it. It will
    create/tear-down appropriate session objects as well.

    Returns (result, return_code) where result is the deserialized JSON saved
    at the end of the job.
    """
    # Create a scratch directory so that we can save results there. The
    # shared directory is also used for running tests as some test jobs
    # leave junk around the current directory.
    with TemporaryDirectory() as scratch_dir:
        # Save results to results.json in the scratch directory
        pathname = os.path.join(scratch_dir, 'results.json')
        # Redirect all standard IO so that the test is silent.
        # Run the script, having relocated to the scratch directory
        with TestIO() as io, TestCwd(scratch_dir):
            try:
                main(['run', '-i', job_name,
                      '--output-format=json', '-o', pathname])
            except SystemExit as exc:
                # Capture SystemExit that is always raised by main() so that we
                # can observe the return code as well.
                job_return_code = exc.args[0]
            else:
                job_return_code = None
        # Load the actual results and keep them in memory
        with open(pathname, encoding='UTF-8') as stream:
            job_result = json.load(stream)
    # [ At this time TestIO and TemporaryDirectory are gone ]
    return job_result, job_return_code, io.stdout, io.stderr
