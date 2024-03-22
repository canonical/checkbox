#!/usr/bin/env python3

import unittest
import os
from unittest.mock import patch
from mei import MEI_INTERFACE, get_mei_firmware_version


class TestMEIInterface(unittest.TestCase):

    def setUp(self):
        self.mei_interface = MEI_INTERFACE()
        self.mock_mei_path = "/dev/mei0"
        self.mock_mei_obj = 123
        self.mock_raw_fw_ver = (
            b'\x01\x02\x03\x04\x05\x06\x07\x08\x09\x0A\x0B\x0C\x0D\x0E'
            b'\x0F\x10\x11\x12\x13\x14\x15\x16\x17\x18\x19\x1A\x1B\x1C')

    def tearDown(self):
        pass

    @patch("os.listdir")
    def test_get_mei(self, mock_listdir):
        # Test when get mei0
        mock_listdir.return_value = ["mei0", "foo", "bar"]
        path = self.mei_interface._get_mei()
        self.assertEqual(self.mock_mei_path, path)
        # Test when get mei1
        mock_listdir.return_value = ["mei1", "foo", "bar"]
        path = self.mei_interface._get_mei()
        self.assertEqual("/dev/mei1", path)
        # Test when get nothing
        mock_listdir.return_value = ["foo", "bar"]
        path = self.mei_interface._get_mei()
        self.assertEqual(None, path)

    @patch("os.open")
    @patch('mei.MEI_INTERFACE._get_mei')
    def test_open(self, mock_get_mei, mock_os_open):
        # Test if raise SystemExit when get None
        mock_get_mei.return_value = None
        with self.assertRaises(SystemExit):
            self.mei_interface.open()
        # Test if get correct value when os.open
        mock_get_mei.return_value = self.mock_mei_path
        self.mei_interface.open()
        mock_os_open.assert_called_once_with(self.mock_mei_path, os.O_RDWR)

    @patch("fcntl.ioctl")
    @patch("os.open")
    @patch('mei.MEI_INTERFACE._get_mei')
    def test_connect(self, mock_get_mei, mock_os_open, mock_ioctl):
        mock_get_mei.return_value = self.mock_mei_path
        mock_os_open.return_value = self.mock_mei_obj
        self.mei_interface.open()
        length, version = self.mei_interface.connect("01234567-89ab-cdef"
                                                     "-0123-456789abcdef")
        self.assertEqual(19088743, length)
        self.assertEqual(171, version)

    @patch("os.write")
    def test_write(self, mock_write):
        self.mei_interface._mei_obj = 123
        self.mei_interface.write(0x000002FF)
        mock_write.assert_called_once_with(123, b'\xff\x02\x00\x00')

    @patch("os.read")
    def test_read(self, mock_read):
        self.mei_interface._mei_obj = 456
        mock_read.return_value = self.mock_raw_fw_ver
        result = self.mei_interface.read(32)
        mock_read.assert_called_once_with(456, 32)
        self.assertEqual(result, self.mock_raw_fw_ver)

    @patch('os.close')
    def test_close(self, mock_os_close):
        self.mei_interface.close()
        mock_os_close.assert_called_once_with(self.mei_interface._mei_obj)

    @patch("mei.MEI_INTERFACE.close")
    @patch("mei.MEI_INTERFACE.open")
    @patch("mei.MEI_INTERFACE.connect")
    @patch("mei.MEI_INTERFACE.write")
    @patch("mei.MEI_INTERFACE.read")
    def test_get_mei_firmware_version(self, mock_read, mock_write,
                                      mock_connect, mock_open, mock_close):
        # Mock MEI_INTERFACE methods
        mock_read.return_value = self.mock_raw_fw_ver
        get_mei_firmware_version()
        # Assert that the MEI_INTERFACE methods are called correctly
        mock_open.assert_called_once_with()
        mock_connect.assert_called_once_with("8e6a6715-9abc-4043-88ef"
                                             "-9e39c6f63e0f")
        mock_write.assert_called_once_with(0x000002FF)
        mock_read.assert_called_once_with(28)
        # Check Raise SystemExit
        mock_open.side_effect = Exception("Some error")
        with self.assertRaises(SystemExit):
            get_mei_firmware_version()
        # Check finally
        # mock_close.assert_called_once()
