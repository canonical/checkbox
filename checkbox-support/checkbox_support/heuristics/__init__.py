# This file is part of Checkbox.
#
# Copyright 2012 Canonical Ltd.
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
checkbox.heuristics
===================

This module contains implementations behind various heuristics used throughout
the code. The intent of this module is twofold:

    1) To encourage code reuse so that developers can use one implementation of
       "guesswork" that is sometimes needed in our test. This reduces duplicate
       bugs where many scripts do similar things in a different way.

    2) To identify missing features in plumbing layer APIs such as
       udev/udisks/dbus etc. Ideally no program should have to guess this, the
       plumbing layer should be able to provide this meta data to allow
       application developers deliver consistent behavior across userspace.

Heuristics should be reusable from both python and shell. To make that possible
each heuristics needs to be constrained to serializable input and output. This
levels the playing field and allows both shell developers and python developers
to reuse the same function.

Additionally heuristics should try to avoid accessing thick APIs (such as
objects returned by various libraries. This is meant to decrease the likelihood
that updates to those libraries break this code. As an added side effect this
also should make the implementation more explicit and easier to understand.

In the long term each heuristic should be discussed with upstream developers of
the particular problem area (udev, udisks, etc) to see if that subsystem can
provide the required information directly, without us having to guess and fill
the gaps.

Things to consider when adding entries to this package:

    1) File a bug on the upstream package about missing feature.

    2) File a bug on checkbox to de-duplicate similar heuristics
"""
