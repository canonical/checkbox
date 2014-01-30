# This file is part of Checkbox.
#
# Copyright 2013 Canonical Ltd.
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
# Parts copied from Python3.3.1:
#   Steven J. Bethard <steven.bethard@gmail.com>.
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
:mod:`plainbox.impl._argparse` -- support code for argparse compatibility
=========================================================================

This module contains a copy of argparse source code from python3.3.1.  It is
required for compatibility as argparse keeps having subtle changes in behavior
across releases.
"""

import argparse


class LegacyHelpFormatter(argparse.HelpFormatter):
    """
    Vanilla copy of argparse.HelpFormatter from python 3.3.1

    This class retains the behavior of argparse as seen on that version of
    python.  This is done for compatibility and for perfectly identical output
    of PlainBox on various versions of python 3.x.

    Investigation after a rather odd test failure lead to this diff::

        --- raring/argparse.py  2014-01-28 18:52:35.789316074 +0100
        +++ trusty/argparse.py  2014-01-28 19:11:19.121282883 +0100
        @@ -174,6 +174,8 @@
                 self._prog = prog
                 self._indent_increment = indent_increment
                 self._max_help_position = max_help_position
        +        self._max_help_position = min(max_help_position,
        +                                      max(width - 20, indent_increment * 2))
                 self._width = width

                 self._current_indent = 0
        @@ -345,7 +347,7 @@
                             else:
                                 line_len = len(indent) - 1
                             for part in parts:
        -                        if line_len + 1 + len(part) > text_width:
        +                        if line_len + 1 + len(part) > text_width and line:
                                     lines.append(indent + ' '.join(line))
                                     line = []
                                     line_len = len(indent) - 1
        @@ -485,7 +487,7 @@
             def _format_text(self, text):
                 if '%(prog)' in text:
                     text = text % dict(prog=self._prog)
        -        text_width = self._width - self._current_indent
        +        text_width = max(self._width - self._current_indent, 11)
                 indent = ' ' * self._current_indent
                 return self._fill_text(text, text_width, indent) + '\n\n'

        @@ -493,7 +495,7 @@
                 # determine the required width and the entry label
                 help_position = min(self._action_max_length + 2,
                                     self._max_help_position)
        -        help_width = self._width - help_position
        +        help_width = max(self._width - help_position, 11)
                 action_width = help_position - self._current_indent - 2
                 action_header = self._format_action_invocation(action)

    The relevant part is the second change, involving the addition of ``and line``.
    It causes a line not to be printed, where it otherwise would. Since this is
    a minor visual change we chose to retain the current behavior.

    In the future, especially when python3.4 is the base version and older
    versions are not supported, a reverse patch might be applied and held here,
    to provide the non-legacy behavior.
    """

    def _format_usage(self, usage, actions, groups, prefix):
        if prefix is None:
            prefix = argparse._('usage: ')

        # if usage is specified, use that
        if usage is not None:
            usage = usage % dict(prog=self._prog)

        # if no optionals or positionals are available, usage is just prog
        elif usage is None and not actions:
            usage = '%(prog)s' % dict(prog=self._prog)

        # if optionals and positionals are available, calculate usage
        elif usage is None:
            prog = '%(prog)s' % dict(prog=self._prog)

            # split optionals from positionals
            optionals = []
            positionals = []
            for action in actions:
                if action.option_strings:
                    optionals.append(action)
                else:
                    positionals.append(action)

            # build full usage string
            format = self._format_actions_usage
            action_usage = format(optionals + positionals, groups)
            usage = ' '.join([s for s in [prog, action_usage] if s])

            # wrap the usage parts if it's too long
            text_width = self._width - self._current_indent
            if len(prefix) + len(usage) > text_width:

                # break usage into wrappable parts
                part_regexp = r'\(.*?\)+|\[.*?\]+|\S+'
                opt_usage = format(optionals, groups)
                pos_usage = format(positionals, groups)
                opt_parts = argparse._re.findall(part_regexp, opt_usage)
                pos_parts = argparse._re.findall(part_regexp, pos_usage)
                assert ' '.join(opt_parts) == opt_usage
                assert ' '.join(pos_parts) == pos_usage

                # helper for wrapping lines
                def get_lines(parts, indent, prefix=None):
                    lines = []
                    line = []
                    if prefix is not None:
                        line_len = len(prefix) - 1
                    else:
                        line_len = len(indent) - 1
                    for part in parts:
                        if line_len + 1 + len(part) > text_width:
                            lines.append(indent + ' '.join(line))
                            line = []
                            line_len = len(indent) - 1
                        line.append(part)
                        line_len += len(part) + 1
                    if line:
                        lines.append(indent + ' '.join(line))
                    if prefix is not None:
                        lines[0] = lines[0][len(indent):]
                    return lines

                # if prog is short, follow it with optionals or positionals
                if len(prefix) + len(prog) <= 0.75 * text_width:
                    indent = ' ' * (len(prefix) + len(prog) + 1)
                    if opt_parts:
                        lines = get_lines([prog] + opt_parts, indent, prefix)
                        lines.extend(get_lines(pos_parts, indent))
                    elif pos_parts:
                        lines = get_lines([prog] + pos_parts, indent, prefix)
                    else:
                        lines = [prog]

                # if prog is long, put it on its own line
                else:
                    indent = ' ' * len(prefix)
                    parts = opt_parts + pos_parts
                    lines = get_lines(parts, indent)
                    if len(lines) > 1:
                        lines = []
                        lines.extend(get_lines(opt_parts, indent))
                        lines.extend(get_lines(pos_parts, indent))
                    lines = [prog] + lines

                # join lines into usage
                usage = '\n'.join(lines)

        # prefix with 'usage:'
        return '%s%s\n\n' % (prefix, usage)
