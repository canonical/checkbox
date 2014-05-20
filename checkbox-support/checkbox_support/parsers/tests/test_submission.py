# -*- coding: utf-8 -*-
#
# This file is part of Checkbox.
#
# Copyright 2012 Canonical Ltd.
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

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

from io import open
from unittest import TestCase
import os

from checkbox_support.parsers.submission import SubmissionParser


class SubmissionRun:

    def __init__(self, result=None):
        if result is None:
            self.result = {}
        else:
            self.result = result

    def setArchitectureState(self, architecture_state):
        self.result["architecture_state"] = architecture_state

    def setDistribution(self, **distribution):
        self.result["distribution"] = distribution

    def setMemoryState(self, **memory_state):
        self.result["memory_state"] = memory_state

    def setProcessorState(self, **processor_state):
        self.result["processor_state"] = processor_state

    def addAttachment(self, **attachment):
        self.result.setdefault("attachments", [])
        self.result["attachments"].append(attachment)

    def addDeviceState(self, **device_state):
        self.result.setdefault("device_states", [])
        self.result["device_states"].append(device_state)

    def addPackageVersion(self, **package_version):
        self.result.setdefault("package_versions", [])
        self.result["package_versions"].append(package_version)

    def addTestResult(self, **test_result):
        self.result.setdefault("test_results", [])
        self.result["test_results"].append(test_result)


class TestSubmissionParser(TestCase):

    def getResult(self, name, project="test"):
        result = {}
        fixture = os.path.join(os.path.dirname(__file__), "fixtures", name)
        with open(fixture) as stream:
            parser = SubmissionParser(stream)
            parser.run(SubmissionRun, result=result, project=project)
        return result

    def test_distribution(self):
        """Distribution information is in the lsbrelease element."""
        result = self.getResult("submission_lsbrelease.xml")
        self.assertTrue("distribution" in result)
        self.assertEqual(result["distribution"]["release"], "12.10")
        self.assertEqual(result["distribution"]["codename"], "quantal")
        self.assertEqual(result["distribution"]["distributor_id"], "Ubuntu")
        self.assertEqual(
            result["distribution"]["description"],
            "Ubuntu quantal (development branch)")

    def test_memory_info(self):
        """Memory state is in an info element."""
        result = self.getResult("submission_info_memory.xml")
        self.assertTrue("memory_state" in result)
        self.assertEqual(result["memory_state"]["total"], 2023460864)
        self.assertEqual(result["memory_state"]["swap"], 2067787776)

    def test_processor(self):
        """Processor information can be in a processors element."""
        result = self.getResult("submission_processors.xml")
        self.assertTrue("processor_state" in result)
        self.assertEqual(result["processor_state"]["bogomips"], 1197)
        self.assertEqual(result["processor_state"]["cache"], 1048576)
        self.assertEqual(result["processor_state"]["count"], 1)
        self.assertEqual(result["processor_state"]["make"], "GenuineIntel")
        self.assertEqual(
            result["processor_state"]["model"],
            "Intel(R) Pentium(R) M processor 1100MHz")
        self.assertEqual(result["processor_state"]["model_number"], "6")
        self.assertEqual(result["processor_state"]["model_revision"], "5")
        self.assertEqual(result["processor_state"]["model_version"], "9")
        self.assertEqual(
            result["processor_state"]["other"],
            """fpu vme de pse tsc msr mce cx8 apic sep mtrr pge mca cmov """
            """pat clflush dts acpi mmx fxsr sse sse2 tm pbe up bts est tm2""")
        self.assertEqual(result["processor_state"]["platform_name"], "i386")
        self.assertEqual(result["processor_state"]["speed"], 597)

    def test_processor_info(self):
        """Processor information can be in an info element."""
        result = self.getResult("submission_info_cpuinfo.xml")
        self.assertTrue("processor_state" in result)
        self.assertEqual(result["processor_state"]["bogomips"], 4788)
        self.assertEqual(result["processor_state"]["cache"], 3145728)
        self.assertEqual(result["processor_state"]["count"], 1)
        self.assertEqual(result["processor_state"]["make"], "GenuineIntel")
        self.assertEqual(
            result["processor_state"]["model"],
            "Intel(R) Core(TM) i5 CPU       M 520  @ 2.40GHz")
        self.assertEqual(result["processor_state"]["model_number"], "6")
        self.assertEqual(result["processor_state"]["model_revision"], "2")
        self.assertEqual(result["processor_state"]["model_version"], "37")
        self.assertEqual(
            result["processor_state"]["other"],
            """fpu vme de pse tsc msr pae mce cx8 apic sep mtrr pge mca """
            """cmov pat pse36 clflush dts acpi mmx fxsr sse sse2 ss ht tm """
            """pbe syscall nx rdtscp lm constant_tsc arch_perfmon pebs bts """
            """rep_good nopl xtopology nonstop_tsc aperfmperf pni pclmulqdq """
            """dtes64 monitor ds_cpl vmx smx est tm2 ssse3 cx16 xtpr pdcm """
            """sse4_1 sse4_2 popcnt aes lahf_lm ida arat dtherm tpr_shadow """
            """vnmi flexpriority ept vpid""")
        self.assertEqual(result["processor_state"]["platform_name"], "x86_64")
        self.assertEqual(result["processor_state"]["speed"], 1865)

    def test_attachments(self):
        """Attachments are in info elements."""
        result = self.getResult("submission_attachment.xml")
        self.assertTrue("attachments" in result)
        self.assertEqual(len(result["attachments"]), 1)

    def test_device_udev(self):
        """Device states can be in the udev element."""
        result = self.getResult("submission_udev.xml")
        self.assertTrue("device_states" in result)
        self.assertEqual(len(result["device_states"]), 80)

    def test_device_udev_armhf(self):
        """ Ensure that device states from udev are also obtained
        for an armhf device (see http://pad.lv/1214123). Udev data
        is from the pandaboard as used in the udevadm parser tests.
        """
        result = self.getResult("submission_udev_armhf.xml")
        self.assertTrue("device_states" in result)
        self.assertEqual(len(result["device_states"]), 14)

    def test_device_udevadm(self):
        """Device states can be in a udevadm info element."""
        result = self.getResult("submission_info_udevadm.xml")
        self.assertTrue("device_states" in result)
        self.assertEqual(len(result["device_states"]), 80)

    def test_device_dmidecode(self):
        """Device states can be in a dmidecode info element."""
        result = self.getResult("submission_info_dmidecode.xml")
        self.assertTrue("device_states" in result)
        self.assertEqual(len(result["device_states"]), 5)

    def test_package_versions(self):
        """Package versions are in the packages element."""
        result = self.getResult("submission_packages.xml")
        self.assertTrue("package_versions" in result)
        self.assertEqual(len(result["package_versions"]), 1)

        package_version = result["package_versions"][0]
        self.assertEqual(package_version["name"], "accountsservice")
        self.assertEqual(package_version["version"], "0.6.21-6ubuntu2")

    def test_test_results(self):
        """Test results are in the questions element."""
        result = self.getResult("submission_questions.xml")
        self.assertTrue("test_results" in result)
        self.assertEqual(len(result["test_results"]), 1)

        test_result = result["test_results"][0]
        self.assertEqual(
            test_result["name"], "audio/alsa_record_playback_external")
        self.assertEqual(test_result["output"], "")
        self.assertEqual(test_result["status"], "pass")
