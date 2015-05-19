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

from checkbox_support.parsers.modinfo import (
    ModinfoParser,
    MultipleModinfoParser,
    ModinfoResult
)


# A single module that is otherwise well-formed, this tests parsing
# when a delimiter is not found and basic key handling
MODINFO1 = """\
name:           uvcvideo
filename:       /lib/modules/3.13.0-48-generic/kernel/drivers/media/usb/uvc/uvcvideo.ko
version:        1.1.1
license:        GPL
description:    USB Video Class driver
author:         Laurent Pinchart &lt;laurent.pinchart@ideasonboard.com&gt;
srcversion:     92BBF15FFC6F4BABEA6EB29
alias:          usb:v*p*d*dc*dsc*dp*ic0Eisc01ip00in*
alias:          usb:v0416pA91Ad*dc*dsc*dp*ic0Eisc01ip00in*
depends:        videodev,videobuf2-core,videobuf2-vmalloc
intree:         Y
vermagic:       3.13.0-48-generic SMP mod_unload modversions 
signer:         Magrathea: Glacier signing key
sig_key:        4E:B2:DE:24:99:17:CB:F3:9C:B8:56:92:E5:4C:EB:AD:E5:94:D6:80
sig_hashalgo:   sha512
parm:           clock:Video buffers timestamp clock
parm:           nodrop:Don't drop incomplete frames (uint)
"""

# Two well-formed modules, this tests multi-stanza parsing.
# A small trick: there are two lines separating the modules and
# one contains some sneaky whitespace
MODINFO2 = """\
name:           uvcvideo
filename:       /lib/modules/3.13.0-48-generic/kernel/drivers/media/usb/uvc/uvcvideo.ko
version:        1.1.1
license:        GPL
description:    USB Video Class driver
author:         Laurent Pinchart &lt;laurent.pinchart@ideasonboard.com&gt;
srcversion:     92BBF15FFC6F4BABEA6EB29
alias:          usb:v*p*d*dc*dsc*dp*ic0Eisc01ip00in*
depends:        videodev,videobuf2-core,videobuf2-vmalloc
intree:         Y
vermagic:       3.13.0-48-generic SMP mod_unload modversions 
signer:         Magrathea: Glacier signing key
sig_key:        4E:B2:DE:24:99:17:CB:F3:9C:B8:56:92:E5:4C:EB:AD:E5:94:D6:80
sig_hashalgo:   sha512
parm:           clock:Video buffers timestamp clock

   
name:           ccm
filename:       /lib/modules/3.13.0-48-generic/kernel/crypto/ccm.ko
alias:          crypto-ccm
description:    Counter with CBC MAC
license:        GPL
srcversion:     5DEAB3AB626E8E116D01BEF
depends:        
intree:         Y
vermagic:       3.13.0-48-generic SMP mod_unload modversions 
"""

# This is a malformed record which only has a name
MODINFO3 = """\
name:          bogus_module

"""

# This is a weird record with NO name
MODINFO4 = """\
filename:       /lib/modules/3.13.0-48-generic/kernel/crypto/ccm.ko
alias:          crypto-ccm
description:    Counter with CBC MAC
license:        GPL
srcversion:     5DEAB3AB626E8E116D01BEF
depends:        
intree:         Y
vermagic:       3.13.0-48-generic SMP mod_unload modversions 

"""


class TestModinfoParser(TestCase):

    """Tests for the "single" modinfo parser."""

    def test_good_parse(self):
        """A good modinfo block is parsed into the expected data items."""
        data = "\n".join(MODINFO1.split("\n")[1:])
        parser = ModinfoParser(data)
        result = parser.get_all()

        expected = {
            'firmware':       [],
            'filename':       "/lib/modules/3.13.0-48-generic/kernel/drivers/media/usb/uvc/uvcvideo.ko",
            'version':        "1.1.1",
            'license':        "GPL",
            'description':    "USB Video Class driver",
            'author':         "Laurent Pinchart &lt;laurent.pinchart@ideasonboard.com&gt;",
            'srcversion':     "92BBF15FFC6F4BABEA6EB29",
            'alias':          ["usb:v*p*d*dc*dsc*dp*ic0Eisc01ip00in*",
                               "usb:v0416pA91Ad*dc*dsc*dp*ic0Eisc01ip00in*"],
            'depends':        "videodev,videobuf2-core,videobuf2-vmalloc",
            'intree':         "Y",
            'vermagic':       "3.13.0-48-generic SMP mod_unload modversions",
            'signer':         "Magrathea: Glacier signing key",
            'sig_key':        "4E:B2:DE:24:99:17:CB:F3:9C:B8:56:92:E5:4C:EB:AD:E5:94:D6:80",
            'sig_hashalgo':   "sha512",
            'parm':           ["clock:Video buffers timestamp clock",
                               "nodrop:Don't drop incomplete frames (uint)"]
            }
        self.assertDictEqual(result, expected)

    def test_bogus_parse(self):
        """Test that a modinfo block with crap is not parsed."""
        data = "lorem ipsum blah"
        parser = ModinfoParser(data)
        result = parser.get_all()
        self.assertEqual(result, {})


class testMultipleModinfoParser(TestCase):

    """Tests for the multiple modinfo parser."""

    def test_good_parse(self):
        """
        A good modinfo block with 2 sets of modinfo should parse ok.

        Test that a known-good modinfo block with slightly tricky
        separators and two sets of modinfos is correctly parsed.
        """
        stream = StringIO(MODINFO2)
        parser = MultipleModinfoParser(stream)
        result = ModinfoResult()
        parser.run(result)

        self.assertEqual(2, len(result.mod_data))
        self.assertIn('uvcvideo', result.mod_data)
        self.assertEqual('1.1.1', result.mod_data['uvcvideo']['version'])
        self.assertIn('ccm', result.mod_data)
        self.assertEqual(['crypto-ccm'], result.mod_data['ccm']['alias'])

    def test_name_only_parse(self):
        """
        A weird record with only a name results in nothing.

        The attachment may contain bogus "name:" records with no info and those
        should be eaten silently as we have no real data.
        """
        stream = StringIO(MODINFO3)
        parser = MultipleModinfoParser(stream)
        result = ModinfoResult()
        parser.run(result)
        self.assertEqual(result.mod_data, {})

    def test_no_name_parse(self):
        """
        A weird record with no name results in nothing.

        This may happen if some unsuspecting soul feeds output from "modinfo
        blah" into the MultipleModinfo parser.
        """
        stream = StringIO(MODINFO4)
        parser = MultipleModinfoParser(stream)
        result = ModinfoResult()
        parser.run(result)
        self.assertEqual(result.mod_data, {})
