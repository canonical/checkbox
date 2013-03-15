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


class IntegrationTests(TestCaseWithParameters):

    parameter_names = ('job_name',)

    def setUp(self):
        # session data are kept in XDG_CACHE_HOME/plainbox/.session
        # To avoid resuming a real session, we have to select a temporary
        # location instead
        self._sandbox = tempfile.mkdtemp()
        self._env = os.environ
        os.environ['XDG_CACHE_HOME'] = self._sandbox

    @classmethod
    def _gen_job_name_values(cls, package='plainbox', root='test-data/integration-tests/'):
        """
        Discover job names for jobs that we have reference data for

        All reference data should be dropped to
        ``plainbox/test-data/integration-tests/`` as a json file
        """
        for name in resource_listdir(package, root):
            resource_name = os.path.join(root, name)
            if resource_isdir(package, resource_name):
                for item in cls._gen_job_name_values(package, resource_name):
                    yield item
            elif resource_name.endswith('.json'):
                yield resource_name[len('test-data/integration-tests/'):-len('.json')]

    @classmethod
    def get_parameter_values(cls):
        """
        Implementation detail of TestCaseWithParameters

        Creates subsequent tuples for each job that has reference data
        """
        for job_name in cls._gen_job_name_values():
            yield (job_name,)

    def test_job_result(self):
        # Create a scratch directory so that we can save results there. The
        # shared directory is also used for running tests as some test jobs
        # leave junk around the current directory.
        with TemporaryDirectory() as scratch_dir:
            # Save results to results.json in the scratch directory
            actual_results_path = os.path.join(scratch_dir, 'results.json')
            # Redirect all standard IO so that the test is silent.
            # Run the script, having relocated to the scratch directory
            # Capture SystemExit that is always raised by main() so that
            # we can observe the return code as well.
            with TestIO(), TestCwd(scratch_dir),\
                    self.assertRaises(SystemExit) as call:
                main(['run', '-i', self.parameters.job_name,
                      '--output-format=json', '-o', actual_results_path])
            # Check the return code for correctness
            self.assertEqual(call.exception.args, (0,))
            # Load the actual results and keep them in memory
            with open(actual_results_path, encoding='UTF-8') as stream:
                actual_result = json.load(stream)
        # [ At this time TestIO and TemporaryDirectory are gone ]
        # Load the expected results and keep them in memory
        reference_path = resource_filename(
            "plainbox", "test-data/integration-tests/{}.json".format(self.parameters.job_name))
        with open(reference_path, encoding='UTF-8') as stream:
            expected_result = json.load(stream)
        # Check that results match expected values
        self.assertEqual(actual_result, expected_result)

    def tearDown(self):
        shutil.rmtree(self._sandbox)
        os.environ = self._env
