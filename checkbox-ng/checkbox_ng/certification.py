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
        self._secure_id = self.options.get('secure_id')
        if self._secure_id is not None:
            self._validate_secure_id(self._secure_id)

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
        logger.debug(
            _("Sending to %s, Secure ID is %s"), self.url, secure_id)
        try:
            response = requests.post(self.url, data=data)
        except requests.exceptions.Timeout as exc:
            raise TransportError(
                _("Request to {0} timed out: {1}").format(self.url, exc))
        except requests.exceptions.InvalidSchema as exc:
            raise TransportError(
                _("Invalid destination URL: {0}").format(exc))
        except requests.exceptions.ConnectionError as exc:
            raise TransportError(
                _("Unable to connect to {0}: {1}").format(self.url, exc))
        if response is not None:
            try:
                # This will raise HTTPError for status != 20x
                response.raise_for_status()
            except requests.exceptions.RequestException as exc:
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
            raise InvalidSecureIDError(
                _("secure_id must be 15-character (or more) alphanumeric string"))
