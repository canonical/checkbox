# This file is part of Checkbox.
#
# Copyright 2013, 2014 Canonical Ltd.
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
plainbox.impl.secure.test_config
================================

Test definitions for plainbox.impl.secure.config module
"""
from io import StringIO
from unittest import TestCase

from plainbox.impl.secure.config import ChoiceValidator
from plainbox.impl.secure.config import ConfigMetaData
from plainbox.impl.secure.config import KindValidator
from plainbox.impl.secure.config import NotEmptyValidator
from plainbox.impl.secure.config import NotUnsetValidator
from plainbox.impl.secure.config import PatternValidator
from plainbox.impl.secure.config import PlainBoxConfigParser, Config
from plainbox.impl.secure.config import Variable, Section, Unset


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

    def test_validator_list__default(self):
        """
        verify that each Variable has a validator_list and that by default,
        that list contains a KindValidator as the first element
        """
        self.assertEqual(Variable().validator_list, [KindValidator])

    def test_validator_list__explicit(self):
        """
        verify that each Variable has a validator_list and that, if
        customized, the list contains the custom validators, preceded by
        the implicit KindValidator object
        """
        def DummyValidator(variable, new_value):
            """ Dummy validator for the test below"""
            pass
        var = Variable(validator_list=[DummyValidator])
        self.assertEqual(var.validator_list, [KindValidator, DummyValidator])

    def test_validator_list__with_NotUnsetValidator(self):
        """
        verify that each Variable has a validator_list and that, if
        customized, and if using NotUnsetValidator it will take precedence
        over all other validators, including the implicit KindValidator
        """
        var = Variable(validator_list=[NotUnsetValidator()])
        self.assertEqual(
            var.validator_list, [NotUnsetValidator(), KindValidator])


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


class PatternValidatorTests(TestCase):

    class _Config(Config):
        var = Variable()

    def test_smoke(self):
        """
        verify that PatternValidator works as intended
        """
        validator = PatternValidator("foo.+")
        self.assertEqual(validator(self._Config.var, "foobar"), None)
        self.assertEqual(
            validator(self._Config.var, "foo"),
            "does not match pattern: 'foo.+'")

    def test_comparison_works(self):
        self.assertTrue(PatternValidator('foo') == PatternValidator('foo'))
        self.assertTrue(PatternValidator('foo') != PatternValidator('bar'))
        self.assertTrue(PatternValidator('foo') != object())


class ChoiceValidatorTests(TestCase):

    class _Config(Config):
        var = Variable()

    def test_smoke(self):
        """
        verify that ChoiceValidator works as intended
        """
        validator = ChoiceValidator(["foo", "bar"])
        self.assertEqual(validator(self._Config.var, "foo"), None)
        self.assertEqual(
            validator(self._Config.var, "omg"), "must be one of foo, bar")

    def test_comparison_works(self):
        self.assertTrue(ChoiceValidator(["a"]) == ChoiceValidator(["a"]))
        self.assertTrue(ChoiceValidator(["a"]) != ChoiceValidator(["b"]))
        self.assertTrue(ChoiceValidator(["a"]) != object())


class NotUnsetValidatorTests(TestCase):
    """
    Tests for the NotUnsetValidator class
    """

    class _Config(Config):
        var = Variable()

    def test_rejects_unset_values(self):
        """
        verify that Unset variables are rejected
        """
        validator = NotUnsetValidator()
        self.assertEqual(
            validator(self._Config.var, Unset), "must be set to something")

    def test_accepts_other_values(self):
        """
        verify that other values are accepted
        """
        validator = NotUnsetValidator()
        self.assertIsNone(validator(self._Config.var, None))
        self.assertIsNone(validator(self._Config.var, "string"))
        self.assertIsNone(validator(self._Config.var, 15))

    def test_supports_custom_message(self):
        """
        verify that custom message is used
        """
        validator = NotUnsetValidator("value required!")
        self.assertEqual(
            validator(self._Config.var, Unset), "value required!")

    def test_comparison_works(self):
        """
        verify that comparison works as expected
        """
        self.assertTrue(NotUnsetValidator() == NotUnsetValidator())
        self.assertTrue(NotUnsetValidator("?") == NotUnsetValidator("?"))
        self.assertTrue(NotUnsetValidator() != NotUnsetValidator("?"))
        self.assertTrue(NotUnsetValidator() != object())


class NotEmptyValidatorTests(TestCase):

    class _Config(Config):
        var = Variable()

    def test_rejects_empty_values(self):
        validator = NotEmptyValidator()
        self.assertEqual(validator(self._Config.var, ""), "cannot be empty")

    def test_supports_custom_message(self):
        validator = NotEmptyValidator("name required!")
        self.assertEqual(validator(self._Config.var, ""), "name required!")

    def test_isnt_broken(self):
        validator = NotEmptyValidator()
        self.assertEqual(validator(self._Config.var, "some value"), None)

    def test_comparison_works(self):
        self.assertTrue(NotEmptyValidator() == NotEmptyValidator())
        self.assertTrue(NotEmptyValidator("?") == NotEmptyValidator("?"))
        self.assertTrue(NotEmptyValidator() != NotEmptyValidator("?"))
        self.assertTrue(NotEmptyValidator() != object())
