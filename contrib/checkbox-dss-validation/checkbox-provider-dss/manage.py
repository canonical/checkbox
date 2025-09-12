#!/usr/bin/env python3
#
# This file is part of Checkbox.
#
# Copyright 2022 Canonical Ltd.
#
# Authors:
#     Abdullah (@motjuste) <abdullah.abdullah@canonical.com>
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
from plainbox.provider_manager import setup, N_

# You can inject other stuff here but please don't go overboard.
#
# In particular, if you need comprehensive compilation support to get
# your bin/ populated then please try to discuss that with us in the
# upstream project IRC channel #checkbox on irc.freenode.net.

# NOTE: one thing that you could do here, that makes a lot of sense,
# is to compute version somehow. This may vary depending on the
# context of your provider. Future version of PlainBox will offer git,
# bzr and mercurial integration using the versiontools library
# (optional)

setup(
    name="checkbox-provider-dss-validation",
    namespace="com.canonical.contrib",
    version="1.0",
    description=N_("Checkbox provider to validate Data Science Stack (DSS)"),
    gettext_domain="checkbox-provider-dss-validation",
)
