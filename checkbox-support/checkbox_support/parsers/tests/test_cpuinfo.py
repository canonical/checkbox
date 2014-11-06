#
# This file is part of Checkbox.
#
# Copyright 2014 Canonical Ltd.
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

from pkg_resources import resource_filename

from checkbox_support.parsers.cpuinfo import CpuinfoParser


class CpuinfoResult(object):

    def __init__(self):
        self.processors = []

    def setProcessor(self, device):
        self.processors.append(device)


class TestCpuinfoParser(TestCase):

    def setUp(self):
        self.cpu_attributes = ["platform",
                               "count",
                               "type",
                               "model",
                               "model_number",
                               "model_version",
                               "model_revision",
                               "cache",
                               "bogomips",
                               "speed",
                               "other"]

    def parse(self, name, machine):
        resource = 'parsers/tests/cpuinfo_data/{}.txt'.format(name)
        filename = resource_filename('checkbox_support', resource)
        with open(filename, 'rt', encoding='UTF-8') as stream:
            parser = CpuinfoParser(stream, machine)
            result = CpuinfoResult()
            parser.run(result)
        # Before returning, do basic sanity checks on processors
        self.sanity_checks(result.processors)
        return result

    def sanity_checks(self, processors):
        # ALL cpuinfo elements should comply with these checks.
        self.assertIsNotNone(processors)
        # Look at only the first processor
        processor = processors[0]
        # Check we have all required attributes and they are not empty
        for attr in self.cpu_attributes:
            self.assertIn(attr, processor.keys())
            self.assertTrue(processor[attr] is not None and
                            processor[attr] != "", "{} is empty".format(attr))
        # Check speed is an integer
        self.assertIsInstance(processor['speed'], int)

    def test_aarch64(self):
        # Note that we need to specify the file name (first parameter) and the
        # GNU identifier for the architecture. This mimics what the submission
        # parser does.
        cpuinforesult = self.parse("aarch64", "aarch64")
        processors = cpuinforesult.processors
        processor = processors[0]

        self.assertEqual(processor['type'], "Unspecified Server Cartridge")
        self.assertEqual(processor['count'], 8)
        self.assertEqual(processor['model'],
                         "AArch64 Processor rev 1 (aarch64)")
        self.assertEqual(processor['model_number'], '0x0')
        self.assertEqual(processor['model_revision'], '1')
        self.assertEqual(processor['model_version'], 'AArch64')
        self.assertEqual(processor['platform'], 'aarch64')
        self.assertEqual(processor['other'], 'fp asimd evtstrm')

    def test_ppc64el(self):
        # Note that we need to specify the file name (first parameter) and the
        # GNU identifier for the architecture. This mimics what the submission
        # parser does.
        cpuinforesult = self.parse("ppc64el", "ppc64el")
        processors = cpuinforesult.processors
        processor = processors[0]

        self.assertEqual(processor['type'], "pSeries")
        self.assertEqual(processor['count'], 1)
        self.assertEqual(processor['model'],
                         "POWER8E (raw), altivec supported")
        self.assertEqual(processor['model_number'],
                         'IBM pSeries (emulated by qemu)')
        self.assertEqual(processor['model_revision'], '2.0 ')
        self.assertEqual(processor['model_version'], 'pvr 004b 0200')
        self.assertEqual(processor['platform'], 'pSeries')
        self.assertEqual(processor['other'], 'emulated by qemu')
        self.assertEqual(processor['cache'], -1)
        self.assertEqual(processor['bogomips'], -1)
        self.assertEqual(processor['speed'], 3457)

    def test_amd64(self):
        cpuinforesult = self.parse("amd64", "x86_64")
        processors = cpuinforesult.processors
        processor = processors[0]

        # Check for specific values.
        self.assertEqual(processor['type'], "GenuineIntel")
        self.assertEqual(processor['count'], 4)
        self.assertEqual(processor['model'],
                         "Intel(R) Core(TM) i7-4500U CPU @ 1.80GHz")
        self.assertEqual(processor['bogomips'], 4789)
        self.assertEqual(processor['cache'], 4194304)
        self.assertEqual(processor['model_number'], '6')
        self.assertEqual(processor['model_revision'], '1')
        self.assertEqual(processor['model_version'], '69')
        self.assertEqual(processor['platform'], 'x86_64')
        self.assertEqual(processor['speed'], 1199)
        self.assertEqual(processor['other'],
                         'fpu vme de pse tsc msr pae mce cx8 apic sep mtrr '
                         'pge mca cmov pat pse36 clflush dts acpi mmx fxsr '
                         'sse sse2 ss ht tm pbe syscall nx pdpe1gb rdtscp '
                         'lm constant_tsc arch_perfmon pebs bts rep_good '
                         'nopl xtopology nonstop_tsc aperfmperf eagerfpu '
                         'pni pclmulqdq dtes64 monitor ds_cpl vmx est tm2 '
                         'ssse3 fma cx16 xtpr pdcm pcid sse4_1 sse4_2 movbe '
                         'popcnt tsc_deadline_timer aes xsave avx f16c '
                         'rdrand lahf_lm abm ida arat epb xsaveopt pln pts '
                         'dtherm tpr_shadow vnmi flexpriority ept vpid '
                         'fsgsbase tsc_adjust bmi1 avx2 smep bmi2 erms '
                         'invpcid')
