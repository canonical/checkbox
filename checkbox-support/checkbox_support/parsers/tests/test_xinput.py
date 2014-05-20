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

from checkbox_support.parsers.xinput import (
    DEVICE_RE,
    ATTRIBUTE_RE,
    CLASS_VALUE_RE,
    LIST_VALUE_RE,
    IXinputResult,
    XinputParser,
    )


class TestDeviceRe(TestCase):

    def test_string(self):
        match = DEVICE_RE.match(
            """⎡ Virtual core pointer                      """
            """id=2    [master pointer  (3)]""")
        self.assertTrue(match)
        self.assertEqual(match.group("name"), "Virtual core pointer")
        self.assertEqual(match.group("id"), "2")


class TestAttributeRe(TestCase):

    def test_string(self):
        match = ATTRIBUTE_RE.match("""Buttons supported: 12""")
        self.assertTrue(match)
        self.assertEqual(match.group("key"), "Buttons supported")
        self.assertEqual(match.group("value"), "12")


class TestClassValueRe(TestCase):

    def test_string(self):
        match = CLASS_VALUE_RE.match("""12. Type: XIButtonClass""")
        self.assertTrue(match)
        self.assertEqual(match.group("class"), "XIButtonClass")


class TestListValueRe(TestCase):

    def test_string(self):
        elements = LIST_VALUE_RE.split(
            """"Button Horiz Wheel Right" None None""")[1::2]
        self.assertTrue(elements)
        self.assertEqual(len(elements), 3)
        self.assertEqual(elements[0], '"Button Horiz Wheel Right"')
        self.assertEqual(elements[1], "None")
        self.assertEqual(elements[2], "None")


class XinputResult(IXinputResult):

    def __init__(self):
        self.devices = {}

    def addXinputDevice(self, device):
        self.devices[device["id"]] = device

    def addXinputDeviceClass(self, device, device_class):
        self.devices[device["id"]].setdefault("classes", [])
        self.devices[device["id"]]["classes"].append(device_class)


class TestXinputParser(TestCase):


    def getResult(self, name):
        fixture = os.path.join(os.path.dirname(__file__), "fixtures", name)
        result = XinputResult()
        with open(fixture, encoding="utf-8") as stream:
            parser = XinputParser(stream)
            parser.run(result)
        return result

    def test_number_of_devices_with_spaces(self):
        """The toshiba xinput with spaces contains 12 devices."""
        result = self.getResult("xinput_toshiba.txt")
        self.assertEqual(len(result.devices), 12)

    def test_number_of_devices_without_spaces(self):
        """The quantal xinput without spaces contains 14 devices."""
        result = self.getResult("xinput_quantal.txt")
        self.assertEqual(len(result.devices), 14)

    def test_multitouch_touchpad_device(self):
        """The toshiba xinput contains a multitouch touchpad device."""
        result = self.getResult("xinput_toshiba.txt")
        devices = [device for device in result.devices.values()
            if device["name"] == "AlpsPS/2 ALPS DualPoint TouchPad"]
        self.assertEqual(len(devices), 1)

        classes = [cls for cls in devices[0]["classes"]
            if cls["device_class"] == "XITouchClass"]
        self.assertEqual(len(classes), 1)
        self.assertEqual(classes[0]["touch_mode"], "dependent")

    def test_multitouch_touchscreen_device(self):
        """The quantal xinput contains a multitouch touchscreen device."""
        result = self.getResult("xinput_quantal.txt")
        devices = [device for device in result.devices.values()
            if device["name"] == "Quanta OpticalTouchScreen"]
        self.assertEqual(len(devices), 1)

        classes = [cls for cls in devices[0]["classes"]
            if cls["device_class"] == "XITouchClass"]
        self.assertEqual(len(classes), 1)
        self.assertEqual(classes[0]["touch_mode"], "direct")
