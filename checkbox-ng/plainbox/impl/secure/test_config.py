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
import configparser

from plainbox.impl.secure.config import ChoiceValidator
from plainbox.impl.secure.config import ConfigMetaData
from plainbox.impl.secure.config import KindValidator
from plainbox.impl.secure.config import NotEmptyValidator
from plainbox.impl.secure.config import NotUnsetValidator
from plainbox.impl.secure.config import PatternValidator
from plainbox.impl.secure.config import PlainBoxConfigParser, Config
from plainbox.impl.secure.config import Variable, Section, Unset
from plainbox.impl.secure.config import understands_Unset


class UnsetTests(TestCase):

    def test_str(self):
        self.assertEqual(str(Unset), "unset")

    def test_repr(self):
        self.assertEqual(repr(Unset), "Unset")

    def test_bool(self):
        self.assertEqual(bool(Unset), False)


class understands_Unset_Tests(TestCase):

    def test_func(self):
        @understands_Unset
        def func():
            pass

        self.assertTrue(hasattr(func, 'understands_Unset'))
        self.assertTrue(getattr(func, 'understands_Unset'))

    def test_cls(self):
        @understands_Unset
        class cls:
            pass

        self.assertTrue(hasattr(cls, 'understands_Unset'))
        self.assertTrue(getattr(cls, 'understands_Unset'))


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

    def _get_featureful_config(self):
        # define a featureful config class
        class TestConfig(Config):
            v1 = Variable()
            v2 = Variable(section="v23_section")
            v3 = Variable(section="v23_section")
            v_unset = Variable()
            v_bool = Variable(section="type_section", kind=bool)
            v_int = Variable(section="type_section", kind=int)
            v_float = Variable(section="type_section", kind=float)
            v_str = Variable(section="type_section", kind=str)
            s = Section()
        conf = TestConfig()
        # assign value to each variable, except v3_unset
        conf.v1 = "v1 value"
        conf.v2 = "v2 value"
        conf.v3 = "v3 value"
        conf.v_bool = True
        conf.v_int = -7
        conf.v_float = 1.5
        conf.v_str = "hi"
        # assign value to the section
        conf.s = {"a": 1, "b": 2}
        return conf

    def test_get_parser_obj(self):
        """
        verify that Config.get_parser_obj() properly writes all the data to the
        ConfigParser object.
        """
        conf = self._get_featureful_config()
        parser = conf.get_parser_obj()
        # verify that section and section-less variables work
        self.assertEqual(parser.get("DEFAULT", "v1"), "v1 value")
        self.assertEqual(parser.get("v23_section", "v2"), "v2 value")
        self.assertEqual(parser.get("v23_section", "v3"), "v3 value")
        # verify that unset variable is not getting set to anything
        with self.assertRaises(configparser.Error):
            parser.get("DEFAULT", "v_unset")
        # verify that various types got converted correctly and still resolve
        # to correct typed values
        self.assertEqual(parser.get("type_section", "v_bool"), "True")
        self.assertEqual(parser.getboolean("type_section", "v_bool"), True)
        self.assertEqual(parser.get("type_section", "v_int"), "-7")
        self.assertEqual(parser.getint("type_section", "v_int"), -7)
        self.assertEqual(parser.get("type_section", "v_float"), "1.5")
        self.assertEqual(parser.getfloat("type_section", "v_float"), 1.5)
        self.assertEqual(parser.get("type_section", "v_str"), "hi")
        # verify that section work okay
        self.assertEqual(parser.get("s", "a"), "1")
        self.assertEqual(parser.get("s", "b"), "2")

    def test_write(self):
        """
        verify that Config.write() works
        """
        conf = self._get_featureful_config()
        with StringIO() as stream:
            conf.write(stream)
            self.assertEqual(stream.getvalue(), (
                "[DEFAULT]\n"
                "v1 = v1 value\n"
                "\n"
                "[v23_section]\n"
                "v2 = v2 value\n"
                "v3 = v3 value\n"
                "\n"
                "[type_section]\n"
                "v_bool = True\n"
                "v_float = 1.5\n"
                "v_int = -7\n"
                "v_str = hi\n"
                "\n"
                "[s]\n"
                "a = 1\n"
                "b = 2\n"
                "\n"))

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

    def test_read_string(self):
        class TestConfig(Config):
            v = Variable()
        conf = TestConfig()
        conf.read_string(
            "[DEFAULT]\n"
            "v = 1")
        self.assertEqual(conf.v, "1")
        self.assertEqual(len(conf.problem_list), 0)

    def test_read_string__does_not_ignore_nonmentioned_variables(self):
        class TestConfig(Config):
            v = Variable(validator_list=[NotUnsetValidator()])
        conf = TestConfig()
        conf.read_string("")
        # Because Unset is the default, sadly
        self.assertEqual(conf.v, Unset)
        # But there was a problem noticed
        self.assertEqual(len(conf.problem_list), 1)
        self.assertEqual(conf.problem_list[0].variable, TestConfig.v)
        self.assertEqual(conf.problem_list[0].new_value, Unset)
        self.assertEqual(conf.problem_list[0].message,
                         "must be set to something")


class ConfigMetaDataTests(TestCase):

    def test_filename_list(self):
        self.assertEqual(ConfigMetaData.filename_list, [])

    def test_variable_list(self):
        self.assertEqual(ConfigMetaData.variable_list, [])

    def test_section_list(self):
        self.assertEqual(ConfigMetaData.section_list, [])


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


class KindValidatorTests(TestCase):

    class _Config(Config):
        var_bool = Variable(kind=bool)
        var_int = Variable(kind=int)
        var_float = Variable(kind=float)
        var_str = Variable(kind=str)

    def test_error_msg(self):
        """
        verify that KindValidator() has correct error message for each type
        """
        bad_value = object()
        self.assertEqual(
            KindValidator(self._Config.var_bool, bad_value),
            "expected a boolean")
        self.assertEqual(
            KindValidator(self._Config.var_int, bad_value),
            "expected an integer")
        self.assertEqual(
            KindValidator(self._Config.var_float, bad_value),
            "expected a floating point number")
        self.assertEqual(
            KindValidator(self._Config.var_str, bad_value),
            "expected a string")


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

    def test_understands_Unset(self):
        """
        verify that Unset can be handled at all
        """
        self.assertTrue(getattr(NotUnsetValidator, "understands_Unset"))

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
