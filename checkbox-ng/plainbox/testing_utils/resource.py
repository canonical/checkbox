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

"""
:mod:`plainbox.testing_utils.resource`
======================================

Implementation of simple resource sharing cache for unit tests
"""

import logging
import time
import weakref

logger = logging.getLogger("plainbox.testing_utils.resource")


class Dict(dict):
    """
    A dict() that can be weakly referenced

    See: http://docs.python.org/3/library/weakref.html
    """


class List(list):
    """
    A list() that can be weakly referenced

    See: http://docs.python.org/3/library/weakref.html
    """


class ResourceCache:
    """
    Cache for expensive operations.

    If your test needs to compute something (slowly) and reuse it in various
    different test\_ methods then this will save time.
    """

    def __init__(self, weak=True):
        """
        Initialize a new ResourceCache object
        """
        if weak:
            # XXX: it would be nice to have something like true cache semantics of
            # java's SoftReference system. We do the second best thing which is to
            # use weak references on the values held in the cache.
            self._cache = weakref.WeakValueDictionary()
        else:
            self._cache = {}

    def get(self, key, operation):
        """
        Get a value from the cache, falling back to computing it if needed

        Gets something from the cache dictionary, referenced by the key. If the
        value is missing it is computed, by calling the operation, and stored
        in the cache.
        """
        try:
            value = self._cache[key]
            logger.debug("Got cached result for %r", key)
        except KeyError:
            logger.debug("Didn't get cached result for %r", key)
            logger.debug("Computing operation: %r", operation)
            start = time.time()
            value = operation()
            value = self.convert_to_weakref_compat(value)
            end = time.time()
            logger.debug(
                "Computation completed in %s seconds, storing into cache",
                end - start)
            self._cache[key] = value
        return value

    @staticmethod
    def convert_to_weakref_compat(obj):
        """
        Convert the passed object to something that can be weakly reachable
        """
        if obj.__class__ is dict:
            return Dict(obj)
        elif obj.__class__ is tuple or obj.__class__ is list:
            return List(obj)
        else:
            return obj
