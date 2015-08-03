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
