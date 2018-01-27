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
from io import TextIOWrapper
from logging import getLogger
import pkg_resources
import re
from shutil import copyfileobj
import sys

from plainbox.abc import ISessionStateTransport
from plainbox.i18n import gettext as _
from plainbox.impl.exporter import ByteStringStreamTranslator
from plainbox.impl.secure.config import Unset

import requests

# OAuth is not always available on all platforms.
_oauth_available = True
try:
    from oauthlib import oauth1
except ImportError:
    _oauth_available = False


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
    expected to produce data in the proper format (e.g. json, tar).

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


SECURE_ID_PATTERN = r"^[a-zA-Z0-9]{15,}$"


class InvalidSecureIDError(ValueError):

    """Exception raised when the secure ID is formatted incorrectly."""

    def __init__(self, value):
        """Initialize a new exception."""
        self.value = value

    def __str__(self):
        """Get a string representation."""
        return repr(self.value)


def oauth_available():
    return _oauth_available


class NoOauthTransport:
    def __init__(self, **args):
        raise NotImplementedError(
            'This platform does not support the OAuth transport.'
        )


class _OAuthTransport(TransportBase):
    def __init__(self, where, options, transport_details):
        """Initialize the OAuth Transport."""
        super().__init__(where, options)
        self.oauth_creds = transport_details.get('oauth_creds', {})
        self.uploader_email = transport_details['uploader_email']

    def send(self, data, config=None, session_state=None):
        headers = {}
        if self.oauth_creds:
            client = oauth1.Client(
                client_key=self.oauth_creds['consumer_key'],
                client_secret=self.oauth_creds['consumer_secret'],
                resource_owner_key=self.oauth_creds['token_key'],
                resource_owner_secret=self.oauth_creds['token_secret'],
                signature_method=oauth1.SIGNATURE_HMAC,
                realm='Checkbox',
            )
            # The uri is unchanged from self.url, it's the headers we're
            # interested in.
            uri, headers, body = client.sign(self.url, 'POST')
        form_payload = dict(data=data)
        form_data = dict(uploader_email=self.uploader_email)
        try:
            response = requests.post(
                self.url, files=form_payload, data=form_data, headers=headers)
        except requests.exceptions.Timeout as exc:
            raise TransportError('Request to timed out: {}'.format(exc))
        except requests.exceptions.InvalidSchema as exc:
            raise TransportError('Invalid destination URL: {0}'.format(exc))
        except requests.exceptions.ConnectionError as exc:
            raise TransportError('Unable to connect: {0}'.format(exc))
        if response is not None:
            try:
                # This will raise HTTPError for status != 20x
                response.raise_for_status()
            except requests.exceptions.RequestException as exc:
                raise TransportError(str(exc))

        return dict(message='Upload successful.', status=response.status_code)


class StreamTransport(TransportBase):

    """Transport for printing data to a stream (stdout or stderr)."""

    def __init__(self, stream, options=None):
        self._stdout = TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
        self._stderr = TextIOWrapper(sys.stderr.buffer, encoding='utf-8')
        url, self._stream = {
            'stdout': ('python://stdout', self._stdout),
            'stderr': ('python://stderr', self._stderr)
        }[stream]
        super().__init__(url, options)

    def send(self, data, config=None, session_state=None):
        """
        Write data to the specified stream.

        :param data:
            Data to be written to the stream.This can be either bytes or a
            file-like object (BytesIO works fine too).  If this is a file-like
            object, it will be read and streamed "on the fly".
        :param config:
             Optional PlainBoxConfig object.
        :param session_state:
            The session for which this transport is associated with
            the data being sent (optional)
        :returns:
            Empty dictionary
        """
        translating_stream = ByteStringStreamTranslator(
            self._stream, self._stream.encoding)
        copyfileobj(data, translating_stream, -1)
        self._stream.flush()
        return {}


class FileTransport(TransportBase):
    def __init__(self, where, options=None):
        super().__init__(where, options)
        self._path = where

    def send(self, data, config=None, session_state=None):
        """
        Write data to the specified file.

        :param data:
            Data to be written to the stream.This can be either bytes or a
            file-like object (BytesIO works fine too).  If this is a file-like
            object, it will be read and streamed "on the fly".
        :param config:
             Optional PlainBoxConfig object.
        :param session_state:
            The session for which this transport is associated with
            the data being sent (optional)
        :returns:
            A dictionary with url pointing to the file.
        :raises OSError:
            When there was IO related error.
        """
        with open(self._path, 'wb') as f:
            copyfileobj(data, f)
        return {'url': 'file://{}'.format(self._path)}

if oauth_available():
    OAuthTransport = _OAuthTransport
else:
    OAuthTransport = NoOauthTransport


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
