# This file is part of Checkbox.
#
# Copyright 2015 Canonical Ltd.
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

from io import StringIO
from unittest import TestCase

from checkbox_support.parsers.dkms_info import DkmsInfoParser, DkmsInfoResult

DKMS1 = """\
some bogus unjson-parsable string
"""

DKMS2 = """\
{"dkms": "Some bogus json-parsable string",
 "non-dkms": 5}
"""

DKMS3 = """\
{"dkms": [{"foo": "bar"}],
 "non-dkms": {"baz":{"quux": "flux"}}}
"""

DKMS4 = """\
{
    "dkms": [
        {
            "arch": "x86_64",
            "dkms_name": "oem-audio-hda-daily",
            "dkms_ver": "0.201503121632~ubuntu14.04.1",
            "install_mods": {
                "snd_hda_codec": [],
                "snd_hda_intel": [
                    "pci:v00008086d*sv*sd*bc04sc03i00*"
                ]
            },
            "kernel_ver": "3.13.0-48-generic",
            "mods": [
                "snd_hda_intel",
                "snd_hda_codec"
            ],
            "pkg": {
                "architecture": "all",
                "depends": "dkms (&gt;= 1.95)",
                "description": "HDA driver in DKMS format.",
                "homepage": "https://code.launchpad.net/~ubuntu-audio-dev",
                "installed-size": "1512",
                "maintainer": "David  &lt;da@example.com&gt;",
                "modaliases": "hwe(pci:v00001022d*sv*sd*bc04sc03i00*, pci:v00001002d*sv*sd*bc04sc03i00*, pci:v000015ADd00001977sv*sd*bc*sc*i*, pci:v000017F3d00003010sv*sd*bc*sc*i*, pci:v000013F6d00005011sv*sd*bc*sc*i*, pci:v00001102d00000009sv*sd*bc*sc*i*, pci:v00001102d00000012sv*sd*bc*sc*i*, pci:v00001102d00000010sv*sd*bc*sc*i*, pci:v00006549d00002200sv*sd*bc*sc*i*, pci:v00006549d00001200sv*sd*bc*sc*i*, pci:v000010DEd*sv*sd*bc04sc03i00*, pci:v000010B9d00005461sv*sd*bc*sc*i*, pci:v00001039d00007502sv*sd*bc*sc*i*, pci:v00001106d00009140sv*sd*bc*sc*i*, pci:v00001106d00009170sv*sd*bc*sc*i*, pci:v00001106d00003288sv*sd*bc*sc*i*, pci:v00001002d0000AAB0sv*sd*bc*sc*i*, pci:v00001002d0000AAA8sv*sd*bc*sc*i*, pci:v00001002d0000AAA0sv*sd*bc*sc*i*, pci:v00001002d00009902sv*sd*bc*sc*i*, pci:v00001002d0000AA98sv*sd*bc*sc*i*, pci:v00001002d0000AA90sv*sd*bc*sc*i*, pci:v00001002d0000AA88sv*sd*bc*sc*i*, pci:v00001002d0000AA80sv*sd*bc*sc*i*, pci:v00001002d0000AA68sv*sd*bc*sc*i*, pci:v00001002d0000AA60sv*sd*bc*sc*i*, pci:v00001002d0000AA58sv*sd*bc*sc*i*, pci:v00001002d0000AA50sv*sd*bc*sc*i*, pci:v00001002d0000AA48sv*sd*bc*sc*i*, pci:v00001002d0000AA40sv*sd*bc*sc*i*, pci:v00001002d0000AA38sv*sd*bc*sc*i*, pci:v00001002d0000AA30sv*sd*bc*sc*i*, pci:v00001002d0000AA28sv*sd*bc*sc*i*, pci:v00001002d0000AA20sv*sd*bc*sc*i*, pci:v00001002d0000AA18sv*sd*bc*sc*i*, pci:v00001002d0000AA10sv*sd*bc*sc*i*, pci:v00001002d0000AA08sv*sd*bc*sc*i*, pci:v00001002d0000AA00sv*sd*bc*sc*i*, pci:v00001002d0000970Fsv*sd*bc*sc*i*, pci:v00001002d0000960Fsv*sd*bc*sc*i*, pci:v00001002d00007919sv*sd*bc*sc*i*, pci:v00001002d0000793Bsv*sd*bc*sc*i*, pci:v00001022d0000780Dsv*sd*bc*sc*i*, pci:v00001002d00004383sv*sd*bc*sc*i*, pci:v00001002d0000437Bsv*sd*bc*sc*i*, pci:v00008086d*sv*sd*bc04sc03i00*, pci:v00008086d00003A6Esv*sd*bc*sc*i*, pci:v00008086d00003A3Esv*sd*bc*sc*i*, pci:v00008086d0000293Fsv*sd*bc*sc*i*, pci:v00008086d0000293Esv*sd*bc*sc*i*, pci:v00008086d0000284Bsv*sd*bc*sc*i*, pci:v00008086d0000269Asv*sd*bc*sc*i*, pci:v00008086d000027D8sv*sd*bc*sc*i*, pci:v00008086d00002668sv*sd*bc*sc*i*, pci:v00008086d00002284sv*sd*bc*sc*i*, pci:v00008086d00000F04sv*sd*bc*sc*i*, pci:v00008086d0000080Asv*sd*bc*sc*i*, pci:v00008086d0000811Bsv*sd*bc*sc*i*, pci:v00008086d00003B56sv*sd*bc*sc*i*, pci:v00008086d0000160Csv*sd*bc*sc*i*, pci:v00008086d00000D0Csv*sd*bc*sc*i*, pci:v00008086d00000C0Csv*sd*bc*sc*i*, pci:v00008086d00000A0Csv*sd*bc*sc*i*, pci:v00008086d00009D70sv*sd*bc*sc*i*, pci:v00008086d0000A170sv*sd*bc*sc*i*, pci:v00008086d00009CA0sv*sd*bc*sc*i*, pci:v00008086d00009C21sv*sd*bc*sc*i*, pci:v00008086d00009C20sv*sd*bc*sc*i*, pci:v00008086d00008D21sv*sd*bc*sc*i*, pci:v00008086d00008D20sv*sd*bc*sc*i*, pci:v00008086d00008CA0sv*sd*bc*sc*i*, pci:v00008086d00008C20sv*sd*bc*sc*i*, pci:v00008086d00001E20sv*sd*bc*sc*i*, pci:v00008086d00001D20sv*sd*bc*sc*i*, pci:v00008086d00001C20sv*sd*bc*sc*i*)",
                "package": "oem-audio-hda-daily-dkms",
                "priority": "extra",
                "section": "devel",
                "status": "install ok installed",
                "version": "0.201503121632~ubuntu14.04.1"
            },
            "pkg_name": "oem-audio-hda-daily-dkms"
        }
    ],
    "non-dkms": {
        "oem-guestsession-workaround-1324327": {
            "architecture": "all",
            "depends": "stella-base-config",
            "installed-size": "36",
            "maintainer": "Canonical &lt;com@canonical.com&gt;",
            "match_patterns": [
                "oemalias:*"
            ],
            "modaliases": "stella_include(oemalias:*)",
            "package": "oem-guestsession-workaround-1324327",
            "priority": "optional",
            "section": "misc",
            "status": "install ok installed",
            "version": "1stella1"
        }
    }
}
"""


class TestDkmsInfoParser(TestCase):

    """
    Tests for the DKMS information parser.

    It actually gets information on some non-dkms packages too.
    """

    def test_json_unparseable(self):
        """A bogus non-json stream results in an empty dataset."""
        stream = StringIO(DKMS1)
        self.parser = DkmsInfoParser(stream)
        result = DkmsInfoResult()
        self.parser.run(result)
        self.assertEqual(result.dkms_info, {})

    def test_bogus_json_parseable(self):
        """A json stream with bad data results in an empty dataset."""
        stream = StringIO(DKMS2)
        self.parser = DkmsInfoParser(stream)
        result = DkmsInfoResult()
        self.parser.run(result)
        self.assertEqual(result.dkms_info, {})

    def test_bogus_json_parseable_tricky(self):
        """
        Another json stream with bad data, should give empty dataset.

        This stream is very misleading because it contains some of the
        keys we expect but the contents are really bogus.
        """
        stream = StringIO(DKMS3)
        self.parser = DkmsInfoParser(stream)
        result = DkmsInfoResult()
        self.parser.run(result)
        self.assertEqual(result.dkms_info, {})

    def test_good_json_parseable(self):
        """
        A json stream with good data contains the expected elements.

        The test data stream is a simplified version of a real one.
        """
        stream = StringIO(DKMS4)
        self.parser = DkmsInfoParser(stream)
        result = DkmsInfoResult()
        self.parser.run(result)
        self.assertIn("oem-audio-hda-daily-dkms", result.dkms_info)
        self.assertEqual(
            result.dkms_info["oem-audio-hda-daily-dkms"]['dkms-status'],
            'dkms')
        self.assertIn("oem-guestsession-workaround-1324327", result.dkms_info)
        self.assertEqual(
            result.dkms_info["oem-guestsession-workaround-1324327"]
            ['dkms-status'],
            'non-dkms')
