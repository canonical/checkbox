# This file is part of Checkbox.
#
# Copyright 2014 Canonical Ltd.
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
#
# Parts copied from Python3.4:
#   Copyright (C) 1999-2001 Gregory P. Ward.
#   Copyright (C) 2002, 2003 Python Software Foundation.
#   Written by Greg Ward <gward@python.net>
#
# PYTHON SOFTWARE FOUNDATION LICENSE VERSION 2
# --------------------------------------------
#
# 1. This LICENSE AGREEMENT is between the Python Software Foundation ("PSF"),
#    and the Individual or Organization ("Licensee") accessing and otherwise
#    using this software ("Python") in source or binary form and its associated
#    documentation.
#
# 2. Subject to the terms and conditions of this License Agreement, PSF hereby
#    grants Licensee a nonexclusive, royalty-free, world-wide license to
#    reproduce, analyze, test, perform and/or display publicly, prepare
#    derivative works, distribute, and otherwise use Python alone or in any
#    derivative version, provided, however, that PSF's License Agreement and
#    PSF's notice of copyright, i.e., "Copyright (c) 2001, 2002, 2003, 2004,
#    2005, 2006, 2007, 2008, 2009, 2010, 2011, 2012, 2013, 2014 Python Software
#    Foundation; All Rights Reserved" are retained in Python alone or in any
#    derivative version prepared by Licensee.
#
# 3. In the event Licensee prepares a derivative work that is based on or
#    incorporates Python or any part thereof, and wants to make the derivative
#    work available to others as provided herein, then Licensee hereby agrees
#    to include in any such work a brief summary of the changes made to Python.
#
# 4. PSF is making Python available to Licensee on an "AS IS" basis.  PSF MAKES
#    NO REPRESENTATIONS OR WARRANTIES, EXPRESS OR IMPLIED.  BY WAY OF EXAMPLE,
#    BUT NOT LIMITATION, PSF MAKES NO AND DISCLAIMS ANY REPRESENTATION OR
#    WARRANTY OF MERCHANTABILITY OR FITNESS FOR ANY PARTICULAR PURPOSE OR THAT
#    THE USE OF PYTHON WILL NOT INFRINGE ANY THIRD PARTY RIGHTS.
#
# 5. PSF SHALL NOT BE LIABLE TO LICENSEE OR ANY OTHER USERS OF PYTHON FOR ANY
#    INCIDENTAL, SPECIAL, OR CONSEQUENTIAL DAMAGES OR LOSS AS A RESULT OF
#    MODIFYING, DISTRIBUTING, OR OTHERWISE USING PYTHON, OR ANY DERIVATIVE
#    THEREOF, EVEN IF ADVISED OF THE POSSIBILITY THEREOF.
#
# 6. This License Agreement will automatically terminate upon a material breach
#    of its terms and conditions.
#
# 7. Nothing in this License Agreement shall be deemed to create any
#    relationship of agency, partnership, or joint venture between PSF and
#    Licensee.  This License Agreement does not grant permission to use PSF
#    trademarks or trade name in a trademark sense to endorse or promote
#    products or services of Licensee, or any third party.
#
# 8. By copying, installing or otherwise using Python, Licensee agrees to be
#    bound by the terms and conditions of this License Agreement.


"""
:mod:`plainbox.impl._textwrap` -- support code for textwrap compatibility
=========================================================================

This module contains a copy of textwrap source code from python3.4
"""


def _textwrap_indent(text, prefix, predicate=None):
    """Adds 'prefix' to the beginning of selected lines in 'text'.

    If 'predicate' is provided, 'prefix' will only be added to the lines
    where 'predicate(line)' is True. If 'predicate' is not provided,
    it will default to adding 'prefix' to all non-empty lines that do not
    consist solely of whitespace characters.
    """
    if predicate is None:
        def predicate(line):
            return line.strip()

    def prefixed_lines():
        for line in text.splitlines(True):
            yield (prefix + line if predicate(line) else line)
    return ''.join(prefixed_lines())
