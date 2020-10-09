# Copyright 2020 Canonical Ltd.
# All rights reserved.
#
# Written by:
#    Jonathan Cave <jonathan.cave@canonical.com>

from requests.models import Response
import unittest
from unittest.mock import Mock

from pkg_resources import resource_filename

from checkbox_support.snap_utils.asserts import decode
from checkbox_support.snap_utils.asserts import model_to_resource
from checkbox_support.snap_utils.asserts import serial_to_resource

model_focal_desktop = 'snap_utils/tests/asserts_data/MODEL_FOCAL_DESKTOP.txt'
serial_focal_desktop = 'snap_utils/tests/asserts_data/SERIAL_FOCAL_DESKTOP.txt'
model_uc18 = 'snap_utils/tests/asserts_data/MODEL_UC18.txt'
model_uc20 = 'snap_utils/tests/asserts_data/MODEL_UC20.txt'
model_bionic_server = 'snap_utils/tests/asserts_data/MODEL_BIONIC_SERVER.txt'
model_focal_server = 'snap_utils/tests/asserts_data/MODEL_FOCAL_SERVER.txt'
model_uc16_brandstore = 'snap_utils/tests/asserts_data/MODEL_UC16_BRANDSTORE.txt'


def create_mock_response(assert_path):
    mock_response = Mock(spec=Response)
    mock_response.status_code = 400
    mock_response.headers = {'X-Ubuntu-Assertions-Count': 1}
    with open(resource_filename('checkbox_support', assert_path), 'r') as f:
        mock_response.text = f.read()
    return mock_response


class TestModelAsserts(unittest.TestCase):

    def test_decode_focal(self):
        assertion_stream = create_mock_response(model_focal_desktop)
        iter = decode(assertion_stream)
        a = next(iter)
        self.assertIn('type', a)
        self.assertEqual(a['type'], 'model')
        self.assertIn('model', a)
        self.assertEqual(a['model'], 'generic-classic')
        with self.assertRaises(StopIteration):
            next(iter)

    def test_decode_uc18(self):
        assertion_stream = create_mock_response(model_uc18)
        iter = decode(assertion_stream)
        a = next(iter)
        self.assertIn('type', a)
        self.assertEqual(a['type'], 'model')
        self.assertIn('model', a)
        self.assertEqual(a['model'], 'ubuntu-core-18-amd64')
        with self.assertRaises(StopIteration):
            next(iter)

    def test_decode_uc20(self):
        assertion_stream = create_mock_response(model_uc20)
        iter = decode(assertion_stream)
        a = next(iter)
        self.assertIn('type', a)
        self.assertEqual(a['type'], 'model')
        self.assertIn('model', a)
        self.assertEqual(a['model'], 'ubuntu-core-20-amd64-dangerous')
        with self.assertRaises(StopIteration):
            next(iter)

    def test_model_to_resource_uc18(self):
        assertion_stream = create_mock_response(model_uc18)
        iter = decode(assertion_stream)
        a = next(iter)
        correct_resource = {
            'type': 'model',
            'authority-id': 'canonical',
            'brand-id': 'canonical',
            'model': 'ubuntu-core-18-amd64',
            'architecture': 'amd64',
            'base': 'core18',
            'sign-key-sha3-384': '9tydnLa6MTJ-jaQTFUXEwHl1yRx7ZS4K5cyFDhYDcPzhS7uyEkDxdUjg9g08BtNn',
            'kernel': 'pc-kernel',
            'kernel_track': '18',
            'gadget': 'pc',
            'gadget_track': '18'
        }
        self.assertDictEqual(correct_resource, model_to_resource(a))
        with self.assertRaises(StopIteration):
            next(iter)

    def test_model_to_resource_uc20(self):
        assertion_stream = create_mock_response(model_uc20)
        iter = decode(assertion_stream)
        a = next(iter)
        correct_resource = {
            'type': 'model',
            'authority-id': 'canonical',
            'brand-id': 'canonical',
            'model': 'ubuntu-core-20-amd64-dangerous',
            'architecture': 'amd64',
            'base': 'core20',
            'grade': 'dangerous',
            'sign-key-sha3-384': '9tydnLa6MTJ-jaQTFUXEwHl1yRx7ZS4K5cyFDhYDcPzhS7uyEkDxdUjg9g08BtNn',
            'gadget': 'pc',
            'gadget_track': '20/edge',
            'kernel': 'pc-kernel',
            'kernel_track': '20/edge'
        }
        self.assertDictEqual(correct_resource, model_to_resource(a))
        with self.assertRaises(StopIteration):
            next(iter)

    def test_decode_bionic_server(self):
        assertion_stream = create_mock_response(model_bionic_server)
        iter = decode(assertion_stream)
        a = next(iter)
        self.assertIn('type', a)
        self.assertEqual(a['type'], 'model')
        self.assertIn('model', a)
        self.assertEqual(a['model'], 'generic-classic')
        with self.assertRaises(StopIteration):
            next(iter)

    def test_model_to_resource_bionic_server(self):
        assertion_stream = create_mock_response(model_bionic_server)
        iter = decode(assertion_stream)
        a = next(iter)
        correct_resource = {
            'type': 'model',
            'authority-id': 'generic',
            'brand-id': 'generic',
            'model': 'generic-classic',
            'sign-key-sha3-384': 'd-JcZF9nD9eBw7bwMnH61x-bklnQOhQud1Is6o_cn2wTj8EYDi9musrIT9z2MdAa'
        }
        self.assertDictEqual(correct_resource, model_to_resource(a))
        self.assertNotIn('kernel', model_to_resource(a))
        with self.assertRaises(StopIteration):
            next(iter)

    def test_decode_focal_server(self):
        assertion_stream = create_mock_response(model_focal_server)
        iter = decode(assertion_stream)
        a = next(iter)
        self.assertIn('type', a)
        self.assertEqual(a['type'], 'model')
        self.assertIn('model', a)
        self.assertEqual(a['model'], 'generic-classic')
        with self.assertRaises(StopIteration):
            next(iter)

    def test_model_to_resource_focal_server(self):
        assertion_stream = create_mock_response(model_focal_server)
        iter = decode(assertion_stream)
        a = next(iter)
        correct_resource = {
            'type': 'model',
            'authority-id': 'generic',
            'brand-id': 'generic',
            'model': 'generic-classic',
            'sign-key-sha3-384': 'd-JcZF9nD9eBw7bwMnH61x-bklnQOhQud1Is6o_cn2wTj8EYDi9musrIT9z2MdAa'
        }
        self.assertDictEqual(correct_resource, model_to_resource(a))
        self.assertNotIn('kernel', model_to_resource(a))
        with self.assertRaises(StopIteration):
            next(iter)

    def test_decode_uc16_brandstore(self):
        assertion_stream = create_mock_response(model_uc16_brandstore)
        iter = decode(assertion_stream)
        a = next(iter)
        self.assertIn('type', a)
        self.assertEqual(a['type'], 'model')
        self.assertIn('model', a)
        self.assertEqual(a['model'], 'devicemodel')
        self.assertIn('store', a)
        self.assertEqual(a['store'], 'aaaaabbbbbccccc12345')
        self.assertIn('brand-id', a)
        self.assertEqual(a['brand-id'], 'acmeinc')
        with self.assertRaises(StopIteration):
            next(iter)

    def test_model_to_resource_uc16_brandstore(self):
        assertion_stream = create_mock_response(model_uc16_brandstore)
        iter = decode(assertion_stream)
        a = next(iter)
        correct_resource = {
            'type': 'model',
            'authority-id': 'acmeinc',
            'brand-id': 'acmeinc',
            'model': 'devicemodel',
            'sign-key-sha3-384': 'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa',
            'architecture': 'amd64',
            'gadget': 'device',
            'kernel': 'device-kernel',
            'store': 'aaaaabbbbbccccc12345'
        }
        self.assertDictEqual(correct_resource, model_to_resource(a))
        with self.assertRaises(StopIteration):
            next(iter)


class TestSerialAsserts(unittest.TestCase):

    def test_decode_focal(self):
        assertion_stream = create_mock_response(serial_focal_desktop)
        iter = decode(assertion_stream)
        a = next(iter)
        self.assertIn('type', a)
        self.assertEqual(a['type'], 'serial')
        self.assertIn('serial', a)
        self.assertEqual(a['serial'], '12345678-1234-1234-1234-b4f4dc4a1f9a')
        with self.assertRaises(StopIteration):
            next(iter)

    def test_serial_to_resource_focal(self):
        assertion_stream = create_mock_response(serial_focal_desktop)
        iter = decode(assertion_stream)
        a = next(iter)
        correct_resource = {
            'type': 'serial',
            'authority-id': 'generic',
            'brand-id': 'generic',
            'model': 'generic-classic',
            'serial': '12345678-1234-1234-1234-b4f4dc4a1f9a',
            'sign-key-sha3-384': 'wrfougkz3Huq2T_KklfnufCC0HzG7bJ9wP99GV0FF-D3QH3eJtuSRlQc2JhrAoh1'
        }
        self.assertDictEqual(correct_resource, serial_to_resource(a))
        with self.assertRaises(StopIteration):
            next(iter)
