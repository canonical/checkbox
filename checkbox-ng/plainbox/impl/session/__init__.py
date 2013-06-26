# This file is part of Checkbox.
#
# Copyright 2012, 2013 Canonical Ltd.
# Written by:
#   Zygmunt Krynicki <zygmunt.krynicki@canonical.com>
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
:mod:`plainbox.impl.session` -- session state handling
======================================================

.. warning::

    THIS MODULE DOES NOT HAVE STABLE PUBLIC API
"""

__all__ = ['JobState', 'JobReadinessInhibitor',
           'UndesiredJobReadinessInhibitor', 'SessionState',
           'SessionStateEncoder']

from plainbox.impl.session.jobs import JobState, JobReadinessInhibitor
from plainbox.impl.session.jobs import UndesiredJobReadinessInhibitor
from plainbox.impl.session.state import SessionState, SessionStateEncoder
