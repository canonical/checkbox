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
Shared code for test data transports..

:mod:`plainbox.impl.transport` -- shared code for test data transports
======================================================================

.. warning::

    THIS MODULE DOES NOT HAVE STABLE PUBLIC API
"""

from collections import OrderedDict
from logging import getLogger
import pkg_resources
import re

from plainbox.abc import ISessionStateTransport
from plainbox.i18n import gettext as _
from plainbox.impl.secure.config import Unset

import requests


logger = getLogger("plainbox.transport")


class TransportError(Exception):

    """
    Base class for any problems related to transports.

    This class acts the base exception for any and all problems encountered by
    the any ISessionStateTransport during execution. Typically this is raised
    from .send() that failed in some way.
    """


class TransportBase(ISessionStateTransport):

    """
    Base class for transports that send test data somewhere.

    They handle just the transmission portion of data sending; exporters are
    expected to produce data in the proper format (e.g. json, xml).

    Each transport can have specific parameters that are required for the
    other end to properly process received information (like system
    identification, authorization data and so on), and that don't semantically
    belong in the test data as produced by the exporter. Additionally
    each transport needs to be told *where* to send test data. This is
    transport-dependent; things like a HTTP endpoint, IP address, port
    are good examples.
    """

    def __init__(self, where, option_string):
        """
        Initialize the transport base class.

        :param where:
            A generalized form of "destination". This can be a file name, an
            URL or anything appropriate for the given transport.
        :param option_string:
            Additional options appropriate for the transport, encoded as a
            comma-separated list of key=value pairs.
        :raises ValueError:
            If the option string is malformed.
        """
        self.url = where
        # parse option string only if there's at least one k=v pair
        self.options = {}
        if not option_string:
            return
        if "=" in option_string:
            self.options = {
                option: value for (option, value) in
                [pair.split("=", 1) for pair in option_string.split(",")]
            }
        if not self.options:
            raise ValueError(_("No valid options in option string"))


SECURE_ID_PATTERN = r"^[a-zA-Z0-9]{15}$|^[a-zA-Z0-9]{18}$"


class InvalidSecureIDError(ValueError):

    """Exception raised when the secure ID is formatted incorrectly."""

    def __init__(self, value):
        """Initialize a new exception."""
        self.value = value

    def __str__(self):
        """Get a string representation."""
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

        It may also contain a submit_to_hexr boolean, set to 1
        to enable submission to hexr.
        """
        super().__init__(where, options)
        # Interpret this setting here
        submit_to_hexr = self.options.get('submit_to_hexr')
        self._submit_to_hexr = False
        try:
            if submit_to_hexr and (submit_to_hexr.lower() in
                                   ('yes', 'true') or
                                   int(submit_to_hexr) == 1):
                self._submit_to_hexr = True
        except ValueError:
            # Just leave it at False
            pass
        self._secure_id = self.options.get('secure_id')
        if self._secure_id is not None:
            self._validate_secure_id(self._secure_id)

    def send(self, data, config=None, session_state=None):
        """
        Send data to the specified server.

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
        if config and config.environment is not Unset:
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
        if secure_id is not None:
            self._validate_secure_id(secure_id)
            logger.debug(
                _("Sending to %s, hardware id is %s"), self.url, secure_id)
            headers = {"X_HARDWARE_ID": secure_id}
        else:
            headers = {}
        # Similar handling for submit_to_hexr
        submit_to_hexr = False
        if config is not None and hasattr(config, 'submit_to_hexr'):
            submit_to_hexr = config.submit_to_hexr
            logger.debug(_("submit_to_hexr set to %s by config"),
                         submit_to_hexr)
        if self._submit_to_hexr:
            submit_to_hexr = self._submit_to_hexr
            logger.debug(_("submit_to_hexr set to %s by UI"), submit_to_hexr)
        # We could always set this header since hexr will only process a value
        # of 'True', but this avoids injecting that extraneous knowledge into
        # the tests.
        # Note that hexr will only process a submission with this header's
        # value set to 'True', so this boolean conversion should be ok.
        if submit_to_hexr:
            headers["X-Share-With-HEXR"] = submit_to_hexr

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


def get_all_transports():
    """
    Discover and load all transport classes.

    Returns a map of transports (mapping from name to transport class)
    """
    transport_map = OrderedDict()
    iterator = pkg_resources.iter_entry_points('plainbox.transport')
    for entry_point in sorted(iterator, key=lambda ep: ep.name):
        try:
            transport_cls = entry_point.load()
        except ImportError as exc:
            logger.exception(_("Unable to import {}: {}"), entry_point, exc)
        else:
            transport_map[entry_point.name] = transport_cls
    return transport_map
