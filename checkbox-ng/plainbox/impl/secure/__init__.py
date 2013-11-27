# This file is part of Checkbox.
#
# Copyright 2013 Canonical Ltd.
# Written by:
#   Sylvain Pineau <sylvain.pineau@canonical.com>
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
:mod:`plainbox.impl.secure` -- code for external (trusted) launchers
====================================================================

This package keeps all of the plainbox code that is executed as root. It should
be carefully reviewed to ensure that we don't introduce security issues that
could allow unpriviledged uses to exploit plainbox to run arbitrary commands as
root.

None of the modues in the secure package may import code that is not coming
from either the plainbox secure package or from the standard python library.
"""
