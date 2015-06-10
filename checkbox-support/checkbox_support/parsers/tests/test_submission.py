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

from unittest import TestCase
import os

from checkbox_support.parsers.submission import SubmissionParser


class SubmissionRun(object):

    def __init__(self, result=None):
        if result is None:
            self.result = {}
        else:
            self.result = result

    def setArchitectureState(self, architecture_state):
        self.result["architecture_state"] = architecture_state

    def setDistribution(self, **distribution):
        self.result["distribution"] = distribution

    def setPciSubsystemId(self, pci_subsys_id):
        self.result["pci_subsystem_id"] = pci_subsys_id

    def setMemoryState(self, **memory_state):
        self.result["memory_state"] = memory_state

    def setProcessorState(self, **processor_state):
        self.result["processor_state"] = processor_state

    def addModprobeInfo(self, module, options):
        self.result.setdefault('module_options', {})
        self.result['module_options'][module] = options

    def addModuleInfo(self, module, data):
        self.result.setdefault('modinfo', {})
        self.result['modinfo'][module] = data

    def setKernelCmdline(self, kernel_cmdline):
        self.result['kernel_cmdline'] = kernel_cmdline

    def addDkmsInfo(self, pkg, details):
        self.result.setdefault('dkms_info', {})
        self.result['dkms_info'][pkg] = details

    def addBuildstampInfo(self, data):
        self.result['buildstamp'] = data

    def addImageVersionInfo(self, key, data):
        self.result[key] = data

    def addBtoInfo(self, key, data):
        self.result.setdefault('bto_info', {})
        self.result['bto_info'][key] = data

    def addAttachment(self, **attachment):
        self.result.setdefault("attachments", [])
        self.result["attachments"].append(attachment)

    def addDeviceState(self, **device_state):
        self.result.setdefault("device_states", [])
        self.result["device_states"].append(device_state)

    def addRawDmiDeviceState(self, raw_dmi_device):
        self.result.setdefault("raw_dmi_devices", [])
        raw_dict = raw_dmi_device.raw_attributes
        raw_dict['category'] = raw_dmi_device.category
        self.result["raw_dmi_devices"].append(raw_dict)

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
        parser = SubmissionParser(fixture)
        parser.run(SubmissionRun, result=result, project=project)
        return result

    def test_non_ascii(self):
        """non-ascii chars in an info element shouldn't cause a crash."""
        result = self.getResult("submission_info_non_ascii.xml")
        self.assertTrue("attachments" in result)
        self.assertIn("Péeter", result["attachments"][0]['content'])

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

    def test_modprobe(self):
        """modprobe_attachment info element can contain options for drivers."""
        result = self.getResult("submission_info_modprobe.xml")
        self.assertTrue('module_options' in result)
        self.assertIn('snd-hda-intel', result['module_options'])
        # This driver has 3 options which were set in different lines
        # so we're testing option aggregation and correct collection.
        self.assertIn("jackpoll_ms=500",
                      result['module_options']['snd-hda-intel'])
        self.assertIn("beep_mode=1",
                      result['module_options']['snd-hda-intel'])
        self.assertIn("single_cmd=1",
                      result['module_options']['snd-hda-intel'])

    def test_kernel_cmdline(self):
        """a kernel commandline can be in a kernel_cmdline info element."""
        result = self.getResult("submission_info_kernel_cmdline.xml")
        self.assertTrue("kernel_cmdline" in result)
        self.assertIn("ro quiet splash video.use_native_backlight=1",
                      result["kernel_cmdline"])

    def test_device_dmidecode(self):
        """Device states can be in a dmidecode info element."""
        result = self.getResult("submission_info_dmidecode.xml")
        self.assertTrue("device_states" in result)
        self.assertEqual(len(result["device_states"]), 5)
        # Ensure the most relevant devices actually contain what we expect, and
        # not empty dictionaries/data with just categories.
        expected_devices = [{
            'bus_name': 'dmi',
            'category_name': 'BIOS',
            'driver_name': None,
            'path': '/devices/virtual/dmi/id/bios',
            'product_id': None,
            'product_name': 'A05',
            'subproduct_id': None,
            'subvendor_id': None,
            'vendor_id': None,
            'vendor_name': 'Dell Inc.'},
            {'bus_name': 'dmi',
             'category_name': 'SYSTEM',
             'driver_name': None,
             'path': '/devices/virtual/dmi/id/system',
             'product_id': None,
             'product_name': 'Latitude E4310',
             'subproduct_id': None,
             'subvendor_id': None,
             'vendor_id': None,
             'vendor_name': 'Dell Inc.'},
            {'bus_name': 'dmi',
             'category_name': 'BOARD',
             'driver_name': None,
             'path': '/devices/virtual/dmi/id/board',
             'product_id': None,
             'product_name': '0101BC',
             'subproduct_id': None,
             'subvendor_id': None,
             'vendor_id': None,
             'vendor_name': 'Dell Inc.'},
            {'bus_name': 'dmi',
             'category_name': 'CHASSIS',
             'driver_name': None,
             'path': '/devices/virtual/dmi/id/chassis',
             'product_id': None,
             'product_name': 'Laptop',
             'subproduct_id': None,
             'subvendor_id': None,
             'vendor_id': None,
             'vendor_name': 'Dell Inc.'},
            {'bus_name': 'dmi',
             'category_name': 'PROCESSOR',
             'driver_name': None,
             'path': '/devices/virtual/dmi/id/processor',
             'product_id': None,
             'product_name': 'Intel(R) Core(TM) i5 CPU       M 520  @ 2.40GH',
             'subproduct_id': None,
             'subvendor_id': None,
             'vendor_id': None,
             'vendor_name': 'Intel'}]
        for dev in expected_devices:
            self.assertIn(dev, result["device_states"])

    def test_device_dmidecode_raw(self):
        """
        Device states can be in a dmidecode info element.

        Also test that BIOS and SYSTEM items are exposed/added as "raw"
        dmi devices for full access to all attributes.
        """
        result = self.getResult("submission_info_dmidecode.xml")
        self.assertTrue("raw_dmi_devices" in result)
        # There are 5 DMI devices in total but only 2 should be added as
        # raw devices.
        self.assertEqual(len(result["raw_dmi_devices"]), 2)
        self.assertNotEqual(len(result["raw_dmi_devices"][0]), 1)
        for dev in [{
            'address': '0xF0000',
            'bios_revision': '4.6',
            'category': 'BIOS',
            'release_date': '11/20/2010',
            'rom_size': '1024 kB',
            'runtime_size': '64 kB',
            'vendor': 'Dell Inc.',
            'version': 'A05'},
            {'category': 'SYSTEM',
             'family': 'Not Specified',
             'name': 'Latitude E4310',
             'serial': '7BWHRK1',
             'uuid': '4C4C4544-0042-5710-8048-B7C04F524B31',
             'vendor': 'Dell Inc.',
             'version': '0001',
             'wake_up_type': 'Power Switch'}]:
            self.assertIn(dev, result['raw_dmi_devices'])

    def test_package_versions(self):
        """Package versions are in the packages element."""
        result = self.getResult("submission_packages.xml")
        self.assertTrue("package_versions" in result)
        self.assertEqual(len(result["package_versions"]), 1)

        package_version = result["package_versions"][0]
        self.assertEqual(package_version["name"], "accountsservice")
        self.assertEqual(package_version["version"], "0.6.21-6ubuntu2")

    def test_package_modaliases(self):
        """
        Modaliases information is in the packages element if a package
        contains it.
        """
        result = self.getResult("submission_packages_modaliases.xml")
        self.assertTrue("package_versions" in result)
        self.assertEqual(len(result["package_versions"]), 2)

        package = result["package_versions"][0]
        self.assertEqual(package["name"], "accountsservice")
        self.assertNotIn("modalias", package)

        package = result["package_versions"][1]
        self.assertEqual(package["name"], "a_package_with_modaliases")

        modalias = "nvidia_340(pci:v000010DEd000005E7sv*sd00000595bc03sc*i*)"
        self.assertEqual(package["modalias"], modalias)
        self.assertEqual(package["version"], "1.0-1-ubuntu1~bogus")

    def test_dkms_info(self):
        """
        DKMS (and packages with modalias) shown if dkms_info attachment
        exists.
        """
        result = self.getResult("submission_info_dkms.xml")
        self.assertTrue("dkms_info" in result)
        self.assertEqual(len(result["dkms_info"]), 8)
        self.maxDiff = None
        self.assertDictEqual(
            result["dkms_info"]['stella-keymaps'],
            {"dkms-status": "non-dkms",
             "architecture": "all",
             "depends": "stella-base-config",
             "description": "Keymaps on stella project\n This ",
             "installed-size": "41",
             "maintainer": "Franz Hsieh (Franz) <franz.hsieh@canonical.com>",
             "match_patterns": [
                 "oemalias:*"
             ],
             "modaliases": "stella_include(oemalias:*)",
             "package": "stella-keymaps",
             "priority": "optional",
             "section": "misc",
             "status": "install ok installed",
             "version": "0.1stella1"})
        self.assertDictEqual(
            result['dkms_info']['oem-audio-hda-daily-dkms'],
            {"arch": "x86_64",
             "dkms-status": "dkms",
             "dkms_name": "oem-audio-hda-daily",
             "dkms_ver": "0.201503121632~ubuntu14.04.1",
             "install_mods": {
                 "snd_hda_codec": [],
                 "snd_hda_codec_generic": [],
                 "snd_hda_codec_realtek": [],
                 "snd_hda_controller": [],
                 "snd_hda_intel": [
                     "pci:v00008086d*sv*sd*bc04sc03i00*",
                     "pci:v00008086d00009C20sv*sd*bc*sc*i*"
                 ]
             },
             "kernel_ver": "3.13.0-48-generic",
             "mods": [
                 "snd_hda_codec_analog",
                 "snd_hda_codec_idt",
                 "snd_hda_codec_cirrus",
                 "snd_hda_codec_generic",
                 "snd_hda_codec_via",
                 "snd_hda_codec_realtek",
                 "snd_hda_codec_ca0132",
                 "snd_hda_codec_hdmi",
                 "snd_hda_codec_ca0110",
                 "snd_hda_codec_si3054",
                 "snd_hda_intel",
                 "snd_hda_codec_conexant",
                 "snd_hda_codec",
                 "snd_hda_codec_cmedia",
                 "snd_hda_controller"
             ],
             "pkg": {
                 "architecture": "all",
                 "depends": "dkms (>= 1.95)",
                 "description": "HDA driver in DKMS format.",
                 "homepage": "https://code.launchpad.net/~ubuntu-audio-dev",
                 "installed-size": "1512",
                 "maintainer": "David H <david.h@canonical.com>",
                 "modaliases": "hwe(pci:v00001022d*sv*sd*bc04sc03i00*)",
                 "package": "oem-audio-hda-daily-dkms",
                 "priority": "extra",
                 "section": "devel",
                 "status": "install ok installed",
                 "version": "0.201503121632~ubuntu14.04.1"
             },
             "pkg_name": "oem-audio-hda-daily-dkms"})

    def test_pci_subsystem_id(self):
        """
        PCI subsystem ID for the first device can be extracted from
        an lspci_standard_config attachment
        """
        result = self.getResult("submission_info_lspci_standard_config.xml")
        self.assertTrue("pci_subsystem_id" in result)
        self.assertEqual(result["pci_subsystem_id"], "060a")

    def test_modinfo(self):
        """
        Modinfo information is in the modinfo element if
        there was an attachment with output from modinfo_attachment job.
        """
        result = self.getResult("submission_info_modinfo.xml")
        self.assertTrue("modinfo" in result)
        self.assertEqual(len(result['modinfo']), 2)

        self.assertIn("bbswitch", result['modinfo'])
        self.assertEqual('0.7', result['modinfo']['bbswitch']['version'])

        self.assertIn("ctr", result['modinfo'])
        self.assertEqual(['crypto-ctr', 'ctr', 'crypto-rfc3686', 'rfc3686'],
                         result['modinfo']['ctr']['alias'])

    def test_buildstamp(self):
        """
        test buildstamp attachment.

        Buildstamp is in the image_info element if there was a buildstamp
        attachment.
        """
        result = self.getResult("submission_info_image_info.xml")
        self.assertTrue("buildstamp" in result)
        self.assertEqual('somerville-trusty-amd64-osp1-20150512-0',
                         result['buildstamp'])

    def test_image_info(self):
        """
        test image_info attachment.

        We should have image versions in the image_info element if there was a
        recovery_info attachment.
        """
        result = self.getResult("submission_info_image_info.xml")
        self.assertTrue("image_version" in result)
        self.assertEqual('somerville-trusty-amd64-osp1-20150512-0',
                         result['image_version'])
        self.assertTrue("bto_version" in result)
        self.assertEqual(
            'A00_dell-bto-trusty-miramar-15-17-X01-iso-20150521-0.iso',
            result['bto_version'])

    def test_bto_info(self):
        """bto data if there was a bto.xml attachment."""
        result = self.getResult("submission_info_image_info.xml")
        self.assertTrue("bto_info" in result)
        self.assertDictEqual(
            {'base': 'somerville-trusty-amd64-osp1-iso-20150512-0.iso',
             'bootstrap': '1.36~somerville3',
             'driver': ['libcuda1-346_346.59-0ubuntu1somerville1_amd64.deb',
                        ('nvidia-libopencl1-346_346.59-0ubuntu1somerville1'
                         '_amd64.deb'),
                        'bbswitch-dkms_0.7-2ubuntu1_amd64.deb',
                        'config-prime-select-intel-all_0.6_all.deb',
                        'nvidia-prime_0.6.2_amd64.deb',
                        'screen-resolution-extra_0.17.1_all.deb',
                        'nvidia-346-uvm_346.59-0ubuntu1somerville1_amd64.deb',
                        'nvidia-346_346.59-0ubuntu1somerville1_amd64.deb',
                        'nvidia-settings_346.47-0somerville1_amd64.deb',
                        ('nvidia-opencl-icd-346_346.59-0ubuntu1somerville1'
                         '_amd64.deb'),
                        'libvdpau1_1.1-0somerville1_amd64.deb'],
             'generator': '1.24.3~somerville11',
             'iso': 'A00_dell-bto-trusty-miramar-15-17-X01-iso-20150521-0.iso',
             'ubiquity': '2.18.8.8kittyhawk1somerville3'},
            result['bto_info'])

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
