# Copyright 2017 Canonical Ltd.
# All rights reserved.
#
# Written by:
#    Maciej Kisielewski <maciej.kisielewski@canonical.com>

import unittest
import sys

from textwrap import dedent
from unittest.mock import mock_open, patch

from checkbox_support.snap_utils.config import get_configuration_set
from checkbox_support.snap_utils.config import get_snapctl_config
from checkbox_support.snap_utils.config import refresh_configuration
from checkbox_support.snap_utils.config import write_checkbox_conf


class TestSnapctlConfig(unittest.TestCase):
    def test_no_keys(self):
        self.assertEqual(get_snapctl_config([]), dict())

    def test_one_key(self):
        SNAPCTL_OUT = dedent("""
        {
        \t"foo": "bar"
        }
        """).lstrip().encode(sys.stdout.encoding)
        with patch('subprocess.check_output', return_value=SNAPCTL_OUT) as p:
            expected = {'foo': 'bar'}
            self.assertEqual(get_snapctl_config(['foo']), expected)
            p.assert_called_with(['snapctl', 'get', '-d', 'foo'])

    def test_not_set_key(self):
        with patch('subprocess.check_output', return_value=b'{}\n') as p:
            expected = {}
            self.assertEqual(get_snapctl_config(['foo']), expected)
            p.assert_called_with(['snapctl', 'get', '-d', 'foo'])

    def test_two_keys(self):
        SNAPCTL_OUT = dedent("""
        {
        \t"foo": "bar",
        \t"biz": "baz"
        }
        """).lstrip().encode(sys.stdout.encoding)
        with patch('subprocess.check_output', return_value=SNAPCTL_OUT) as p:
            expected = {'foo': 'bar', 'biz': 'baz'}
            self.assertEqual(get_snapctl_config(['foo', 'biz']), expected)
            p.assert_called_with(['snapctl', 'get', '-d', 'foo', 'biz'])

    def test_two_keys_one_missing(self):
        SNAPCTL_OUT = dedent("""
        {
        \t"foo": "bar"
        }
        """).lstrip().encode(sys.stdout.encoding)
        with patch('subprocess.check_output', return_value=SNAPCTL_OUT) as p:
            expected = {'foo': 'bar'}
            self.assertEqual(get_snapctl_config(['foo', 'biz']), expected)
            p.assert_called_with(['snapctl', 'get', '-d', 'foo', 'biz'])

    def test_two_keys_both_missing(self):
        with patch('subprocess.check_output', return_value=b'{}\n') as p:
            self.assertEqual(get_snapctl_config(['foo', 'biz']), dict())
            p.assert_called_with(['snapctl', 'get', '-d', 'foo', 'biz'])


class TestConfigSet(unittest.TestCase):
    def test_empty_on_missing(self):
        class FNFE_raiser():
            def __call__(self, *args):
                raise FileNotFoundError()
        with patch('builtins.open', new_callable=FNFE_raiser, create=True):
            result = get_configuration_set()
            self.assertEqual(result, dict())

    def test_correct_values(self):
        with patch('builtins.open', mock_open(read_data='FOO=bar\nBAZ=Biz')):
            result = get_configuration_set()
            self.assertEqual(result, {'foo': 'bar', 'baz': 'Biz'})

    def test_comments_ignored(self):
        DATA = """
        # comment
        FOO=bar
            # indented comment
        BAZ=Biz
        """
        with patch('builtins.open', mock_open(read_data=DATA)):
            result = get_configuration_set()
            self.assertEqual(result, {'foo': 'bar', 'baz': 'Biz'})

    def test_inline_comments_is_val(self):
        DATA = 'FOO=bar # inline comment'
        with patch('builtins.open', mock_open(read_data=DATA)):
            result = get_configuration_set()
            self.assertEqual(result, {'foo': 'bar # inline comment'})

    def test_lowercase_key_raises(self):
        DATA = 'foo=bar'
        with patch('builtins.open', mock_open(read_data=DATA)):
            expected_msg = 'foo is not a valid configuration key'
            with self.assertRaisesRegex(ValueError, expected_msg):
                get_configuration_set()

    def test_empty_on_empty_file(self):
        with patch('builtins.open', mock_open(read_data='')):
            self.assertEqual(get_configuration_set(), dict())


class TestWriteCheckboxConf(unittest.TestCase):
    def test_smoke(self):
        m = mock_open()
        with patch('builtins.open', m):
            write_checkbox_conf({'foo': 'bar'})
        m().write.called_once_with('[environ]\n')
        m().write.called_once_with('FOO = bar\n')
        m().write.called_once_with('\n')
        self.assertEqual(m().write.call_count, 3)

    def test_writes_empty(self):
        m = mock_open()
        with patch('builtins.open', m):
            write_checkbox_conf({})
        m().write.called_once_with('[environ]\n')
        m().write.called_once_with('\n')
        self.assertEqual(m().write.call_count, 2)


class ConfigIntegrationTests(unittest.TestCase):
    """
        Integration tests for configuration manipulation.

        The test have following structure:
            establish values in config_vars
            establish values in snapd database
            expect calls to `snapctl set`
            expect checkbox.conf to be written
    """
    @patch('checkbox_support.snap_utils.config.get_configuration_set')
    @patch('checkbox_support.snap_utils.config.write_checkbox_conf')
    @patch('subprocess.run')
    def test_empty_on_missing(self, mock_run, mock_write, mock_conf_set):
        """ nothing in config_vars,
            nothing in snapd db,
            so checkbox.conf should not be written
            and no calls to snapctl should be made
        """
        mock_conf_set.return_value = {}
        refresh_configuration()
        self.assertTrue(mock_conf_set.called)
        self.assertFalse(mock_write.called)
        self.assertFalse(mock_run.called)

    @patch('checkbox_support.snap_utils.config.get_configuration_set')
    @patch('subprocess.check_output', return_value=b'{}\n')
    @patch('subprocess.run')
    def test_one_value(self, mock_run, mock_subproc, mock_conf_set):
        """ FOO=bar in config_vars,
            nothing in snapd db,
            so checkbox.conf should be written with:
            "FOO=bar"
            and snapctl should be called with:
            foo=bar
        """
        mock_conf_set.return_value = {'foo': 'bar'}
        m = mock_open()
        with patch('builtins.open', m):
            refresh_configuration()
        m().write.called_once_with('[environ]\n')
        m().write.called_once_with('FOO = bar\n')
        m().write.called_once_with('\n')
        self.assertTrue(mock_conf_set.called)
        mock_run.assert_called_once_with(['snapctl', 'set', 'foo=bar'])

    @patch('checkbox_support.snap_utils.config.get_configuration_set')
    @patch('subprocess.check_output')
    @patch('subprocess.run')
    def test_one_value_overriden_by_config(
            self, mock_run, mock_subproc, mock_conf_set):
        """
            FOO=default in config_vars,
            and snapd db has foo=bar,
            so checkbox.conf should be written with:
            "FOO=bar"
        """
        mock_conf_set.return_value = {'foo': 'default'}
        mock_subproc.return_value = dedent("""
        {
        \t"foo": "bar"
        }
        """).lstrip().encode(sys.stdout.encoding)
        m = mock_open()
        with patch('builtins.open', m):
            refresh_configuration()
        m().write.called_once_with('[environ]\n')
        m().write.called_once_with('FOO = bar\n')
        m().write.called_once_with('\n')
        mock_run.assert_called_once_with(['snapctl', 'set', 'foo=bar'])

    @patch('checkbox_support.snap_utils.config.get_configuration_set')
    @patch('subprocess.check_output')
    @patch('subprocess.run')
    def test_one_new_one_existing(
            self, mock_run, mock_subproc, mock_conf_set):
        """
            FOO=bar BIZ=baz in config_vars,
            and snapd db has foo=old,
            so checkbox.conf should be written with:
            "FOO=old and BIZ=baz"
        """
        mock_conf_set.return_value = {'foo': 'bar', 'biz': 'baz'}
        mock_subproc.return_value = dedent("""
        {
        \t"foo": "old"
        }
        """).lstrip().encode(sys.stdout.encoding)
        m = mock_open()
        with patch('builtins.open', m):
            refresh_configuration()
        m().write.called_once_with('[environ]\n')
        m().write.called_once_with('FOO = old\n')
        m().write.called_once_with('BIZ = baz\n')
        m().write.called_once_with('\n')
        mock_run.assert_called_once_with(
            ['snapctl', 'set', 'biz=baz', 'foo=old'])
