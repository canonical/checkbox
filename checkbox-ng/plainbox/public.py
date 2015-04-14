# This file is part of Checkbox.
#
# Copyright 2012-2015 Canonical Ltd.
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
Public, stable, high-level API for third party developers.

:mod:`plainbox.public`
======================

The are actually implemented by the plainbox.impl package. This module is here
so that the essential API concepts are in a single spot and are easier to
understand (by not being mixed with additional source code).

.. warning::

    This module is ironically UNSTABLE until the 1.0 release

.. note::

    This module has API stability guarantees. We are not going to break or
    introduce backwards incompatible interfaces here without following our API
    deprecation policy. All existing features will be retained for at least
    three releases. All deprecated symbols will warn when they will cease to be
    available.
"""

from plainbox._lazymod import LazyModule, far


_mod = LazyModule.shadow_normal_module()
_mod.lazily('main', far, ('plainbox.impl.box:main',))
_mod.lazily('get_providers', far, ('plainbox.impl.providers:get_providers',))
