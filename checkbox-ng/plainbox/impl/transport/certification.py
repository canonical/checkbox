# This file is part of Checkbox.
#
# Copyright 2013 Canonical Ltd.
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
:mod:`plainbox.impl.transport.certification` -- send to certification database
==============================================================================

.. warning::

    THIS MODULE DOES NOT HAVE STABLE PUBLIC API
"""

from logging import getLogger
import re
import requests

from plainbox.impl.secure.config import Unset
from plainbox.impl.transport import TransportBase

logger = getLogger("plainbox.transport.certification")


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

    def __init__(self, where, options, config=None):
        """
        Initialize the Certification Transport.

        The options string must contain:
        * secure_id: A 15- or 18-character alphanumeric ID for the system.
                     Valid characters are [a-zA-Z0-9]

        :param config:
             optional PlainBoxConfig object. If http_proxy and https_proxy
             values are set in this config object, they will be used to send
             data via the specified protocols. Note that the transport also
             honors the http_proxy and https_proxy environment variables.
             Proxy string format is http://[user:password@]<proxy-ip>:port
        """
        super(CertificationTransport, self).__init__(where, options)

        if config is not None and config.environment is not Unset:
            self.proxies = {proto: config.environment[proto + "_proxy"]
                            for proto in ['http', 'https']
                            if proto + "_proxy" in config.environment}
        else:
            self.proxies = None

        if not 'secure_id' in self.options:
            raise InvalidSecureIDError("Required option secure_id missing")
        if not re.match(r"^[a-zA-Z0-9]{15}$|^[a-zA-Z0-9]{18}$",
                        self.options['secure_id']):
            raise InvalidSecureIDError(("secure_id must be 15 or 18-character "
                                        "alphanumeric string"))

    def send(self, data):
        """ Sends data to the specified server.

        :param data:
            Data containing the xml dump to be sent to the server. This
            can be either bytes or a file-like object (BytesIO works fine too).
            If this is a file-like object, it will be read and streamed "on
            the fly".

        :returns: a dictionary with responses from the server if submission
            was successful. This should contain an 'id' key, however
            the server response may change, so the only guarantee
            we make is that this will be non-False if the server
            accepted the data.

        :raises requests.exceptions.Timeout: If sending timed out.

        :raises requests.exceptions.ConnectionError:
            If connection failed outright.

        :raises requests.exceptions.HTTPError: if the server returned
            a non-success result code
        """

        logger.debug("Sending to %s, hardware id is %s",
                     self.url, self.options['secure_id'])
        cert_headers = {"X_HARDWARE_ID": self.options['secure_id']}
        form_payload = {"data": data}  # Requests takes care of properly
                                       # handling a file-like object for
                                       # data here.
        try:
            r = requests.post(self.url, files=form_payload,
                              headers=cert_headers, proxies=self.proxies)
        except requests.exceptions.Timeout as error:
            logger.warning("Request to %s timed out: %s", self.url, error)
            raise
        except requests.exceptions.ConnectionError as error:
            logger.error("Unable to connect to %s: %s", self.url, error)
            raise
        if r is not None:
            r.raise_for_status()  # This will raise HTTPError for status != 20x
            logger.debug("Success! Server said %s", r.text)
            return r.json()
