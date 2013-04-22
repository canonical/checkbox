# This file is part of Checkbox.
#
# Copyright 2012, 2013 Canonical Ltd.
# Written by:
#   Zygmunt Krynicki <zygmunt.krynicki@canonical.com>
#   Daniel Manrique <roadmr@ubuntu.com>
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
plainbox.impl.transport.test_certification
==========================================

Test definitions for plainbox.impl.certification module
"""

from io import BytesIO
from pkg_resources import resource_string
from unittest import TestCase

from mock import MagicMock
import mock
from requests.exceptions import ConnectionError, InvalidSchema, HTTPError
import requests

from plainbox.impl.transport.certification import CertificationTransport
from plainbox.impl.transport.certification import InvalidSecureIDError
from plainbox.impl.applogic import PlainBoxConfig


class CertificationTransportTests(TestCase):

    #URL are just here to exemplify, since we mock away all network access,
    #they're not really used.
    valid_url = "https://certification.canonical.com/submissions/submit"
    invalid_url = "htz://:3128"
    unreachable_url = "http://i.dont.exist"
    valid_secure_id = "a00D000000Kkk5j"
    valid_option_string = "secure_id={}".format(valid_secure_id)

    def setUp(self):
        self.sample_xml = BytesIO(resource_string(
            "plainbox", "test-data/xml-exporter/example-data.xml"
        ))
        self.patcher = mock.patch('requests.post')
        self.mock_requests = self.patcher.start()

    def test_parameter_parsing(self):
        #Makes sense since I'm overriding the base class's constructor.
        transport = CertificationTransport(self.valid_url,
                                           self.valid_option_string)
        self.assertEqual(self.valid_url, transport.url)
        self.assertEqual(self.valid_secure_id,
                         transport.options['secure_id'])

    def test_invalid_length_secure_id_are_rejected(self):
        for length in (14, 16, 20):
            dummy_id = "a" * length
            option_string = "secure_id={}".format(dummy_id)
            with self.assertRaises(InvalidSecureIDError):
                transport = CertificationTransport(self.valid_url,
                                                   option_string)
                self.assertIsInstance(CertificationTransport,
                                      transport)

    def test_invalid_characters_in_secure_id_are_rejected(self):
        option_string = "secure_id=aA0#"
        with self.assertRaises(InvalidSecureIDError):
                transport = CertificationTransport(self.valid_url,
                                                   option_string)
                self.assertIsInstance(CertificationTransport,
                                      transport)

    def test_invalid_url(self):
        transport = CertificationTransport(self.invalid_url,
                                           self.valid_option_string)
        dummy_data = BytesIO(b"some data to send")
        requests.post.side_effect = InvalidSchema

        with self.assertRaises(InvalidSchema):
            result = transport.send(dummy_data)
            self.assertIsNotNone(result)
        requests.post.assert_called_with(self.invalid_url,
                                         files={'data': dummy_data},
                                         headers={'X_HARDWARE_ID':
                                         self.valid_secure_id},
                                         proxies=None)

    def test_valid_url_cant_connect(self):
        transport = CertificationTransport(self.unreachable_url,
                                           self.valid_option_string)
        dummy_data = BytesIO(b"some data to send")
        requests.post.side_effect = ConnectionError

        with self.assertRaises(ConnectionError):
            result = transport.send(dummy_data)
            self.assertIsNotNone(result)
        requests.post.assert_called_with(self.unreachable_url,
                                         files={'data': dummy_data},
                                         headers={'X_HARDWARE_ID':
                                                  self.valid_secure_id},
                                         proxies=None)

    def test_send_success(self):
        transport = CertificationTransport(self.valid_url,
                                           self.valid_option_string)

        requests.post.return_value = MagicMock(name='response')
        requests.post.return_value.status_code = 200
        requests.post.return_value.text = '{"id": 768}'
        result = transport.send(self.sample_xml)

        self.assertTrue(result)

    def test_send_failure(self):
        transport = CertificationTransport(self.valid_url,
                                           self.valid_option_string)

        requests.post.return_value = MagicMock(name='response')
        requests.post.return_value.status_code = 412
        requests.post.return_value.text = 'Some error'
        #Oops, raise_for_status doesn't get fooled by my mocking,
        #so I have to mock *that* method as well..
        requests.post.return_value.raise_for_status = MagicMock(
            side_effect=HTTPError)

        with self.assertRaises(HTTPError):
            result = transport.send(self.sample_xml)
            self.assertIsNotNone(result)

    def proxy_test(self, environment, proxies):
        test_environment = environment
        test_proxies = proxies
        test_config = PlainBoxConfig()
        test_config.environment = test_environment

        transport = CertificationTransport(self.valid_url,
                                           self.valid_option_string,
                                           config=test_config)
        dummy_data = BytesIO(b"some data to send")

        requests.post.return_value = MagicMock(name='response')
        requests.post.return_value.status_code = 200
        requests.post.return_value.text = '{"id": 768}'
        result = transport.send(dummy_data)

        self.assertTrue(result)

        requests.post.assert_called_with(self.valid_url,
                                         files={'data': dummy_data},
                                         headers={'X_HARDWARE_ID':
                                         self.valid_secure_id},
                                         proxies=test_proxies)

    def test_set_only_one_proxy(self):
        test_environment = {'http_proxy': "http://1.2.3.4:5"}
        test_proxies = {'http': "http://1.2.3.4:5"}
        self.proxy_test(test_environment, test_proxies)

    def test_set_two_proxies(self):
        test_environment = {'http_proxy': "http://1.2.3.4:5",
                            'https_proxy': "http://1.2.3.4:6"}
        test_proxies = {'http': "http://1.2.3.4:5",
                        'https': "http://1.2.3.4:6"}
        self.proxy_test(test_environment, test_proxies)

    def test_behavior_with_extraneous_environment(self):
        test_environment = {'http_proxy': "http://1.2.3.4:5",
                            'weird_value': 'What is this'}
        test_proxies = {'http': "http://1.2.3.4:5"}
        self.proxy_test(test_environment, test_proxies)

