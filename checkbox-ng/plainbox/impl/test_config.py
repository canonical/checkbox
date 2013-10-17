# This file is part of Checkbox.
#
# Copyright 2013 Canonical Ltd.
# Written by:
#   Zygmunt Krynicki <zygmunt.krynicki@canonical.com>
#
# Checkbox is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Checkbox is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Checkbox.  If not, see <http://www.gnu.org/licenses/>.

"""
plainbox.impl.test_config
=========================

Test definitions for plainbox.impl.config module
"""
from io import StringIO
from unittest import TestCase

from plainbox.impl.config import ChoiceValidator
from plainbox.impl.config import KindValidator
from plainbox.impl.config import NotEmptyValidator
from plainbox.impl.config import PlainBoxConfigParser, Config, ConfigMetaData
from plainbox.impl.config import Variable, Section, Unset


class VariableTests(TestCase):

    def test_name(self):
        v1 = Variable()
        self.assertIsNone(v1.name)
        v2 = Variable('var')
        self.assertEqual(v2.name, 'var')
        v3 = Variable(name='var')
        self.assertEqual(v3.name, 'var')

    def test_section(self):
        v1 = Variable()
        self.assertEqual(v1.section, 'DEFAULT')
        v2 = Variable(section='foo')
        self.assertEqual(v2.section, 'foo')

    def test_kind(self):
        v1 = Variable(kind=bool)
        self.assertIs(v1.kind, bool)
        v2 = Variable(kind=int)
        self.assertIs(v2.kind, int)
        v3 = Variable(kind=float)
        self.assertIs(v3.kind, float)
        v4 = Variable(kind=str)
        self.assertIs(v4.kind, str)
        v5 = Variable()
        self.assertIs(v5.kind, str)
        with self.assertRaises(ValueError):
            Variable(kind=list)

    def test_validator_list(self):
        v1 = Variable()
        self.assertEqual(v1.validator_list, [KindValidator])


class SectionTests(TestCase):

    def test_name(self):
        s1 = Section()
        self.assertIsNone(s1.name)
        s2 = Section('sec')
        self.assertEqual(s2.name, 'sec')
        s3 = Variable(name='sec')
        self.assertEqual(s3.name, 'sec')


class ConfigTests(TestCase):

    def test_Meta_present(self):
        class TestConfig(Config):
            pass
        self.assertTrue(hasattr(TestConfig, 'Meta'))

    def test_Meta_base_cls(self):
        class TestConfig(Config):
            pass
        self.assertTrue(issubclass(TestConfig.Meta, ConfigMetaData))

        class HelperMeta:
            pass

        class TestConfigWMeta(Config):
            Meta = HelperMeta
        self.assertTrue(issubclass(TestConfigWMeta.Meta, ConfigMetaData))
        self.assertTrue(issubclass(TestConfigWMeta.Meta, HelperMeta))

    def test_Meta_variable_list(self):
        class TestConfig(Config):
            v1 = Variable()
            v2 = Variable()
        self.assertEqual(
            TestConfig.Meta.variable_list,
            [TestConfig.v1, TestConfig.v2])

    def test_variable_smoke(self):
        class TestConfig(Config):
            v = Variable()
        conf = TestConfig()
        self.assertIs(conf.v, Unset)
        conf.v = "value"
        self.assertEqual(conf.v, "value")
        del conf.v
        self.assertIs(conf.v, Unset)

    def test_section_smoke(self):
        class TestConfig(Config):
            s = Section()
        conf = TestConfig()
        self.assertIs(conf.s, Unset)
        with self.assertRaises(TypeError):
            conf.s['key'] = "key-value"
        conf.s = {}
        self.assertEqual(conf.s, {})
        conf.s['key'] = "key-value"
        self.assertEqual(conf.s['key'], "key-value")
        del conf.s
        self.assertIs(conf.s, Unset)

    def test_read(self):
        class TestConfig(Config):
            v = Variable()
        conf = TestConfig()
        conf.read_string(
            "[DEFAULT]\n"
            "v = 1")
        self.assertEqual(conf.v, "1")


class ConfigMetaDataTests(TestCase):

    def test_filename_list(self):
        self.assertEqual(ConfigMetaData.filename_list, [])

    def test_variable_list(self):
        self.assertEqual(ConfigMetaData.variable_list, [])


class PlainBoxConfigParserTest(TestCase):

    def test_parser(self):
        conf_file = StringIO("[testsection]\nlower = low\nUPPER = up")
        config = PlainBoxConfigParser()
        config.read_file(conf_file)

        self.assertEqual(['testsection'], config.sections())
        all_keys = list(config['testsection'].keys())
        self.assertTrue('lower' in all_keys)
        self.assertTrue('UPPER' in all_keys)
        self.assertFalse('upper' in all_keys)


class ChoiceValidatorTests(TestCase):

    def test_smoke(self):
        """
        verify that ChoiceValidator works as intended
        """
        validator = ChoiceValidator(["foo", "bar"])
        self.assertEqual(validator(None, "foo"), None)
        self.assertEqual(validator(None, "omg"), "must be one of foo, bar")


class NotEmptyValidatorTests(TestCase):

    def test_rejects_empty_values(self):
        validator = NotEmptyValidator()
        self.assertEqual(validator(None, ""), "cannot be empty")

    def test_supports_custom_message(self):
        validator = NotEmptyValidator("name required!")
        self.assertEqual(validator(None, ""), "name required!")

    def test_isnt_broken(self):
        validator = NotEmptyValidator()
        self.assertEqual(validator(None, "some value"), None)
