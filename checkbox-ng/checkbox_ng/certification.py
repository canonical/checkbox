# This file is part of Checkbox.
#
# Copyright 2013-2021 Canonical Ltd.
# Written by:
#   Zygmunt Krynicki <zygmunt.krynicki@canonical.com>
#   Daniel Manrique <roadmr@ubuntu.com>
#   Maciej Kisielewski <maciej.kisielewski@canonical.com>
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
:mod:`checkbox.certification` -- plainbox transport to certification database
=============================================================================

This module contains a PlainBox transport that knows how to send the
certification tarball to the Canonical certification database.
"""

from gettext import gettext as _
from logging import getLogger
import re

from plainbox.impl.transport import InvalidSecureIDError
from plainbox.impl.transport import SECURE_ID_PATTERN
from plainbox.impl.transport import TransportBase
from plainbox.impl.transport import TransportError
import requests


logger = getLogger("checkbox.ng.certification")


class GatewayTimeoutError(TransportError):
    """
    Exception raised when a 504 Gateway Timeout occurs during submission.

    This error indicates that the submission may have been successful on the
    server side despite the timeout response, and should be handled differently
    from other transport errors to avoid unnecessary retries.
    """

    def __init__(self, message, response=None):
        super().__init__(message)
        self.response = response


class SubmissionServiceTransport(TransportBase):
    """
    Transport for sending data to certification database.
     - POSTs data to a http(s) endpoint
     - Payload can be in:
        * LZMA compressed tarball that includes a submission.json and results
          from checkbox.
    """

    def __init__(self, where, options):
        """
        Initialize the Certification Transport.

        The options string may contain 'secure_id' which must be
        a 15-character (or longer)  alphanumeric ID for the system.
        """
        super().__init__(where, options)
        self._secure_id = self.options.get("secure_id")
        if self._secure_id is not None:
            self._validate_secure_id(self._secure_id)

    def _check_submission_success_in_response(self, response):
        """
        Check if the response indicates a successful submission despite timeout.

        This method attempts to parse the response content to determine if
        the submission was actually processed successfully on the server side,
        even though a 504 Gateway Timeout was returned.

        :param response: The HTTP response object
        :returns: dict with submission info if successful, None otherwise
        """
        try:
            # Try to parse JSON response first
            if response.content:
                try:
                    json_data = response.json()
                    # Check for common success indicators in the response
                    if isinstance(json_data, dict):
                        # Look for submission ID or URL which indicates success
                        if any(key in json_data for key in ['id', 'url', 'status_url', 'submission_id']):
                            logger.info(
                                _("Found submission success indicators in 504 response: %s"),
                                json_data
                            )
                            return json_data
                except (ValueError, TypeError):
                    # Not valid JSON, continue to text parsing
                    pass

                # Try to parse HTML/text response for success indicators
                response_text = response.text.lower()
                if any(indicator in response_text for indicator in [
                    'submission successful', 'upload successful', 'submission received',
                    'submission id', 'submission url'
                ]):
                    logger.info(
                        _("Found submission success indicators in 504 response text")
                    )
                    # Return a basic success response
                    return {"message": "Submission appears successful despite timeout"}

        except Exception as exc:
            logger.debug(_("Error checking response for success indicators: %s"), exc)

        return None

    def send(self, data, config=None, session_state=None):
        """
        Sends data to the specified server.

        :param data:
            Data containing the session dump to be sent to the server. This
            can be either bytes or a file-like object (BytesIO works fine too).
            If this is a file-like object, it will be read and streamed "on
            the fly".
        :param config:
            This is here only to to implement the interface.
        :param session_state:
            This is here only to to implement the interface.
        :returns:
            A dictionary with responses from the server if submission
            was successful. This should contain an 'id' key, however
            the server response may change, so the only guarantee
            we make is that this will be non-False if the server
            accepted the data. Returns empty dictionary otherwise.
        :raises requests.exceptions.Timeout:
            If sending timed out.
        :raises requests.exceptions.ConnectionError:
            If connection failed outright.
        :raises requests.exceptions.HTTPError:
            If the server returned a non-success result code
        """
        secure_id = self._secure_id
        if secure_id is None:
            raise InvalidSecureIDError(_("Secure ID not specified"))
        self._validate_secure_id(secure_id)
        logger.debug(_("Sending to %s, Secure ID is %s"), self.url, secure_id)
        try:
            response = requests.post(self.url, data=data)
        except requests.exceptions.Timeout as exc:
            raise TransportError(
                _("Request to {0} timed out: {1}").format(self.url, exc)
            )
        except requests.exceptions.InvalidSchema as exc:
            raise TransportError(_("Invalid destination URL: {0}").format(exc))
        except requests.exceptions.ConnectionError as exc:
            raise TransportError(
                _("Unable to connect to {0}: {1}").format(self.url, exc)
            )
        if response is not None:
            try:
                # This will raise HTTPError for status != 20x
                response.raise_for_status()
            except requests.exceptions.RequestException as exc:
                # Handle 504 Gateway Timeout specifically
                if response.status_code == 504:
                    logger.warning(
                        _("Received 504 Gateway Timeout from %s. "
                          "Checking if submission was successful despite timeout."),
                        self.url
                    )

                    # Check if the response contains success indicators
                    success_data = self._check_submission_success_in_response(response)
                    if success_data:
                        logger.info(
                            _("Submission appears to have succeeded despite 504 timeout")
                        )
                        return success_data

                    # No success indicators found, raise the timeout error
                    raise GatewayTimeoutError(
                        _("504 Gateway Timeout: {0}. The submission may have been "
                          "processed successfully on the server despite this timeout. "
                          "Please check the certification website to verify if your "
                          "submission was received before retrying.").format(str(exc)),
                        response=response
                    )
                raise TransportError(" ".join([str(exc), exc.response.text]))
            logger.debug("Success! Server said %s", response.text)
            try:
                return response.json()
            except Exception as exc:
                raise TransportError(str(exc))

        # ISessionStateTransport.send must return dictionary
        return {}

    def _validate_secure_id(self, secure_id):
        if not re.match(SECURE_ID_PATTERN, secure_id):
            message = _(
                (
                    "{} is not a valid secure_id. secure_id must be a "
                    "15-character (or more) alphanumeric string"
                ).format(secure_id)
            )
            raise InvalidSecureIDError(message)
