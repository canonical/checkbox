# This file is part of Checkbox.
#
# Copyright 2013-2021 Canonical Ltd.
# Written by:
#   Zygmunt Krynicki <zygmunt.krynicki@canonical.com>
#   Daniel Manrique <roadmr@ubuntu.com>
#   Sylvain Pineau <sylvain.pineau@canonical.com>
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
plainbox.impl.transport.test_certification
==========================================

Test definitions for plainbox.impl.certification module
"""

import requests
from io import BytesIO
from unittest import TestCase

from plainbox.impl.transport import InvalidSecureIDError
from plainbox.impl.transport import TransportError
from plainbox.vendor import mock
from plainbox.vendor.mock import MagicMock
from requests.exceptions import ConnectionError, InvalidSchema, HTTPError

from checkbox_ng.certification import SubmissionServiceTransport, GatewayTimeoutError

try:
    from importlib.resources import files

    def resource_string(module, path):
        return files(module).joinpath(path).read_bytes()

except ImportError:
    from pkg_resources import resource_string


class SubmissionServiceTransportTests(TestCase):

    # URL are just here to exemplify, since we mock away all network access,
    # they're not really used.
    valid_url = "https://certification.canonical.com/submissions/submit"
    invalid_url = "htz://:3128"
    unreachable_url = "http://i.dont.exist"
    valid_secure_id = "a00D000000Kkk5j"
    valid_option_string = "secure_id={}".format(valid_secure_id)

    def setUp(self):
        self.sample_archive = BytesIO(
            resource_string(
                "plainbox", "test-data/tar-exporter/example-data.tar.xz"
            )
        )
        self.patcher = mock.patch("requests.post")
        self.mock_requests = self.patcher.start()

    def test_parameter_parsing(self):
        # Makes sense since I'm overriding the base class's constructor.
        transport = SubmissionServiceTransport(
            self.valid_url, self.valid_option_string
        )
        self.assertEqual(self.valid_url, transport.url)
        self.assertEqual(self.valid_secure_id, transport.options["secure_id"])

    def test_invalid_length_secure_id_are_rejected(self):
        length = 14
        dummy_id = "a" * length
        option_string = "secure_id={}".format(dummy_id)
        with self.assertRaises(InvalidSecureIDError):
            SubmissionServiceTransport(self.valid_url, option_string)

    def test_invalid_characters_in_secure_id_are_rejected(self):
        option_string = "secure_id=aA0#"
        with self.assertRaises(InvalidSecureIDError):
            SubmissionServiceTransport(self.valid_url, option_string)

    def test_invalid_url(self):
        transport = SubmissionServiceTransport(
            self.invalid_url, self.valid_option_string
        )
        dummy_data = BytesIO(b"some data to send")
        requests.post.side_effect = InvalidSchema

        with self.assertRaises(TransportError):
            result = transport.send(dummy_data)
            self.assertIsNotNone(result)
        requests.post.assert_called_with(self.invalid_url, data=dummy_data)

    @mock.patch("checkbox_ng.certification.logger")
    def test_valid_url_cant_connect(self, mock_logger):
        transport = SubmissionServiceTransport(
            self.unreachable_url, self.valid_option_string
        )
        dummy_data = BytesIO(b"some data to send")
        requests.post.side_effect = ConnectionError
        with self.assertRaises(TransportError):
            result = transport.send(dummy_data)
            self.assertIsNotNone(result)
        requests.post.assert_called_with(self.unreachable_url, data=dummy_data)

    def test_send_success(self):
        transport = SubmissionServiceTransport(
            self.valid_url, self.valid_option_string
        )
        requests.post.return_value = MagicMock(name="response")
        requests.post.return_value.status_code = 200
        requests.post.return_value.text = '{"id": 768}'
        result = transport.send(self.sample_archive)
        self.assertTrue(result)

    def test_send_failure(self):
        transport = SubmissionServiceTransport(
            self.valid_url, self.valid_option_string
        )
        requests.post.return_value = MagicMock(name="response")
        requests.post.return_value.status_code = 412
        requests.post.return_value.text = "Some error"
        # Oops, raise_for_status doesn't get fooled by my mocking,
        # so I have to mock *that* method as well..
        response = requests.Response()
        error = HTTPError(response=response)
        requests.post.return_value.raise_for_status = MagicMock(
            side_effect=error
        )
        with self.assertRaises(TransportError):
            transport.send(self.sample_archive)

    def test_504_timeout_with_success_indicators_json(self):
        """Test that 504 timeout with JSON success indicators returns success."""
        transport = SubmissionServiceTransport(
            self.valid_url, self.valid_option_string
        )

        # Mock a 504 response with JSON success indicators
        mock_response = MagicMock()
        mock_response.status_code = 504
        mock_response.content = b'{"id": "12345", "url": "https://certification.canonical.com/hardware/12345/"}'
        mock_response.json.return_value = {"id": "12345", "url": "https://certification.canonical.com/hardware/12345/"}
        mock_response.text = '{"id": "12345", "url": "https://certification.canonical.com/hardware/12345/"}'

        # Mock HTTPError for 504 status
        http_error = HTTPError(response=mock_response)
        mock_response.raise_for_status.side_effect = http_error

        requests.post.return_value = mock_response

        # Should return success data instead of raising exception
        result = transport.send(self.sample_archive)
        self.assertIsNotNone(result)
        self.assertEqual(result["id"], "12345")

    def test_504_timeout_with_success_indicators_text(self):
        """Test that 504 timeout with text success indicators returns success."""
        transport = SubmissionServiceTransport(
            self.valid_url, self.valid_option_string
        )

        # Mock a 504 response with text success indicators
        mock_response = MagicMock()
        mock_response.status_code = 504
        mock_response.content = b'<html><body>Submission successful! Your submission ID is 67890</body></html>'
        mock_response.json.side_effect = ValueError("Not JSON")
        mock_response.text = '<html><body>Submission successful! Your submission ID is 67890</body></html>'

        # Mock HTTPError for 504 status
        http_error = HTTPError(response=mock_response)
        mock_response.raise_for_status.side_effect = http_error

        requests.post.return_value = mock_response

        # Should return success data instead of raising exception
        result = transport.send(self.sample_archive)
        self.assertIsNotNone(result)
        self.assertEqual(result["message"], "Submission appears successful despite timeout")

    def test_504_timeout_without_success_indicators(self):
        """Test that 504 timeout without success indicators raises GatewayTimeoutError."""
        transport = SubmissionServiceTransport(
            self.valid_url, self.valid_option_string
        )

        # Mock a 504 response without success indicators
        mock_response = MagicMock()
        mock_response.status_code = 504
        mock_response.content = b'<html><body><h1>504 Gateway Time-out</h1></body></html>'
        mock_response.json.side_effect = ValueError("Not JSON")
        mock_response.text = '<html><body><h1>504 Gateway Time-out</h1></body></html>'

        # Mock HTTPError for 504 status
        http_error = HTTPError(response=mock_response)
        mock_response.raise_for_status.side_effect = http_error

        requests.post.return_value = mock_response

        # Should raise GatewayTimeoutError
        with self.assertRaises(GatewayTimeoutError) as cm:
            transport.send(self.sample_archive)

        self.assertIn("504 Gateway Timeout", str(cm.exception))
        self.assertEqual(cm.exception.response, mock_response)

    def test_504_timeout_with_empty_response(self):
        """Test that 504 timeout with empty response raises GatewayTimeoutError."""
        transport = SubmissionServiceTransport(
            self.valid_url, self.valid_option_string
        )

        # Mock a 504 response with empty content
        mock_response = MagicMock()
        mock_response.status_code = 504
        mock_response.content = b''
        mock_response.text = ''

        # Mock HTTPError for 504 status
        http_error = HTTPError(response=mock_response)
        mock_response.raise_for_status.side_effect = http_error

        requests.post.return_value = mock_response

        # Should raise GatewayTimeoutError
        with self.assertRaises(GatewayTimeoutError):
            transport.send(self.sample_archive)

    def test_check_submission_success_with_various_json_keys(self):
        """Test submission success detection with various JSON key patterns."""
        transport = SubmissionServiceTransport(
            self.valid_url, self.valid_option_string
        )

        test_cases = [
            {"id": "123"},
            {"url": "https://example.com/submission/123"},
            {"status_url": "https://example.com/status/123"},
            {"submission_id": "456"},
        ]

        for test_data in test_cases:
            mock_response = MagicMock()
            mock_response.content = True
            mock_response.json.return_value = test_data

            result = transport._check_submission_success_in_response(mock_response)
            self.assertEqual(result, test_data)

    def test_check_submission_success_with_text_indicators(self):
        """Test submission success detection with various text indicators."""
        transport = SubmissionServiceTransport(
            self.valid_url, self.valid_option_string
        )

        text_indicators = [
            "Submission successful - your data has been received",
            "Upload successful! Thank you for your submission",
            "Submission received and is being processed",
            "Your submission ID is: 12345",
            "Visit your submission URL: https://example.com/12345"
        ]

        for text in text_indicators:
            mock_response = MagicMock()
            mock_response.content = True
            mock_response.json.side_effect = ValueError("Not JSON")
            mock_response.text = text

            result = transport._check_submission_success_in_response(mock_response)
            self.assertIsNotNone(result)
            self.assertEqual(result["message"], "Submission appears successful despite timeout")

    def test_check_submission_success_with_no_indicators(self):
        """Test submission success detection with no success indicators."""
        transport = SubmissionServiceTransport(
            self.valid_url, self.valid_option_string
        )

        mock_response = MagicMock()
        mock_response.content = True
        mock_response.json.side_effect = ValueError("Not JSON")
        mock_response.text = "Generic error message with no success indicators"

        result = transport._check_submission_success_in_response(mock_response)
        self.assertIsNone(result)
