#!/usr/bin/env python3
# This file is part of Checkbox.
#
# Copyright 2025 Canonical Ltd.
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

import plainbox
from plainbox.provider_manager import setup, N_

setup(
    name='checkbox-provider-dpdk',
    namespace="com.canonical.certification",
    version=plainbox.__version__,
    description=N_("Checkbox Provider for Data Plane Development Kit (DPDK)"),
    gettext_domain="checkbox-provider-dpdk",
)