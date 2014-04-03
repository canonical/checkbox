# This file is part of Checkbox.
#
# Copyright 2013 Canonical Ltd.
# Written by:
#   Zygmunt Krynicki <zygmunt.krynicki@canonical.com>
#   Daniel Manrique <roadmr@ubuntu.com>
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
certification XML data to the Canonical certification database.
"""

from gettext import gettext as _
from logging import getLogger
import re

from plainbox.impl.transport import TransportBase
from plainbox.impl.transport import TransportError
import requests

from checkbox_ng.config import SECURE_ID_PATTERN


logger = getLogger("checkbox.ng.certification")


class InvalidSecureIDError(ValueError):
    def __init__(self, value):
        self.value = value

    def __str__(self):
        return repr(self.value)


class CertificationTransport(TransportBase):
    """
    Transport for sending data to certification database.
     - POSTs data to a http(s) endpoint
     - Adds a header with a hardware identifier
     - Data is expected to be in checkbox xml-compatible format.
       This means it will work best with a stream produced by the
       xml exporter.
   """

    def __init__(self, where, options):
        """
        Initialize the Certification Transport.

        The options string may contain 'secure_id' which must be
        a 15- or 18-character alphanumeric ID for the system.
        """
        super().__init__(where, options)
        self._secure_id = self.options.get('secure_id')
        if self._secure_id is not None:
            self._validate_secure_id(self._secure_id)

    def send(self, data, config=None, session_state=None):
        """
        Sends data to the specified server.

        :param data:
            Data containing the xml dump to be sent to the server. This
            can be either bytes or a file-like object (BytesIO works fine too).
            If this is a file-like object, it will be read and streamed "on
            the fly".
        :param config:
             Optional PlainBoxConfig object. If http_proxy and https_proxy
             values are set in this config object, they will be used to send
             data via the specified protocols. Note that the transport also
             honors the http_proxy and https_proxy environment variables.
             Proxy string format is http://[user:password@]<proxy-ip>:port
        :param session_state:
            The session for which this transport is associated with
            the data being sent (optional)
        :returns:
            A dictionary with responses from the server if submission
            was successful. This should contain an 'id' key, however
            the server response may change, so the only guarantee
            we make is that this will be non-False if the server
            accepted the data.
        :raises requests.exceptions.Timeout:
            If sending timed out.
        :raises requests.exceptions.ConnectionError:
            If connection failed outright.
        :raises requests.exceptions.HTTPError:
            If the server returned a non-success result code
        """
        proxies = None
        if config:
            proxies = {
                proto[:-len("_proxy")]: config.environment[proto]
                for proto in ['http_proxy', 'https_proxy']
                if proto in config.environment
            }
        # Find the effective value of secure_id:
        # - use the configuration object (if available)
        # - override with secure_id= option (if defined)
        secure_id = None
        if config is not None and hasattr(config, 'secure_id'):
            secure_id = config.secure_id
        if self._secure_id is not None:
            secure_id = self._secure_id
        if secure_id is None:
            raise InvalidSecureIDError(_("Secure ID not specified"))
        self._validate_secure_id(secure_id)
        logger.debug("Sending to %s, hardware id is %s", self.url, secure_id)
        headers = {"X_HARDWARE_ID": secure_id}
        # Requests takes care of properly handling a file-like data.
        form_payload = {"data": data}
        try:
            response = requests.post(
                self.url, files=form_payload, headers=headers, proxies=proxies)
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
                raise TransportError(str(exc))
            logger.debug("Success! Server said %s", response.text)
            try:
                return response.json()
            except Exception as exc:
                raise TransportError(str(exc))
        # XXX: can response be None?
        return {}

    def _validate_secure_id(self, secure_id):
        if not re.match(SECURE_ID_PATTERN, secure_id):
            raise InvalidSecureIDError(
                _("secure_id must be 15 or 18-character alphanumeric string"))
