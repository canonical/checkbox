# This file is part of Checkbox.
#
# Copyright 2012-2018 Canonical Ltd.
# Written by:
#   Zygmunt Krynicki <zygmunt.krynicki@canonical.com>
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
:mod:`plainbox` -- main package
===============================

Simple checkbox (2008 version) redesign, without the complex message passing

All abstract base classes are in :mod:`plainbox.abc`.
"""

# PEP440 compliant version declaration.
#
# This is used by @public decorator to enforce our public API guarantees.
__version__ = '1.17.0rc1'

def get_version_string():
    import os
    version_string = ''
    if os.environ.get('SNAP_NAME'):
        version_string = '{} {} ({})'.format(
            os.environ['SNAP_NAME'],
            os.environ.get('SNAP_VERSION', 'unknown_version'),
            os.environ.get('SNAP_REVISION', 'unknown_revision')
        )
    else:
        version_string = '{} {}'.format('Checkbox', __version__)
    return version_string
