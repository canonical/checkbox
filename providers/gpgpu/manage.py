#!/usr/bin/env python3
# Copyright 2015-2019 Canonical Ltd.
# All rights reserved.
#
# Written by:
#   Zygmunt Krynicki <zygmunt.krynicki@canonical.com>
#   Jonathan Cave <jonathan.cave@canonical.com>

from plainbox.provider_manager import setup
from plainbox.provider_manager import N_

setup(
    name='checkbox-provider-gpgpu',
    namespace='com.canonical.certification',
    version="0.4.0",
    description=N_("Checkbox Provider for GPGPU Testing"),
    gettext_domain='checkbox-provider-gpgpu',
)
