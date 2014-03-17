#!/usr/bin/env python3
# This file is part of Checkbox.
#
# Copyright 2012, 2013 Canonical Ltd.
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


from plainbox.provider_manager import setup, N_
from plainbox.impl.providers.special import get_stubbox_def

# NOTE: this is not a good example of manage.py as it is internally bound to
# plainbox. Don't just copy paste this as good design, it's *not*.
# Use `plainbox startprovider` if you want to get a provider template to edit.
stubbox_def = get_stubbox_def()

# This is stubbox_def.description, we need it here to extract is as a part of
# stubbox
N_("StubBox (dummy data for development)")

setup(
    name=stubbox_def.name,
    version=stubbox_def.version,
    description=stubbox_def.description,
    gettext_domain=stubbox_def.gettext_domain
)
