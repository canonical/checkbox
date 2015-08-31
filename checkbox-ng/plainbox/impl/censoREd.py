# This file is part of Checkbox.
#
# Copyright 2015 Canonical Ltd.
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
:mod:`plainbox.impl.censoREd` -- working around frustrating stuff
=================================================================

This module is the result of an evening of frustration caused by the need to
support Python 3.2 and a failing doctest that exercises, unintentionally, the
behavior of the compiled regular expression object's __repr__() method. That
should be something we can fix, right?  Let's not get crazy here:

    >>> import re
    >>> sre_cls = type(re.compile(""))
    >>> sre_cls
    <class '_sre.SRE_Pattern'>

Aha, we have a nice type. It's only got a broken __repr__ method that sucks.
But this is Python, we can fix that? Right?

    >>> sre_cls.__repr__ = (
    ...     lambda self: "re.compile({!r})".format(self.pattern))
    ... # doctest: +NORMALIZE_WHITESPACE
    Traceback (most recent call last):
    ...
    TypeError: can't set attributes of built-in/extension
               type '_sre.SRE_Pattern'

Hmm, okay, so let's try something else:

    >>> class Pattern(sre_cls):
    ...     def __repr__(self):
    ...         return "re.compile({!r})".format(self.pattern)
    Traceback (most recent call last):
    ...
    TypeError: type '_sre.SRE_Pattern' is not an acceptable base type

*Sigh*, denial, anger, bargaining, depression, acceptance
https://twitter.com/zygoon/status/560088469192843264

The last resort, aka, the proxy approach. Let's use a bit of magic to work
around the problem. This way we won't have to subclass or override anything.
"""
from padme import proxy


__all__ = ["PatternProxy"]


class PatternProxy(proxy):
    """
    A proxy that overrides the __repr__() to match what Python 3.3+ providers
    on the internal object representing a compiled regular expression.

        >>> import re
        >>> sre_cls = type(re.compile(""))
        >>> pattern = PatternProxy(re.compile("profanity"))

    Can we have a repr() like in Python3.4 please?

        >>> pattern
        re.compile('profanity')

    Does it still work like a normal pattern object?

        >>> pattern.match("profanity") is not None
        True
        >>> pattern.match("love") is not None
        False

    **Yes** (gets another drink).
    """
    @proxy.direct
    def __repr__(self):
        return "re.compile({!r})".format(self.pattern)
