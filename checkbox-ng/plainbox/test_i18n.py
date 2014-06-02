# This file is part of Checkbox.
#
# Copyright 2014 Canonical Ltd.
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
plainbox.test_i18n
==================

Test definitions for plainbox.i18n module
"""

from unittest import TestCase

from plainbox.i18n import gettext_noop
from plainbox.i18n import NoOpTranslator
from plainbox.i18n import docstring


class FunctionTests(TestCase):

    def test_gettext_noop(self):
        self.assertEqual(gettext_noop("string"), "string")

    def test_docstring_cls(self):
        @docstring("text")
        class Foo:
            pass
        self.assertEqual(Foo.__doc__, "text")

    def test_docstring_func(self):
        @docstring("text")
        def foo():
            pass
        self.assertEqual(foo.__doc__, "text")


class NoOpTranslatorTests(TestCase):

    DOMAIN = 'domain'

    def setUp(self):
        self.t = NoOpTranslator()

    def test_gettext(self):
        self.assertEqual(self.t.gettext("msgid"), "msgid")

    def test_ngettext(self):
        self.assertEqual(self.t.ngettext("msgid1", "msgid2", 1), "msgid1")
        self.assertEqual(self.t.ngettext("msgid1", "msgid2", 2), "msgid2")

    def test_dgettext(self):
        self.assertEqual(self.t.dgettext("other-domain", "msgid"), "msgid")

    def test_dngettext(self):
        self.assertEqual(
            self.t.dngettext("other-domain", "msgid1", "msgid2", 1), "msgid1")
        self.assertEqual(
            self.t.dngettext("other-domain", "msgid1", "msgid2", 2), "msgid2")

    def test_pgettext(self):
        self.assertEqual(self.t.pgettext("msgctxt", "msgid"), "msgid")

    def test_pdgettext(self):
        self.assertEqual(
            self.t.pdgettext("msgctxt", "other-domain", "msgid"), "msgid")

    def test_pngettext(self):
        self.assertEqual(
            self.t.pngettext("msgctxt", "msgid1", "msgid2", 1), "msgid1")
        self.assertEqual(
            self.t.pngettext("msgctxt", "msgid1", "msgid2", 2), "msgid2")

    def test_pdngettext(self):
        self.assertEqual(
            self.t.pdngettext(
                "msgctxt", "other-domain", "msgid1", "msgid2", 1),
            "msgid1")
        self.assertEqual(
            self.t.pdngettext(
                "msgctxt", "other-domain", "msgid1", "msgid2", 2),
            "msgid2")
