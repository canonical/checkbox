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
:mod:`checkbox_support.parsers.tests.test_pactl` -- tests for pactl parser
==================================================================
"""

from math import log10, floor, ceil
from unittest import TestCase

from pkg_resources import resource_filename

from checkbox.parsers import pyparsing as p
from checkbox_support.parsers import pactl


class ParsingMixIn:
    """
    Mix-in class for writing tests that parse stuff.

    This mix-in adds the assertParse() method which displays helpful data in
    case of problems.
    """

    def parse(self, syntax, text):
        return syntax.parseString(text, parseAll=True)

    def assertParses(self, syntax, text):
        try:
            return self.parse(syntax, text)
        except p.ParseBaseException as exc:
            if hasattr(exc, 'col') and hasattr(exc, 'lineno'):
                lineno = exc.lineno
                col = exc.col
            else:
                lineno = p.lineno(exc.loc, text)
                col = p.col(exc.loc, text)
            print()
            print("Parse error on line {} column {}: {}".format(
                lineno, col, exc))
            self._show_text(text, lineno, col, context=3)
            raise

    def _show_text(self, text, hl_line=None, hl_col=None, context=None):
        """
        Show a body of text, with line and column markers.

        If both hl_line and hl_col are provided, they will be used
        to highlight the particular spot in the text.
        """
        lines = text.splitlines(True)
        if hl_line is not None and hl_col is not None and context is not None:
            window = slice(
                max(0, hl_line - context),
                min(hl_line + context, len(lines)))
        else:
            window = slice(0, len(lines))
        lines = lines[window]
        num_lines = len(lines)
        num_cols = max(len(line) for line in lines)
        col_lines_needed = floor(log10(num_cols))
        line_cols_needed = ceil(log10(window.start + num_lines))

        def print_col_ruler():
            for ndigit in range(col_lines_needed, -1, -1):
                print(" " * (line_cols_needed + 2), end='')
                print_it = False
                for colno in range(1, num_cols + 1):
                    digit = (colno // 10 ** ndigit) % 10
                    if digit > 0:
                        print_it = True
                    print(digit if print_it else ' ', end='')
                print("")
            print(" " * (line_cols_needed + 1) + "+-" + "-" * num_cols)
        print_col_ruler()
        for lineno, line in enumerate(lines, window.start + 1):
            print(("{:" + str(line_cols_needed) + "d} |").format(lineno),
                  end='')
            for c in line:
                if c.isprintable():
                    print(c, end='')
                elif c == '\t':
                    print('\x1B[33mT\x1B[0m', end='')
                elif c == '\n':
                    print('\x1B[32;1m\\n\x1B[0m', end='')
                else:
                    print('\x1B[33m%r\x1B[0m' % c, end='')
            print()
            if lineno == hl_line:
                print('\x1B[37;1m' + '_' * (line_cols_needed + 1) +
                      hl_col * '_' + '^\x1B[0m')


class PactlDataMixIn:
    """
    Mix in with a helper method to load sample pactl data
    """

    def get_text(self, name):
        resource = 'parsers/tests/pactl_data/{}.txt'.format(name)
        filename = resource_filename('checkbox', resource)
        with open(filename, 'rt', encoding='UTF-8') as stream:
            return stream.read()


class ParsingTestCase(TestCase, ParsingMixIn):
    """
    Vanilla TestCase with the ParsingMixIn class added
    """


class PropertyTests(ParsingTestCase):

    def test_smoke(self):
        prop = self.assertParses(
            pactl.Property.Syntax, 'device.vendor.name = "Intel Corporation"'
        )['property']
        self.assertEqual(prop.name, 'device.vendor.name')
        self.assertEqual(prop.value, 'Intel Corporation')

    def test_underscore(self):
        prop = self.assertParses(
            pactl.Property.Syntax, 'alsa.resolution_bits = "16"'
        )['property']
        self.assertEqual(prop.name, 'alsa.resolution_bits')
        self.assertEqual(prop.value, '16')

    def test_dash(self):
        prop = self.assertParses(
            pactl.Property.Syntax, 'module-udev-detect.discovered = "1"'
        )['property']
        self.assertEqual(prop.name, 'module-udev-detect.discovered')
        self.assertEqual(prop.value, '1')


class PortTests(ParsingTestCase):

    def test_port(self):
        port = self.assertParses(
            pactl.Port.Syntax, (
                'hdmi-output-1: HDMI / DisplayPort 2 (priority: 5800, available)')
        )['port']
        self.assertEqual(port.name, 'hdmi-output-1')
        self.assertEqual(port.label, 'HDMI / DisplayPort 2')
        self.assertEqual(port.priority, 5800)
        self.assertEqual(port.availability, 'available')

    def test_port_not_available(self):
        port = self.assertParses(
            pactl.Port.Syntax, (
                'analog-output-headphones: Słuchawki (priority: 9000, not available)')
        )['port']
        self.assertEqual(port.name, 'analog-output-headphones')
        self.assertEqual(port.label, 'Słuchawki')
        self.assertEqual(port.priority, 9000)
        self.assertEqual(port.availability, 'not available')

    def test_port_no_availability_info(self):
        port = self.assertParses(
            pactl.Port.Syntax, (
                'analog-output: Wyjście analogowe (priority: 9900)')
        )['port']
        self.assertEqual(port.name, 'analog-output')
        self.assertEqual(port.label, 'Wyjście analogowe')
        self.assertEqual(port.priority, 9900)
        self.assertEqual(port.availability, '')

    def test_chinese_label(self):
        port = self.assertParses(
            pactl.Port.Syntax, (
                'analog-output;output-amplifier-on: 模拟输出 / 均衡器 (priority: 9910)')
        )['port']
        self.assertEqual(port.name, 'analog-output;output-amplifier-on')
        self.assertEqual(port.label, '模拟输出 / 均衡器')
        self.assertEqual(port.priority, 9910)
        self.assertEqual(port.availability, '')


class ProfileTests(ParsingTestCase):

    def test_smoke(self):
        profiles = (
            'input:analog-stereo: Wejście Analogowe stereo (sinks: 0, sources: 1, priority. 60)',
            'off: Wyłącz (sinks: 0, sources: 0, priority. 0)',
            'output:analog-stereo+input:analog-stereo: Analogowy dupleks stereo (sinks: 1, sources: 1, priority. 6060)',
            'output:analog-stereo: Wyjście Analogowe stereo (sinks: 1, sources: 0, priority. 6000)',
            'output:analog-surround-40+input:analog-stereo: Wyjście Analogowe surround 4.0 + Wejście Analogowe stereo (sinks: 1, sources: 1, priority. 760)',
            'output:analog-surround-40: Wyjście Analogowe surround 4.0 (sinks: 1, sources: 0, priority. 700)',
            'output:analog-surround-41+input:analog-stereo: Wyjście Analogowe surround 4.1 + Wejście Analogowe stereo (sinks: 1, sources: 1, priority. 860)',
            'output:analog-surround-41: Wyjście Analogowe surround 4.1 (sinks: 1, sources: 0, priority. 800)',
            'output:analog-surround-50+input:analog-stereo: Wyjście Analogowe surround 5.0 + Wejście Analogowe stereo (sinks: 1, sources: 1, priority. 760)',
            'output:analog-surround-50: Wyjście Analogowe surround 5.0 (sinks: 1, sources: 0, priority. 700)',
            'output:analog-surround-51+input:analog-stereo: Wyjście Analogowe surround 5.1 + Wejście Analogowe stereo (sinks: 1, sources: 1, priority. 860)',
            'output:analog-surround-51: Wyjście Analogowe surround 5.1 (sinks: 1, sources: 0, priority. 800)',
            'output:analog-surround-71+input:analog-stereo: Wyjście Analog Surround 7.1 + Wejście Analogowe stereo (sinks: 1, sources: 1, priority. 760)',
            'output:analog-surround-71: Wyjście Analog Surround 7.1 (sinks: 1, sources: 0, priority. 700)',
            'output:hdmi-stereo-extra1: Wyjście Digital Stereo (HDMI) (sinks: 1, sources: 0, priority. 5200)',
            'output:hdmi-stereo-extra2: Wyjście Digital Stereo (HDMI) (sinks: 1, sources: 0, priority. 5200)',
            'output:hdmi-stereo: Wyjście Digital Stereo (HDMI) (sinks: 1, sources: 0, priority. 5400)',
            'output:hdmi-surround-extra2: Wyjście Digital Surround 5.1 (HDMI) (sinks: 1, sources: 0, priority. 100)',
            'output:hdmi-surround: Wyjście Digital Surround 5.1 (HDMI) (sinks: 1, sources: 0, priority. 300)',
            'output:iec958-stereo+input:analog-stereo: Wyjście Cyfrowe stereo (IEC958) + Wejście Analogowe stereo (sinks: 1, sources: 1, priority. 5560)',
            'output:iec958-stereo: Wyjście Cyfrowe stereo (IEC958) (sinks: 1, sources: 0, priority. 5500)',
        )
        for profile_text in profiles:
            profile = self.assertParses(
                pactl.Profile.Syntax, profile_text,
            )['profile']
            self.assertNotEqual(profile.name, "")
            self.assertNotEqual(profile.label, "")
            self.assertNotEqual(profile.sink_cnt, "")
            self.assertNotEqual(profile.source_cnt, "")

    def test_HDMI_in_label(self):
        # This checks that '(HDMI)' does not confuse the parser to parse
        # '(' before 'sinks'
        profile = self.assertParses(
            pactl.Profile.Syntax,
            'output:hdmi-stereo-extra1: Wyjście Digital Stereo (HDMI) (sinks: 1, sources: 0, priority. 5200)'
        )['profile']
        self.assertEqual(profile.name, "output:hdmi-stereo-extra1")
        self.assertEqual(profile.label, "Wyjście Digital Stereo (HDMI)")
        self.assertEqual(profile.sink_cnt, 1)
        self.assertEqual(profile.source_cnt, 0)
        self.assertEqual(profile.priority, 5200)

    def test_IEC985_in_label(self):
        # This checks that '(IEC985)' does not confuse the parser to parse
        # '(' before 'sinks'
        profile = self.assertParses(
            pactl.Profile.Syntax,
            'output:iec958-stereo: Wyjście Cyfrowe stereo (IEC958) (sinks: 1, sources: 0, priority. 5500)'
        )['profile']
        self.assertEqual(profile.name, "output:iec958-stereo")
        self.assertEqual(profile.label, "Wyjście Cyfrowe stereo (IEC958)")
        self.assertEqual(profile.sink_cnt, 1)
        self.assertEqual(profile.source_cnt, 0)
        self.assertEqual(profile.priority, 5500)
        self.assertNotEqual(profile.priority, "")

    def test_colon_after_priority(self):
        # This checks that : can be parsed correctly after priority
        profile = self.assertParses(
            pactl.Profile.Syntax,
            'output:hdmi-stereo-extra1: Wyjście Digital Stereo (HDMI) (sinks: 1, sources: 0, priority: 5800)'
        )['profile']
        self.assertEqual(profile.priority, 5800)


class AttributeTests(ParsingTestCase):

    def test_simple(self):
        attr = self.assertParses(
            pactl.GenericSimpleAttribute.Syntax,
            'Sample Specification: s16le 2ch 44100Hz'
        )['attribute']
        self.assertEqual(attr.name, 'Sample Specification')
        self.assertEqual(attr.value, 's16le 2ch 44100Hz')

    def test_leading_space(self):
        with self.assertRaises(p.ParseBaseException):
            self.parse(pactl.GenericSimpleAttribute.Syntax, ' attr: value')

    def test_empty_value(self):
        attr = self.assertParses(
            pactl.GenericSimpleAttribute.Syntax, 'Argument:'
        )['attribute']
        self.assertEqual(attr.name, 'Argument')
        self.assertEqual(attr.value, '')

    def test_properties(self):
        attr = self.assertParses(
            pactl.GenericListAttribute.Syntax, (
                'Properties:\n'
                '\talsa.resolution_bits = "16"\n'
                '\tdevice.api = "alsa"\n')
        )['attribute']
        self.assertEqual(attr.name, 'Properties')
        self.assertIsInstance(attr.value, list)
        self.assertIsInstance(attr.value[0], pactl.Property)
        self.assertIsInstance(attr.value[1], pactl.Property)
        self.assertEqual(attr.value[0].name, 'alsa.resolution_bits')
        self.assertEqual(attr.value[0].value, '16')
        self.assertEqual(attr.value[1].name, 'device.api')
        self.assertEqual(attr.value[1].value, 'alsa')

    def test_volume(self):
        # NOTE: both of those are a bit odd as they use spaces for the extra
        # indent. Most of the typical output uses tabs. Localized values have
        # incorrect, inconsistent, amount of space indents
        attr = self.assertParses(
            pactl.GenericSimpleAttribute.Syntax, (
                'Volume: 0:  60% 1:  60%\n'
                '        0: -13.40 dB 1: -13.40 dB\n'
                '        balance 0.00\n')
        )['attribute']
        self.assertEqual(attr.name, 'Volume')
        self.assertEqual(attr.value, (
            '0:  60% 1:  60%\n'
            '0: -13.40 dB 1: -13.40 dB\n'
            'balance 0.00\n'))

    def test_volume_with_tabs(self):
        attr = self.assertParses(
            pactl.GenericSimpleAttribute.Syntax, (
                '\tVolume: 0:  60% 1:  60%\n'
                '\t        0: -13.40 dB 1: -13.40 dB\n'
                '\t        balance 0.00\n')
        )['attribute']
        self.assertEqual(attr.name, 'Volume')
        self.assertEqual(attr.value, (
            '0:  60% 1:  60%\n'
            '0: -13.40 dB 1: -13.40 dB\n'
            'balance 0.00\n'))

    def test_base_volume(self):
        attr = self.assertParses(
            pactl.GenericSimpleAttribute.Syntax, (
                'Base Volume: 100%\n'
                '             0.00 dB\n')
        )['attribute']
        self.assertEqual(attr.name, 'Base Volume')
        self.assertEqual(attr.value, '100%\n0.00 dB\n')

    def test_one_port(self):
        attr = self.assertParses(
            pactl.GenericListAttribute.Syntax, (
                'Ports:\n'
                '\thdmi-output-1: HDMI / DisplayPort 2 (priority: 5800, available)\n')
        )['attribute']
        self.assertEqual(attr.name, 'Ports')
        self.assertEqual(attr.value[0].name, 'hdmi-output-1')
        self.assertEqual(attr.value[0].label, 'HDMI / DisplayPort 2')
        self.assertEqual(attr.value[0].priority, 5800)
        self.assertEqual(attr.value[0].availability, 'available')

    def test_many_ports(self):
        attr = self.assertParses(
            pactl.GenericListAttribute.Syntax, (
                'Ports:\n'
                '\tanalog-output: Wyjście analogowe (priority: 9900)\n'
                '\tanalog-output-headphones: Słuchawki (priority: 9000, not available)\n')
        )['attribute']
        self.assertEqual(attr.name, 'Ports')
        self.assertEqual(attr.value[0].name, 'analog-output')
        self.assertEqual(attr.value[0].label, 'Wyjście analogowe')
        self.assertEqual(attr.value[0].priority, 9900)
        self.assertEqual(attr.value[0].availability, '')
        self.assertEqual(attr.value[1].name, 'analog-output-headphones')
        self.assertEqual(attr.value[1].label, 'Słuchawki')
        self.assertEqual(attr.value[1].priority, 9000)
        self.assertEqual(attr.value[1].availability, 'not available')

    def test_chinese_ports(self):
        attr = self.assertParses(
            pactl.GenericListAttribute.Syntax, (
                'Ports:\n'
                '\tanalog-output;output-amplifier-on: 模拟输出 / 均衡器 (priority: 9910)\n'
                '\tanalog-output;output-amplifier-off: 模拟输出 / 无均衡器 (priority: 9900)\n'
                '\tanalog-output-mono;output-amplifier-on: 模拟单声道输出 / 均衡器 (priority: 5010)\n'
                '\tanalog-output-mono;output-amplifier-off: 模拟单声道输出 / 无均衡器 (priority: 5000)\n')
        )['attribute']
        self.assertEqual(attr.name, 'Ports')
        self.assertEqual(len(attr.value), 4)
        self.assertEqual(attr.value[1].name, 'analog-output;output-amplifier-off')
        self.assertEqual(attr.value[1].label, '模拟输出 / 无均衡器')

    def test_with_profile_association(self):
        attr = self.assertParses(
            pactl.GenericListAttribute.Syntax, (
                'Ports:\n'
                '\tanalog-output-speaker: Głośniki (priority 10000)\n'
                '\t\tPart of profile(s): output:analog-stereo, output:analog-stereo+input:analog-stereo\n'
            )
        )['attribute']
        self.assertEqual(attr.name, 'Ports')
        self.assertEqual(attr.value[0].name, 'analog-output-speaker')
        self.assertEqual(attr.value[0].label, 'Głośniki')
        self.assertEqual(attr.value[0].priority, 10000)
        self.assertEqual(attr.value[0].profile_list, [
            'output:analog-stereo', 'output:analog-stereo+input:analog-stereo'])

    def test_with_ports_properties(self):
        attr = self.assertParses(
            pactl.GenericListAttribute.Syntax, (
                'Ports:\n'
                '\tanalog-input-microphone-internal: Internal Microphone (priority: 98903, latency offset: 982 usec)\n'
                '\t\tProperties:\n'
                '\t\t\tdevice.icon_name = "audio-input-microphone"\n'
                '\t\t\tdevice.display_name = "Microphone"\n'
                '\t\tPart of profile(s): input:analog-stereo\n'
            )
        )['attribute']
        self.assertEqual(attr.name, 'Ports')
        self.assertEqual(attr.value[0].latency_offset, 982)
        self.assertEqual(attr.value[0].properties[0].name, 'device.icon_name')
        self.assertEqual(attr.value[0].properties[0].value, 'audio-input-microphone')
        self.assertEqual(attr.value[0].properties[1].name, 'device.display_name')
        self.assertEqual(attr.value[0].properties[1].value, 'Microphone')

    def test_SPDIF_in_port_label(self):
        # This checks that '(S/PDIF)' does not confuse the parser to parse
        # '(' before port properties
        attr = self.assertParses(
            pactl.GenericListAttribute.Syntax, (
                'Ports:\n'
                '\tiec958-stereo-input: Digital Input (S/PDIF) (priority: 0, latency offset: 0 usec)\n'
                '\t\tPart of profile(s): input:iec958-stereo\n'
            )
        )['attribute']
        self.assertEqual(attr.name, 'Ports')
        self.assertEqual(attr.value[0].name, 'iec958-stereo-input')
        self.assertEqual(attr.value[0].label, 'Digital Input (S/PDIF)')
        self.assertEqual(attr.value[0].priority, 0)
        self.assertEqual(attr.value[0].latency_offset, 0)
        self.assertEqual(attr.value[0].profile_list, ['input:iec958-stereo'])

    def test_profiles(self):
        attr = self.assertParses(
            pactl.GenericListAttribute.Syntax, (
                'Profiles:\n'
                '\toutput:analog-stereo: Wyjście Analogowe stereo (sinks: 1, sources: 0, priority. 6000)\n'
                '\toutput:analog-stereo+input:analog-stereo: Analogowy dupleks stereo (sinks: 1, sources: 1, priority. 6060)\n'
                '\toutput:hdmi-stereo: Wyjście Digital Stereo (HDMI) (sinks: 1, sources: 0, priority. 5400)\n'
                '\toutput:hdmi-stereo+input:analog-stereo: Wyjście Digital Stereo (HDMI) + Wejście Analogowe stereo (sinks: 1, sources: 1, priority. 5460)\n'
                '\toutput:hdmi-surround: Wyjście Digital Surround 5.1 (HDMI) (sinks: 1, sources: 0, priority. 300)\n'
                '\toutput:hdmi-surround+input:analog-stereo: Wyjście Digital Surround 5.1 (HDMI) + Wejście Analogowe stereo (sinks: 1, sources: 1, priority. 360)\n'
                '\tinput:analog-stereo: Wejście Analogowe stereo (sinks: 0, sources: 1, priority. 60)\n'
                '\toff: Wyłącz (sinks: 0, sources: 0, priority. 0)\n'
            )
        )['attribute']
        self.assertEqual(attr.name, 'Profiles')
        self.assertEqual(attr.value[0].name, 'output:analog-stereo')
        self.assertEqual(attr.value[0].label, 'Wyjście Analogowe stereo')
        self.assertEqual(attr.value[0].priority, 6000) 
        self.assertEqual(attr.value[-3].label, 'Wyjście Digital Surround 5.1 (HDMI) + Wejście Analogowe stereo') 
        self.assertEqual(attr.value[-3].priority, 360) 
        self.assertEqual(attr.value[-1].name, 'off')

    def test_format(self):
        attr = self.assertParses(
            pactl.GenericListAttribute.Syntax, 'Formats:\n' '\tpcm\n'
        )['attribute']
        self.assertEqual(attr.name, 'Formats')
        self.assertEqual(attr.value, ['pcm'])


class RecordTests(ParsingTestCase, PactlDataMixIn):

    def test_sinks(self):
        record = self.assertParses(
            pactl.Record.Syntax, self.get_text("sinks-desktop-precise-0")
        )['record']
        self.assertEqual(record.name, "Sink #0")
        self.assertEqual(record.attribute_list[0].name, "State")
        self.assertIs(record.attribute_map['State'], record.attribute_list[0])
        # Probe some random things
        self.assertEqual(
            record.attribute_map['Ports'].value[0].name, "hdmi-output-1")
        self.assertEqual(
            record.attribute_map['Properties'].value[2].value, "sound")
        self.assertEqual(
            record.attribute_map['Formats'].value, ['pcm'])

    def test_modules(self):
        record = self.assertParses(
            pactl.Record.Syntax, self.get_text("modules-desktop-precise-0")
        )['record']
        self.assertEqual(record.name, "Module #0")
        self.assertEqual(record.attribute_list[0].name, "Name")
        self.assertEqual(record.attribute_list[0].value,
                         "module-device-restore")
        self.assertEqual(record.attribute_list[1].name, "Argument")
        self.assertEqual(record.attribute_list[1].value, "")
        self.assertEqual(record.attribute_list[2].name, "Usage counter")
        self.assertEqual(record.attribute_list[2].value, "n/a")
        self.assertEqual(record.attribute_list[3].name, "Properties")
        self.assertEqual(record.attribute_list[3].value[0].name,
                         "module.author")
        self.assertEqual(record.attribute_list[3].value[0].value,
                         "Lennart Poettering")
        # Skip the second property because it's pretty long
        self.assertEqual(record.attribute_list[3].value[2].name,
                         "module.version")
        self.assertEqual(record.attribute_list[3].value[2].value, "1.1")


class DocumentTests(ParsingTestCase, PactlDataMixIn):

    def test_pactl_list_modules(self):
        document = self.assertParses(
            pactl.Document.Syntax, self.get_text("modules-desktop-precise")
        )[0]
        self.assertEqual(len(document.record_list), 24)
        self.assertEqual(document.record_list[0].name, "Module #0")
        self.assertEqual(document.record_list[0].attribute_map['Argument'].value, "")
        self.assertEqual(document.record_list[23].name, "Module #23")

    def test_pactl_list_sinks(self):
        document = self.assertParses(
            pactl.Document.Syntax, self.get_text("sinks-desktop-precise")
        )[0]
        self.assertEqual(len(document.record_list), 1)

    def test_pactl_list_cards(self):
        document = self.assertParses(
            pactl.Document.Syntax, self.get_text("cards-desktop-precise")
        )[0]
        self.assertEqual(len(document.record_list), 1)

    def test_pactl_list_cards_xps1340(self):
        document = self.assertParses(
            pactl.Document.Syntax, self.get_text("desktop-precise-xps1340")
        )[0]
        self.assertEqual(len(document.record_list), 34)

    def test_pactl_list(self):
        document = self.assertParses(
            pactl.Document.Syntax, self.get_text("desktop-precise")
        )[0]
        for i in range(24):
            self.assertEqual(
                document.record_list[i].name,
                "Module #{}".format(i))
        self.assertEqual(document.record_list[24].name, "Sink #0")
        self.assertEqual(document.record_list[25].name, "Source #0")
        self.assertEqual(document.record_list[26].name, "Source #1")
        self.assertEqual(document.record_list[27].name, "Sink Input #1249")
        self.assertEqual(document.record_list[28].name, "Source Output #11")
        self.assertEqual(document.record_list[29].name, "Client #0")
        self.assertEqual(document.record_list[30].name, "Client #1")
        self.assertEqual(document.record_list[31].name, "Client #2")
        self.assertEqual(document.record_list[32].name, "Client #7")
        self.assertEqual(document.record_list[33].name, "Client #9")
        self.assertEqual(document.record_list[34].name, "Client #10")
        self.assertEqual(document.record_list[35].name, "Client #63")
        self.assertEqual(document.record_list[36].name, "Client #101")
        self.assertEqual(document.record_list[37].name, "Client #173")
        self.assertEqual(document.record_list[38].name, "Client #175")
        self.assertEqual(document.record_list[39].name, "Client #195")
        self.assertEqual(document.record_list[40].name, "Sample #0")
        self.assertEqual(document.record_list[41].name, "Sample #1")
        self.assertEqual(document.record_list[42].name, "Card #0")
        self.assertEqual(len(document.record_list), 43)
