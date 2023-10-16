#!/usr/bin/env python3
# Copyright 2023 Canonical Ltd.
# Written by:
#   Rick Wu <rickwu4444@canonical.com>
#   Patrick Chang <patrick.chang@canonical.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License version 3,
# as published by the Free Software Foundation.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import unittest
import subprocess
import io
import logging
from unittest import mock
import sys

from cpufreq_governors import CPUScalingInfo, CPUScalingTest


class TestCPUScalingTest(unittest.TestCase):
    @mock.patch('cpufreq_governors.CPUScalingInfo',
                return_value={})
    def setUp(self, mock_cpuscalinginfo):
        suppress_text = io.StringIO()
        sys.stdout = suppress_text
        logging.disable(logging.CRITICAL)
        # Create an instance of CPUScalingTest
        self.cpu_scaling_test = CPUScalingTest()

    @mock.patch('subprocess.run')
    def test_probe_governor_module_success(self, mock_subprocess_run):
        ''' Check if returns True while governor be probed successfully
        '''
        # Simulate a scenario governor module probe successfully.
        governor = "test_governor"
        mock_subprocess_run.returncode = 0
        status = self.cpu_scaling_test.probe_governor_module(governor)
        self.assertTrue(status)

    @mock.patch('subprocess.run')
    def test_probe_governor_module_fail(self, mock_subprocess_run):
        ''' Check if returns False while governor cannot be probed
        '''
        # Simulate a scenario where the governors module probed fail.
        # Create a mock subprocess.CompletedProcess object with a
        # return code of SystemError
        governor = "test_governor"
        cmd = ["modprobe", governor]
        mock_subprocess_run.side_effect = subprocess.CalledProcessError(
            returncode=1,
            cmd=cmd,
        )
        status = self.cpu_scaling_test.probe_governor_module(governor)
        self.assertFalse(status)

    @mock.patch('cpufreq_governors.CPUScalingInfo')
    def test_test_driver_detect_empty_cpu_policies(self, mock_cpuscalinginfo):
        ''' Check if returns False while no cpu policy found
        '''
        mock_cpuscalinginfo.return_value.cpu_policies = []
        instance = CPUScalingTest()
        result = instance.test_driver_detect()
        self.assertFalse(result)

    @mock.patch('cpufreq_governors.CPUScalingInfo')
    def test_test_driver_detect_single_policy(self, mock_cpuscalinginfo):
        ''' Check if returns True while one cpu policy found
        '''
        mock_cpuscalinginfo.return_value.cpu_policies = ['policy0']
        # Return 'fake' string as driver name
        mock_cpuscalinginfo.return_value.get_scaling_driver = lambda x: 'fake'
        instance = CPUScalingTest()
        result = instance.test_driver_detect()
        self.assertTrue(result)

    @mock.patch('cpufreq_governors.CPUScalingInfo')
    def test_test_driver_detect_multiple_policies(self, mock_cpuscalinginfo):
        ''' Check if returns True while multiple cpu policies found
        '''
        mock_cpuscalinginfo.return_value.cpu_policies = [
            'policy0', 'policy1']
        # Return 'fake' string as driver name
        mock_cpuscalinginfo.return_value.get_scaling_driver = lambda x: 'fake'
        instance = CPUScalingTest()
        result = instance.test_driver_detect()
        self.assertTrue(result)

    @mock.patch('cpufreq_governors.CPUScalingInfo')
    def test_test_driver_detect_no_driver(self, mock_cpuscalinginfo):
        ''' Check if returns False while no driver found
        '''
        mock_cpuscalinginfo.return_value.cpu_policies = ['policy0']
        mock_cpuscalinginfo.return_value.get_scaling_driver.return_value = []
        instance = CPUScalingTest()
        result = instance.test_driver_detect()
        self.assertFalse(result)

    @mock.patch('cpufreq_governors.CPUScalingInfo')
    def test_test_userspace_success(self, mock_cpuscalinginfo):
        ''' Check if CPU frequence can be set to the minimum and maximun while
            using Userspce Governor
        '''
        mock_cpuscalinginfo.return_value.governors = ['userspace']
        mock_cpuscalinginfo.return_value.cpu_policies = ['policy0']
        mock_cpuscalinginfo.return_value.set_governor = lambda *args: True
        minimum = 400000
        mock_cpuscalinginfo.return_value.min_freq = minimum
        maximum = 3600000
        mock_cpuscalinginfo.return_value.max_freq = maximum
        mock_cpuscalinginfo.return_value.get_policy_attribute.side_effect = [
            minimum, maximum]

        with self.assertLogs(level='DEBUG') as lc:
            # release stdout
            sys.stdout = sys.__stdout__
            logging.disable(logging.NOTSET)
            instance = CPUScalingTest()
            result = instance.test_userspace()
            # Expect True (Pass)
            self.assertTrue(result)
            # Check stdout
            self.assertEqual(
                'INFO:root:-------------------------------------------------',
                lc.output[0]
            )
            self.assertEqual(
                'INFO:root:Running Userspace Governor Test', lc.output[1])
            self.assertEqual(
                'INFO:root:Setting governor to userspace', lc.output[2])
            self.assertEqual(
                'INFO:root:Setting CPU frequency to {} MHz'.format(
                    int(minimum / 1000)), lc.output[3])
            self.assertEqual(
                'INFO:root:Setting CPU frequency to {} MHz'.format(
                    int(maximum / 1000)), lc.output[4])
            self.assertEqual(
                'INFO:root:Userspace Governor Test: PASS', lc.output[5])
        # Supress stdout
        suppress_text = io.StringIO()
        sys.stdout = suppress_text
        logging.disable(logging.CRITICAL)

    @mock.patch('cpufreq_governors.CPUScalingInfo')
    def test_test_userspace_fails_to_set_as_minimum(self, mock_cpuscalinginfo):
        ''' Check if CPU frequence cannot be set to the minimum value while
            using Userspce Governor
        '''
        mock_cpuscalinginfo.return_value.governors = ['userspace']
        mock_cpuscalinginfo.return_value.cpu_policies = ['policy0']
        mock_cpuscalinginfo.return_value.set_governor = lambda *args: True
        minimum = 400000
        mock_cpuscalinginfo.return_value.min_freq = minimum
        maximum = 3600000
        mock_cpuscalinginfo.return_value.max_freq = maximum
        # Mock the current value is 800000 after setting minimux to be 400000
        mock_cpuscalinginfo.return_value.get_policy_attribute.side_effect = [
            800000, maximum]

        with self.assertLogs(level='DEBUG') as lc:
            # release stdout
            sys.stdout = sys.__stdout__
            logging.disable(logging.NOTSET)
            instance = CPUScalingTest()
            result = instance.test_userspace()
            # Expect False
            self.assertFalse(result)
            # Check stdout
            self.assertEqual(
                'INFO:root:-------------------------------------------------',
                lc.output[0]
            )
            self.assertEqual(
                'INFO:root:Running Userspace Governor Test', lc.output[1])
            self.assertEqual(
                'INFO:root:Setting governor to userspace', lc.output[2])
            self.assertEqual(
                'INFO:root:Setting CPU frequency to {} MHz'.format(
                    int(minimum / 1000)), lc.output[3])
            self.assertEqual(
                'ERROR:root:Could not verify that cpu frequency is set' +
                ' to the minimum value of {}'.format(minimum),
                lc.output[4])
            self.assertEqual(
                'INFO:root:Setting CPU frequency to {} MHz'.format(
                    int(maximum / 1000)), lc.output[5])

        # Supress stdout
        suppress_text = io.StringIO()
        sys.stdout = suppress_text
        logging.disable(logging.CRITICAL)

    @mock.patch('cpufreq_governors.CPUScalingInfo')
    def test_test_userspace_fails_to_set_as_maximum(self, mock_cpuscalinginfo):
        ''' Check if CPU frequence cannot be set to the maximum value while
            using Userspce Governor
        '''
        mock_cpuscalinginfo.return_value.governors = ['userspace']
        mock_cpuscalinginfo.return_value.cpu_policies = ['policy0']
        mock_cpuscalinginfo.return_value.set_governor = lambda *args: True
        minimum = 400000
        mock_cpuscalinginfo.return_value.min_freq = 400000
        maximum = 3600000
        mock_cpuscalinginfo.return_value.max_freq = maximum
        # Mock the current value is 2500000 after setting maximum to be 3600000
        mock_cpuscalinginfo.return_value.get_policy_attribute.side_effect = [
            minimum, 2500000]

        with self.assertLogs(level='DEBUG') as lc:
            # release stdout
            sys.stdout = sys.__stdout__
            logging.disable(logging.NOTSET)
            instance = CPUScalingTest()
            result = instance.test_userspace()
            # Expect False
            self.assertFalse(result)
            # Check stdout
            self.assertEqual(
                'INFO:root:-------------------------------------------------',
                lc.output[0]
            )
            self.assertEqual(
                'INFO:root:Running Userspace Governor Test', lc.output[1])
            self.assertEqual(
                'INFO:root:Setting governor to userspace', lc.output[2])
            self.assertEqual(
                'INFO:root:Setting CPU frequency to {} MHz'.format(
                    int(minimum / 1000)), lc.output[3])
            self.assertEqual(
                'INFO:root:Setting CPU frequency to {} MHz'.format(
                    int(maximum / 1000)), lc.output[4])
            self.assertEqual(
                'ERROR:root:Could not verify that cpu frequency is set' +
                ' to the maximum value of {}'.format(maximum),
                lc.output[5])

        # Supress stdout
        suppress_text = io.StringIO()
        sys.stdout = suppress_text
        logging.disable(logging.CRITICAL)

    @mock.patch('cpufreq_governors.CPUScalingInfo')
    def test_test_performance_success(self, mock_cpuscalinginfo):
        ''' Check if CPU frequence is close to the maximum value (>99%) while
            using Performance Governor
        '''
        mock_cpuscalinginfo.return_value.governors = ['performance']
        mock_cpuscalinginfo.return_value.cpu_policies = ['policy0']
        mock_cpuscalinginfo.return_value.set_governor = lambda *args: True
        maximum = 3600000
        mock_cpuscalinginfo.return_value.max_freq = maximum
        # Mock the value of current frequency overs 99% of maximum
        mock_cpuscalinginfo.return_value.get_policy_attribute.return_value = (
            0.995 * float(maximum))

        with self.assertLogs(level='DEBUG') as lc:
            # release stdout
            sys.stdout = sys.__stdout__
            logging.disable(logging.NOTSET)
            instance = CPUScalingTest()
            result = instance.test_performance()
            # Expect True (Pass)
            self.assertTrue(result)
            # Check stdout
            self.assertEqual(
                'INFO:root:-------------------------------------------------',
                lc.output[0]
            )
            self.assertEqual(
                'INFO:root:Running Performance Governor Test', lc.output[1])
            self.assertEqual(
                'INFO:root:Setting governor to performance', lc.output[2])
            self.assertEqual(
                'DEBUG:root:Verifying current CPU frequency' +
                ' {} is close to max frequency'.format(
                    int(0.995 * float(maximum))),
                lc.output[3]
            )
            self.assertEqual(
                'INFO:root:Performance Governor Test: PASS', lc.output[4])
        # Supress stdout
        suppress_text = io.StringIO()
        sys.stdout = suppress_text
        logging.disable(logging.CRITICAL)

    @mock.patch('cpufreq_governors.CPUScalingInfo')
    def test_test_performance_fails_to_close_maximum(
            self, mock_cpuscalinginfo):
        ''' Check if CPU frequence is not close to the maximum value (<99%)
            while using Performance Governor
        '''
        mock_cpuscalinginfo.return_value.governors = ['performance']
        mock_cpuscalinginfo.return_value.cpu_policies = ['policy0']
        mock_cpuscalinginfo.return_value.set_governor = lambda *args: True
        maximum = 3600000
        mock_cpuscalinginfo.return_value.max_freq = maximum
        # Mock the value of current frequency overs 99% of maximum
        mock_cpuscalinginfo.return_value.get_policy_attribute.return_value = (
            0.989 * float(maximum))

        with self.assertLogs(level='DEBUG') as lc:
            # release stdout
            sys.stdout = sys.__stdout__
            logging.disable(logging.NOTSET)
            instance = CPUScalingTest()
            result = instance.test_performance()
            # Expect False
            self.assertFalse(result)
            # Check stdout
            self.assertEqual(
                'INFO:root:-------------------------------------------------',
                lc.output[0]
            )
            self.assertEqual(
                'INFO:root:Running Performance Governor Test', lc.output[1])
            self.assertEqual(
                'INFO:root:Setting governor to performance', lc.output[2])
            self.assertEqual(
                'DEBUG:root:Verifying current CPU frequency' +
                ' {} is close to max frequency'.format(
                    int(0.989 * float(maximum))),
                lc.output[3]
            )
            self.assertEqual(
                'ERROR:root:Current cpu frequency of' +
                ' {} is not close'.format(int(0.989 * float(maximum))) +
                ' enough to the maximum value of {}'.format(maximum),
                lc.output[4]
            )
        # Supress stdout
        suppress_text = io.StringIO()
        sys.stdout = suppress_text
        logging.disable(logging.CRITICAL)

    @mock.patch('cpufreq_governors.CPUScalingInfo')
    def test_test_powersave_success(self, mock_cpuscalinginfo):
        ''' Check if current CPU frequence is very close to the minimum value
            while using Powersave Governor
        '''
        mock_cpuscalinginfo.return_value.governors = ['powersave']
        mock_cpuscalinginfo.return_value.cpu_policies = ['policy0']
        mock_cpuscalinginfo.return_value.set_governor = lambda *args: True
        minimum = 400000
        mock_cpuscalinginfo.return_value.min_freq = minimum
        # Mock the value of current frequency is over the minimum a little
        mock_cpuscalinginfo.return_value.get_policy_attribute.return_value = (
            float(minimum) * 100 / 99)

        with self.assertLogs(level='DEBUG') as lc:
            # release stdout
            sys.stdout = sys.__stdout__
            logging.disable(logging.NOTSET)
            instance = CPUScalingTest()
            result = instance.test_powersave()
            # Expect True (Pass)
            self.assertTrue(result)
            # Check stdout
            self.assertEqual(
                'INFO:root:-------------------------------------------------',
                lc.output[0]
            )
            self.assertEqual(
                'INFO:root:Running Powersave Governor Test', lc.output[1])
            self.assertEqual(
                'INFO:root:Setting governor to powersave', lc.output[2])
            self.assertEqual(
                'DEBUG:root:Verifying current CPU frequency' +
                ' {} is close to min frequency'.format(
                    int(float(minimum) * 100 / 99)),
                lc.output[3]
            )
            self.assertEqual(
                'INFO:root:Powersave Governor Test: PASS', lc.output[4])
        # Supress stdout
        suppress_text = io.StringIO()
        sys.stdout = suppress_text
        logging.disable(logging.CRITICAL)

    @mock.patch('cpufreq_governors.CPUScalingInfo')
    def test_test_powersave_fails_to_close_minimum(self, mock_cpuscalinginfo):
        ''' Check if current CPU frequence is not very close to the minimum
            value while using Powersave Governor
        '''
        mock_cpuscalinginfo.return_value.governors = ['powersave']
        mock_cpuscalinginfo.return_value.cpu_policies = ['policy0']
        mock_cpuscalinginfo.return_value.set_governor = lambda *args: True
        minimum = 400000
        mock_cpuscalinginfo.return_value.min_freq = minimum
        # Mock the value of current frequency is over the minimum a little
        mock_cpuscalinginfo.return_value.get_policy_attribute.return_value = (
            float(minimum) * 100 / 98)

        with self.assertLogs(level='DEBUG') as lc:
            # release stdout
            sys.stdout = sys.__stdout__
            logging.disable(logging.NOTSET)
            instance = CPUScalingTest()
            result = instance.test_powersave()
            # Expect False
            self.assertFalse(result)
            # Check stdout
            self.assertEqual(
                'INFO:root:-------------------------------------------------',
                lc.output[0]
            )
            self.assertEqual(
                'INFO:root:Running Powersave Governor Test', lc.output[1])
            self.assertEqual(
                'INFO:root:Setting governor to powersave', lc.output[2])
            self.assertEqual(
                'DEBUG:root:Verifying current CPU frequency' +
                ' {} is close to min frequency'.format(
                    int(float(minimum) * 100 / 98)),
                lc.output[3]
            )
            self.assertEqual(
                'ERROR:root:Current cpu frequency of' +
                ' {} is not close'.format(int(float(minimum) * 100 / 98)) +
                ' enough to the minimum value of {}'.format(minimum),
                lc.output[4]
            )

        # Supress stdout
        suppress_text = io.StringIO()
        sys.stdout = suppress_text
        logging.disable(logging.CRITICAL)

    @mock.patch('time.sleep', return_value=None)
    @mock.patch(
        'cpufreq_governors.CPUScalingTest.stop_stress_cpus',
        return_value=None)
    @mock.patch(
        'cpufreq_governors.CPUScalingTest.stress_cpus', return_value=None)
    @mock.patch('cpufreq_governors.CPUScalingInfo')
    def test_test_ondemand_success(
        self,
        mock_cpuscalinginfo,
        mock_stress_cpus,
        mock_stop_stress_cpus,
        mock_time_sleep
    ):
        ''' Check if CPU frequence is able to be the maximun value while
            stressing CPU and then down to lower frequency after stopping
            stress and sleep for a while when using ondemand governor.
        '''
        mock_cpuscalinginfo.return_value.governors = ['ondemand']
        mock_cpuscalinginfo.return_value.cpu_policies = ['policy0']
        mock_cpuscalinginfo.return_value.set_governor.return_value = True
        mock_cpuscalinginfo.return_value.min_freq = 400000
        maximum = 3600000
        mock_cpuscalinginfo.return_value.max_freq = maximum
        # Mock the value of CPU frequency is maximum while stressing CPU, then
        # down to the 60% of maximun after stopping stress and sleep for a
        # while
        mock_cpuscalinginfo.return_value.get_policy_attribute.side_effect = [
            maximum, maximum * 0.6]

        with self.assertLogs(level='DEBUG') as lc:
            # release stdout
            sys.stdout = sys.__stdout__
            logging.disable(logging.NOTSET)
            instance = CPUScalingTest()
            result = instance.test_ondemand()
            # Expect True (Pass)
            self.assertTrue(result)
            # Check stdout
            self.assertEqual(
                'INFO:root:-------------------------------------------------',
                lc.output[0]
            )
            self.assertEqual(
                'INFO:root:Running Ondemand Governor Test on CPU policy0',
                lc.output[1])
            self.assertEqual(
                'INFO:root:Setting governor to ondemand', lc.output[2])
            self.assertEqual(
                'INFO:root:Stressing CPUs...', lc.output[3])
            self.assertEqual(
                'DEBUG:root:Current CPU frequency: {} MHz'.format(
                    maximum / 1000
                ), lc.output[4])
            self.assertEqual(
                'INFO:root:Verified current CPU frequency is equal to the' +
                ' max frequency', lc.output[5])
            self.assertEqual('INFO:root:Stop stressing CPUs...', lc.output[6])
            self.assertEqual(
                'DEBUG:root:Current CPU frequency: {} MHz'.format(
                    maximum * 0.6 / 1000
                ), lc.output[7])
            self.assertEqual(
                'INFO:root:Verified current CPU frequency has ' +
                'settled to a lower frequency', lc.output[8])

            self.assertEqual(
                'INFO:root:Ondemand Governor Test: PASS', lc.output[9])

        # Supress stdout
        suppress_text = io.StringIO()
        sys.stdout = suppress_text
        logging.disable(logging.CRITICAL)

    @mock.patch('time.sleep', return_value=None)
    @mock.patch(
        'cpufreq_governors.CPUScalingTest.stop_stress_cpus',
        return_value=None)
    @mock.patch(
        'cpufreq_governors.CPUScalingTest.stress_cpus', return_value=None)
    @mock.patch('cpufreq_governors.CPUScalingInfo')
    def test_test_ondemand_fails_to_increase_frequency(
        self,
        mock_cpuscalinginfo,
        mock_stress_cpus,
        mock_stop_stress_cpus,
        mock_time_sleep
    ):
        ''' Check if CPU frequence is unable to be incresed to the maximun
            value after stressing CPU while using ondemand governor.
        '''
        mock_cpuscalinginfo.return_value.governors = ['ondemand']
        mock_cpuscalinginfo.return_value.cpu_policies = ['policy0']
        mock_cpuscalinginfo.return_value.set_governor.return_value = True
        mock_cpuscalinginfo.return_value.min_freq = 400000
        maximum = 3600000
        mock_cpuscalinginfo.return_value.max_freq = maximum
        # Mock the value of CPU frequency is not maximum even stress the CPU
        # Set the second value to be same as origin since the value is not
        # increased, we assume it's broken.
        mock_cpuscalinginfo.return_value.get_policy_attribute.side_effect = [
            maximum * 0.6, maximum * 0.6]

        with self.assertLogs(level='DEBUG') as lc:
            # release stdout
            sys.stdout = sys.__stdout__
            logging.disable(logging.NOTSET)
            instance = CPUScalingTest()
            result = instance.test_ondemand()
            # Expect False (Pass)
            self.assertFalse(result)
            # Check stdout
            self.assertEqual(
                'INFO:root:-------------------------------------------------',
                lc.output[0]
            )
            self.assertEqual(
                'INFO:root:Running Ondemand Governor Test on CPU policy0',
                lc.output[1])
            self.assertEqual(
                'INFO:root:Setting governor to ondemand', lc.output[2])
            self.assertEqual(
                'INFO:root:Stressing CPUs...', lc.output[3])
            self.assertEqual(
                'DEBUG:root:Current CPU frequency: {} MHz'.format(
                    maximum * 0.6 / 1000
                ), lc.output[4])
            self.assertEqual(
                'ERROR:root:Could not verify that cpu frequency has ' +
                'increased to the maximum value', lc.output[5])
            self.assertEqual('INFO:root:Stop stressing CPUs...', lc.output[6])
            self.assertEqual(
                'DEBUG:root:Current CPU frequency: {} MHz'.format(
                    maximum * 0.6 / 1000
                ), lc.output[7])
            self.assertEqual(
                'INFO:root:Verified current CPU frequency has ' +
                'settled to a lower frequency', lc.output[8])

        # Supress stdout
        suppress_text = io.StringIO()
        sys.stdout = suppress_text
        logging.disable(logging.CRITICAL)

    @mock.patch('time.sleep', return_value=None)
    @mock.patch(
        'cpufreq_governors.CPUScalingTest.stop_stress_cpus',
        return_value=None)
    @mock.patch(
        'cpufreq_governors.CPUScalingTest.stress_cpus', return_value=None)
    @mock.patch('cpufreq_governors.CPUScalingInfo')
    def test_test_ondemand_fails_to_decrease_frequency(
        self,
        mock_cpuscalinginfo,
        mock_stress_cpus,
        mock_stop_stress_cpus,
        mock_time_sleep
    ):
        ''' Check if CPU frequence is increased to the maximun value
            after stressing CPU but cannot be decreased even after stopping
            the stress and sleep for a while when using ondemand governor.
        '''
        mock_cpuscalinginfo.return_value.governors = ['ondemand']
        mock_cpuscalinginfo.return_value.cpu_policies = ['policy0']
        mock_cpuscalinginfo.return_value.set_governor.return_value = True
        mock_cpuscalinginfo.return_value.min_freq = 400000
        maximum = 3600000
        mock_cpuscalinginfo.return_value.max_freq = maximum
        # Mock the value of CPU frequency is to be maximum after stress the CPU
        # Set the second value to be same as maximum since the value is not
        # decreased, we assume it's broken.
        mock_cpuscalinginfo.return_value.get_policy_attribute.side_effect = [
            maximum, maximum]

        with self.assertLogs(level='DEBUG') as lc:
            # release stdout
            sys.stdout = sys.__stdout__
            logging.disable(logging.NOTSET)
            instance = CPUScalingTest()
            result = instance.test_ondemand()
            # Expect False (Pass)
            self.assertFalse(result)
            # Check stdout
            self.assertEqual(
                'INFO:root:-------------------------------------------------',
                lc.output[0]
            )
            self.assertEqual(
                'INFO:root:Running Ondemand Governor Test on CPU policy0',
                lc.output[1])
            self.assertEqual(
                'INFO:root:Setting governor to ondemand', lc.output[2])
            self.assertEqual(
                'INFO:root:Stressing CPUs...', lc.output[3])
            self.assertEqual(
                'DEBUG:root:Current CPU frequency: {} MHz'.format(
                    maximum / 1000
                ), lc.output[4])
            self.assertEqual(
                'INFO:root:Verified current CPU frequency is equal to the' +
                ' max frequency', lc.output[5])
            self.assertEqual('INFO:root:Stop stressing CPUs...', lc.output[6])
            self.assertEqual(
                'DEBUG:root:Current CPU frequency: {} MHz'.format(
                    maximum / 1000
                ), lc.output[7])
            self.assertEqual(
                'ERROR:root:Could not verify that cpu frequency has ' +
                'settled to a lower frequency', lc.output[8])

        # Supress stdout
        suppress_text = io.StringIO()
        sys.stdout = suppress_text
        logging.disable(logging.CRITICAL)

    @mock.patch('time.sleep', return_value=None)
    @mock.patch(
        'cpufreq_governors.CPUScalingTest.stop_stress_cpus',
        return_value=None)
    @mock.patch(
        'cpufreq_governors.CPUScalingTest.stress_cpus', return_value=None)
    @mock.patch('cpufreq_governors.CPUScalingInfo')
    def test_test_conservative_success(
        self,
        mock_cpuscalinginfo,
        mock_stress_cpus,
        mock_stop_stress_cpus,
        mock_time_sleep
    ):
        ''' Check if CPU frequence is able to be the maximun value while
            stressing CPU and then down to lower frequency after stopping
            stress and sleep for a while when using conservative governor.
        '''
        mock_cpuscalinginfo.return_value.governors = ['conservative']
        mock_cpuscalinginfo.return_value.cpu_policies = ['policy0']
        mock_cpuscalinginfo.return_value.set_governor.return_value = True
        mock_cpuscalinginfo.return_value.min_freq = 400000
        maximum = 3600000
        mock_cpuscalinginfo.return_value.max_freq = maximum
        # Mock the value of CPU frequency is maximum while stressing CPU, then
        # down to the 60% of maximun after stopping stress and sleep for a
        # while
        mock_cpuscalinginfo.return_value.get_policy_attribute.side_effect = [
            maximum, maximum * 0.6]

        with self.assertLogs(level='DEBUG') as lc:
            # release stdout
            sys.stdout = sys.__stdout__
            logging.disable(logging.NOTSET)
            instance = CPUScalingTest()
            result = instance.test_conservative()
            # Expect True (Pass)
            self.assertTrue(result)
            # Check stdout
            self.assertEqual(
                'INFO:root:-------------------------------------------------',
                lc.output[0]
            )
            self.assertEqual(
                'INFO:root:Running Conservative Governor Test on CPU policy0',
                lc.output[1])
            self.assertEqual(
                'INFO:root:Setting governor to conservative', lc.output[2])
            self.assertEqual(
                'INFO:root:Stressing CPUs...', lc.output[3])
            self.assertEqual(
                'DEBUG:root:Current CPU frequency: {} MHz'.format(
                    maximum / 1000
                ), lc.output[4])
            self.assertEqual(
                'INFO:root:Verified current CPU frequency is equal to the' +
                ' max frequency', lc.output[5])
            self.assertEqual('INFO:root:Stop stressing CPUs...', lc.output[6])
            self.assertEqual(
                'DEBUG:root:Current CPU frequency: {} MHz'.format(
                    maximum * 0.6 / 1000
                ), lc.output[7])
            self.assertEqual(
                'INFO:root:Verified current CPU frequency has ' +
                'settled to a lower frequency', lc.output[8])

            self.assertEqual(
                'INFO:root:Conservative Governor Test: PASS', lc.output[9])

        # Supress stdout
        suppress_text = io.StringIO()
        sys.stdout = suppress_text
        logging.disable(logging.CRITICAL)

    @mock.patch('time.sleep', return_value=None)
    @mock.patch(
        'cpufreq_governors.CPUScalingTest.stop_stress_cpus',
        return_value=None)
    @mock.patch(
        'cpufreq_governors.CPUScalingTest.stress_cpus', return_value=None)
    @mock.patch('cpufreq_governors.CPUScalingInfo')
    def test_test_conservative_fails_to_increase_frequency(
        self,
        mock_cpuscalinginfo,
        mock_stress_cpus,
        mock_stop_stress_cpus,
        mock_time_sleep
    ):
        ''' Check if CPU frequence is unable to be incresed to the maximun
            value after stressing CPU while using conservative governor.
        '''
        mock_cpuscalinginfo.return_value.governors = ['conservative']
        mock_cpuscalinginfo.return_value.cpu_policies = ['policy0']
        mock_cpuscalinginfo.return_value.set_governor.return_value = True
        mock_cpuscalinginfo.return_value.min_freq = 400000
        maximum = 3600000
        mock_cpuscalinginfo.return_value.max_freq = maximum
        # Mock the value of CPU frequency is not maximum even stress the CPU
        # Set the second value to be same as origin since the value is not
        # increased, we assume it's broken.
        mock_cpuscalinginfo.return_value.get_policy_attribute.side_effect = [
            maximum * 0.6, maximum * 0.6]

        with self.assertLogs(level='DEBUG') as lc:
            # release stdout
            sys.stdout = sys.__stdout__
            logging.disable(logging.NOTSET)
            instance = CPUScalingTest()
            result = instance.test_conservative()
            # Expect False (Pass)
            self.assertFalse(result)
            # Check stdout
            self.assertEqual(
                'INFO:root:-------------------------------------------------',
                lc.output[0]
            )
            self.assertEqual(
                'INFO:root:Running Conservative Governor Test on CPU policy0',
                lc.output[1])
            self.assertEqual(
                'INFO:root:Setting governor to conservative', lc.output[2])
            self.assertEqual(
                'INFO:root:Stressing CPUs...', lc.output[3])
            self.assertEqual(
                'DEBUG:root:Current CPU frequency: {} MHz'.format(
                    maximum * 0.6 / 1000
                ), lc.output[4])
            self.assertEqual(
                'ERROR:root:Could not verify that cpu frequency has ' +
                'increased to the maximum value', lc.output[5])
            self.assertEqual('INFO:root:Stop stressing CPUs...', lc.output[6])
            self.assertEqual(
                'DEBUG:root:Current CPU frequency: {} MHz'.format(
                    maximum * 0.6 / 1000
                ), lc.output[7])
            self.assertEqual(
                'INFO:root:Verified current CPU frequency has ' +
                'settled to a lower frequency', lc.output[8])

        # Supress stdout
        suppress_text = io.StringIO()
        sys.stdout = suppress_text
        logging.disable(logging.CRITICAL)

    @mock.patch('time.sleep', return_value=None)
    @mock.patch(
        'cpufreq_governors.CPUScalingTest.stop_stress_cpus',
        return_value=None)
    @mock.patch(
        'cpufreq_governors.CPUScalingTest.stress_cpus', return_value=None)
    @mock.patch('cpufreq_governors.CPUScalingInfo')
    def test_test_conservative_fails_to_decrease_frequency(
        self,
        mock_cpuscalinginfo,
        mock_stress_cpus,
        mock_stop_stress_cpus,
        mock_time_sleep
    ):
        ''' Check if CPU frequence is increased to the maximun value
            after stressing CPU but cannot be decreased even after stopping
            the stress and sleep for a while when using conservative governor.
        '''
        mock_cpuscalinginfo.return_value.governors = ['conservative']
        mock_cpuscalinginfo.return_value.cpu_policies = ['policy0']
        mock_cpuscalinginfo.return_value.set_governor.return_value = True
        mock_cpuscalinginfo.return_value.min_freq = 400000
        maximum = 3600000
        mock_cpuscalinginfo.return_value.max_freq = maximum
        # Mock the value of CPU frequency is to be maximum after stress the CPU
        # Set the second value to be same as maximum since the value is not
        # decreased, we assume it's broken.
        mock_cpuscalinginfo.return_value.get_policy_attribute.side_effect = [
            maximum, maximum]

        with self.assertLogs(level='DEBUG') as lc:
            # release stdout
            sys.stdout = sys.__stdout__
            logging.disable(logging.NOTSET)
            instance = CPUScalingTest()
            result = instance.test_conservative()
            # Expect False (Pass)
            self.assertFalse(result)
            # Check stdout
            self.assertEqual(
                'INFO:root:-------------------------------------------------',
                lc.output[0]
            )
            self.assertEqual(
                'INFO:root:Running Conservative Governor Test on CPU policy0',
                lc.output[1])
            self.assertEqual(
                'INFO:root:Setting governor to conservative', lc.output[2])
            self.assertEqual(
                'INFO:root:Stressing CPUs...', lc.output[3])
            self.assertEqual(
                'DEBUG:root:Current CPU frequency: {} MHz'.format(
                    maximum / 1000
                ), lc.output[4])
            self.assertEqual(
                'INFO:root:Verified current CPU frequency is equal to the' +
                ' max frequency', lc.output[5])
            self.assertEqual('INFO:root:Stop stressing CPUs...', lc.output[6])
            self.assertEqual(
                'DEBUG:root:Current CPU frequency: {} MHz'.format(
                    maximum / 1000
                ), lc.output[7])
            self.assertEqual(
                'ERROR:root:Could not verify that cpu frequency has ' +
                'settled to a lower frequency', lc.output[8])

        # Supress stdout
        suppress_text = io.StringIO()
        sys.stdout = suppress_text
        logging.disable(logging.CRITICAL)

    @mock.patch('time.sleep', return_value=None)
    @mock.patch(
        'cpufreq_governors.CPUScalingTest.stop_stress_cpus',
        return_value=None)
    @mock.patch(
        'cpufreq_governors.CPUScalingTest.stress_cpus', return_value=None)
    @mock.patch('cpufreq_governors.CPUScalingInfo')
    def test_test_schedutil_success(
        self,
        mock_cpuscalinginfo,
        mock_stress_cpus,
        mock_stop_stress_cpus,
        mock_time_sleep
    ):
        ''' Check if CPU frequence is able to be the maximun value while
            stressing CPU and then down to lower frequency after stopping
            stress and sleep for a while when using schedutil governor.
        '''
        mock_cpuscalinginfo.return_value.governors = ['schedutil']
        mock_cpuscalinginfo.return_value.cpu_policies = ['policy0']
        mock_cpuscalinginfo.return_value.set_governor.return_value = True
        mock_cpuscalinginfo.return_value.min_freq = 400000
        maximum = 3600000
        mock_cpuscalinginfo.return_value.max_freq = maximum
        # Mock the value of CPU frequency is maximum while stressing CPU, then
        # down to the 60% of maximun after stopping stress and sleep for a
        # while
        mock_cpuscalinginfo.return_value.get_policy_attribute.side_effect = [
            maximum, maximum * 0.6]

        with self.assertLogs(level='DEBUG') as lc:
            # release stdout
            sys.stdout = sys.__stdout__
            logging.disable(logging.NOTSET)
            instance = CPUScalingTest()
            result = instance.test_schedutil()
            # Expect True (Pass)
            self.assertTrue(result)
            # Check stdout
            self.assertEqual(
                'INFO:root:-------------------------------------------------',
                lc.output[0]
            )
            self.assertEqual(
                'INFO:root:Running Schedutil Governor Test on CPU policy0',
                lc.output[1])
            self.assertEqual(
                'INFO:root:Setting governor to schedutil', lc.output[2])
            self.assertEqual(
                'INFO:root:Stressing CPUs...', lc.output[3])
            self.assertEqual(
                'DEBUG:root:Current CPU frequency: {} MHz'.format(
                    maximum / 1000
                ), lc.output[4])
            self.assertEqual(
                'INFO:root:Verified current CPU frequency is equal to the' +
                ' max frequency', lc.output[5])
            self.assertEqual('INFO:root:Stop stressing CPUs...', lc.output[6])
            self.assertEqual(
                'DEBUG:root:Current CPU frequency: {} MHz'.format(
                    maximum * 0.6 / 1000
                ), lc.output[7])
            self.assertEqual(
                'INFO:root:Verified current CPU frequency has ' +
                'settled to a lower frequency', lc.output[8])

            self.assertEqual(
                'INFO:root:Schedutil Governor Test: PASS', lc.output[9])

        # Supress stdout
        suppress_text = io.StringIO()
        sys.stdout = suppress_text
        logging.disable(logging.CRITICAL)

    @mock.patch('time.sleep', return_value=None)
    @mock.patch(
        'cpufreq_governors.CPUScalingTest.stop_stress_cpus',
        return_value=None)
    @mock.patch(
        'cpufreq_governors.CPUScalingTest.stress_cpus', return_value=None)
    @mock.patch('cpufreq_governors.CPUScalingInfo')
    def test_test_schedutil_fails_to_increase_frequency(
        self,
        mock_cpuscalinginfo,
        mock_stress_cpus,
        mock_stop_stress_cpus,
        mock_time_sleep
    ):
        ''' Check if CPU frequence is unable to be incresed to the maximun
            value after stressing CPU while using schedutil governor.
        '''
        mock_cpuscalinginfo.return_value.governors = ['schedutil']
        mock_cpuscalinginfo.return_value.cpu_policies = ['policy0']
        mock_cpuscalinginfo.return_value.set_governor.return_value = True
        mock_cpuscalinginfo.return_value.min_freq = 400000
        maximum = 3600000
        mock_cpuscalinginfo.return_value.max_freq = maximum
        # Mock the value of CPU frequency is not maximum even stress the CPU
        # Set the second value to be same as origin since the value is not
        # increased, we assume it's broken.
        mock_cpuscalinginfo.return_value.get_policy_attribute.side_effect = [
            maximum * 0.6, maximum * 0.6]

        with self.assertLogs(level='DEBUG') as lc:
            # release stdout
            sys.stdout = sys.__stdout__
            logging.disable(logging.NOTSET)
            instance = CPUScalingTest()
            result = instance.test_schedutil()
            # Expect False (Pass)
            self.assertFalse(result)
            # Check stdout
            self.assertEqual(
                'INFO:root:-------------------------------------------------',
                lc.output[0]
            )
            self.assertEqual(
                'INFO:root:Running Schedutil Governor Test on CPU policy0',
                lc.output[1])
            self.assertEqual(
                'INFO:root:Setting governor to schedutil', lc.output[2])
            self.assertEqual(
                'INFO:root:Stressing CPUs...', lc.output[3])
            self.assertEqual(
                'DEBUG:root:Current CPU frequency: {} MHz'.format(
                    maximum * 0.6 / 1000
                ), lc.output[4])
            self.assertEqual(
                'ERROR:root:Could not verify that cpu frequency has ' +
                'increased to the maximum value', lc.output[5])
            self.assertEqual('INFO:root:Stop stressing CPUs...', lc.output[6])
            self.assertEqual(
                'DEBUG:root:Current CPU frequency: {} MHz'.format(
                    maximum * 0.6 / 1000
                ), lc.output[7])
            self.assertEqual(
                'INFO:root:Verified current CPU frequency has ' +
                'settled to a lower frequency', lc.output[8])

        # Supress stdout
        suppress_text = io.StringIO()
        sys.stdout = suppress_text
        logging.disable(logging.CRITICAL)

    @mock.patch('time.sleep', return_value=None)
    @mock.patch(
        'cpufreq_governors.CPUScalingTest.stop_stress_cpus',
        return_value=None)
    @mock.patch(
        'cpufreq_governors.CPUScalingTest.stress_cpus', return_value=None)
    @mock.patch('cpufreq_governors.CPUScalingInfo')
    def test_test_schedutil_fails_to_decrease_frequency(
        self,
        mock_cpuscalinginfo,
        mock_stress_cpus,
        mock_stop_stress_cpus,
        mock_time_sleep
    ):
        ''' Check if CPU frequence is increased to the maximun value
            after stressing CPU but cannot be decreased even after stopping
            the stress and sleep for a while when using schedutil governor.
        '''
        mock_cpuscalinginfo.return_value.governors = ['schedutil']
        mock_cpuscalinginfo.return_value.cpu_policies = ['policy0']
        mock_cpuscalinginfo.return_value.set_governor.return_value = True
        mock_cpuscalinginfo.return_value.min_freq = 400000
        maximum = 3600000
        mock_cpuscalinginfo.return_value.max_freq = maximum
        # Mock the value of CPU frequency is to be maximum after stress the CPU
        # Set the second value to be same as maximum since the value is not
        # decreased, we assume it's broken.
        mock_cpuscalinginfo.return_value.get_policy_attribute.side_effect = [
            maximum, maximum]

        with self.assertLogs(level='DEBUG') as lc:
            # release stdout
            sys.stdout = sys.__stdout__
            logging.disable(logging.NOTSET)
            instance = CPUScalingTest()
            result = instance.test_schedutil()
            # Expect False (Pass)
            self.assertFalse(result)
            # Check stdout
            self.assertEqual(
                'INFO:root:-------------------------------------------------',
                lc.output[0]
            )
            self.assertEqual(
                'INFO:root:Running Schedutil Governor Test on CPU policy0',
                lc.output[1])
            self.assertEqual(
                'INFO:root:Setting governor to schedutil', lc.output[2])
            self.assertEqual(
                'INFO:root:Stressing CPUs...', lc.output[3])
            self.assertEqual(
                'DEBUG:root:Current CPU frequency: {} MHz'.format(
                    maximum / 1000
                ), lc.output[4])
            self.assertEqual(
                'INFO:root:Verified current CPU frequency is equal to the' +
                ' max frequency', lc.output[5])
            self.assertEqual('INFO:root:Stop stressing CPUs...', lc.output[6])
            self.assertEqual(
                'DEBUG:root:Current CPU frequency: {} MHz'.format(
                    maximum / 1000
                ), lc.output[7])
            self.assertEqual(
                'ERROR:root:Could not verify that cpu frequency has ' +
                'settled to a lower frequency', lc.output[8])

        # Supress stdout
        suppress_text = io.StringIO()
        sys.stdout = suppress_text
        logging.disable(logging.CRITICAL)

    def tearDown(self):
        # release stdout
        sys.stdout = sys.__stdout__
        logging.disable(logging.NOTSET)


class TestCPUScalingInfo(unittest.TestCase):
    @mock.patch('cpufreq_governors.CPUScalingInfo.__init__',
                return_value=None)
    def setUp(self,
              mock_init):
        suppress_text = io.StringIO()
        sys.stdout = suppress_text
        logging.disable(logging.CRITICAL)
        CPUScalingInfo.__init__ = mock_init
        # Create an instance of CPUScalingInfo
        self.cpu_scaling_info = CPUScalingInfo()
        self.cpu_scaling_info.sys_cpu_dir = "/sys/devices/system/cpu"

    @mock.patch('os.listdir')
    def test_get_cpu_policies_success(self, mock_listdir):
        ''' Check if a sorted list contains cpu policy number can be returned
            while policies exist.
        '''
        # Mock the listdir function to return a list of CPU policies
        mock_listdir.return_value = ["policy0", "policy1", "policy2"]
        # Call the get_cpu_policies function
        policies = self.cpu_scaling_info.get_cpu_policies()

        # Assert that the function returns the expected list of policies
        self.assertEqual(policies, [0, 1, 2])

    @mock.patch('os.listdir')
    def test_get_cpu_policies_failure(self, mock_listdir):
        ''' Check if an empty list be returned while OSError
        '''
        # Mock the listdir function to raise an OSError
        mock_listdir.side_effect = OSError("OSError")
        result = self.cpu_scaling_info.get_cpu_policies()
        self.assertEqual(result, [])

    @mock.patch('os.listdir')
    def test_get_cpu_policies_failure_empty(self, mock_listdir):
        ''' Check if an empty list be returned while no policy exists
        '''
        # Mock the listdir function to return an empty list
        mock_listdir.return_value = []
        result = self.cpu_scaling_info.get_cpu_policies()
        self.assertEqual(result, [])

    @mock.patch('builtins.open', mock.mock_open(read_data='Driver'))
    def test_get_scaling_driver_success(self):
        ''' Check if the name of driver be returned
        '''
        # Mock the open function to return a scaling driver
        result = self.cpu_scaling_info.get_scaling_driver()
        self.assertEqual(result, "Driver")

    @mock.patch('builtins.open', side_effect=OSError)
    def test_get_scaling_driver_oserror(self, mock_open):
        ''' Check if an empty string be returned while OSError
        '''
        # Mock the open function to raise an OSError
        result = self.cpu_scaling_info.get_scaling_driver()
        self.assertEqual(result, "")

    @mock.patch('builtins.open', mock.mock_open(read_data='Attribute_Value'))
    def test_get_attribute_success(self):
        ''' Check if get_attribute gets the contain of specific node
        '''
        # Mock the open function to return a attribute value
        result = self.cpu_scaling_info.get_attribute("Attribute")
        self.assertEqual(result, "Attribute_Value")

    @mock.patch('builtins.open', side_effect=OSError)
    def test_get_attribute_oserror(self, mock_open):
        ''' Check if get_attribute gets an empty string while OSError occurs
        '''
        # Mock the open function to raise an OSError
        result = self.cpu_scaling_info.get_attribute("Attribute")
        self.assertEqual(result, "")

    @mock.patch('builtins.open', new_callable=mock.mock_open, create=True)
    def test_set_attribute_success(self, mock_open):
        ''' Check if returns True while setting a value to a specific node
        '''
        mock_file = mock_open.return_value
        result = self.cpu_scaling_info.set_attribute(
            'attribute_name',
            'new_value')
        mock_file.write.assert_called_once_with('new_value')
        self.assertTrue(result)

    @mock.patch('builtins.open', side_effect=PermissionError)
    def test_set_attribute_permissionerror(self, mock_open):
        ''' Check if returns False while PermissionError occurs
        '''
        # Mock the open function to raise an PermissionError
        result = self.cpu_scaling_info.set_attribute(
            'attribute_name',
            'new_value')
        self.assertFalse(result)

    @mock.patch('builtins.open', side_effect=OSError)
    def test_set_attribute_oserror(self, mock_open):
        ''' Check if returns False while OSError occurs
        '''
        # Mock the open function to raise an OSError
        result = self.cpu_scaling_info.set_attribute(
            'attribute_name',
            'new_value')
        self.assertFalse(result)

    def tearDown(self):
        # release stdout
        sys.stdout = sys.__stdout__
        logging.disable(logging.NOTSET)


if __name__ == '__main__':
    unittest.main()
