# Copyright (c) 2010-2012 Linaro Limited
# Copyright (c) 2013 Canonical Ltd.
#
# Author: Zygmunt Krynicki <zygmunt.krynicki@linaro.org>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import doctest
import unittest

from plainbox.vendor import extcmd


def test_suite():
    suite = unittest.defaultTestLoader.loadTestsFromName("extcmd.test")
    suite.addTests(doctest.DocTestSuite(extcmd))
    return suite


class Dummy:
    """
    Dummy class that has deterministic __repr__()
    """

    def __repr__(self):
        return "<Dummy>"


class ReprTests(unittest.TestCase):

    def test_safe_delegate(self):
        obj = extcmd.SafeDelegate(Dummy())
        self.assertEqual(repr(obj), "<SafeDelegate wrapping <Dummy>>")

    def test_chain(self):
        obj = extcmd.Chain([Dummy()])
        self.assertEqual(
            repr(obj), "<Chain [<SafeDelegate wrapping <Dummy>>]>")

    def test_redirect(self):
        obj = extcmd.Redirect(stdout=Dummy(), stderr=Dummy())
        self.assertEqual(
            repr(obj), "<Redirect stdout:<Dummy> stderr:<Dummy>>")

    def test_transform(self):
        obj = extcmd.Transform(callback=Dummy(), delegate=Dummy())
        self.assertEqual(
            repr(obj), ("<Transform callback:<Dummy> delegate:<SafeDelegate"
                        " wrapping <Dummy>>>"))

    def test_decode(self):
        obj = extcmd.Decode(delegate=Dummy())
        self.assertEqual(
            repr(obj), ("<Decode encoding:'UTF-8'"
                        " delegate:<SafeDelegate wrapping <Dummy>>>"))

    def test_encode(self):
        obj = extcmd.Encode(delegate=Dummy())
        self.assertEqual(
            repr(obj), ("<Encode encoding:'UTF-8'"
                        " delegate:<SafeDelegate wrapping <Dummy>>>"))


class Detector:
    """
    Auxiliary class that records if on_begin() and on_end() got called
    """

    on_begin_called = False
    on_end_called = False

    def on_begin(self, args, kwargs):
        self.on_begin_called = True

    def on_end(self, returncode):
        self.on_end_called = True


class PropagationTests(unittest.TestCase):

    def test_transform(self):
        detector = Detector()
        self.assertEqual(detector.on_begin_called, False)
        self.assertEqual(detector.on_end_called, False)
        obj = extcmd.Transform(lambda data: data, detector)
        obj.on_begin(None, None)
        obj.on_end(None)
        self.assertEqual(detector.on_begin_called, True)
        self.assertEqual(detector.on_end_called, True)
