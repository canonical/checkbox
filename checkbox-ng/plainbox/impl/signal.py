# Copyright 2012-2015 Canonical Ltd.
# Written by:
#   Zygmunt Krynicki <zygmunt.krynicki@canonical.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License version 3,
# as published by the Free Software Foundation.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
"""
:mod:`plainbox.impl.signal` -- signal system
============================================

.. note::
    This module is now a simple pass-through to the vendorized copy of morris.
"""
__all__ = [
    'Signal',
    'SignalInterceptorMixIn',
    'SignalTestCase',
    'remove_signals_listeners',
    'signal',
]

from plainbox.vendor.morris import Signal
from plainbox.vendor.morris import SignalInterceptorMixIn
from plainbox.vendor.morris import SignalTestCase
from plainbox.vendor.morris import remove_signals_listeners
from plainbox.vendor.morris import signal
