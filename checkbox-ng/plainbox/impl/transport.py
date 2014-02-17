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
:mod:`plainbox.impl.transport` -- shared code for test data transports
======================================================================

.. warning::

    THIS MODULE DOES NOT HAVE STABLE PUBLIC API
"""

from abc import ABCMeta, abstractmethod
from collections import OrderedDict
from logging import getLogger

import pkg_resources

from plainbox.i18n import gettext as _


logger = getLogger("plainbox.transport")


class TransportBase(metaclass=ABCMeta):
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
        self.url = where
        #parse option string only if there's at least one k=v pair
        self.options = {}
        if not option_string:
            return
        if "=" in option_string:
            self.options = {option: value for (option, value) in
                            [pair.split("=", 1) for pair in
                            option_string.split(",")]}
        if not self.options:
            raise ValueError(_("No valid options in option string"))

    @abstractmethod
    def send(self, data):
        """
        Send data somewhere.

        Data is the stream of data to send, its format depends on the
        receiving end. It should be a file-like object.

        """


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
