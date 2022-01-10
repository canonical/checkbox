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
    name='plainbox-provider-ipdt',
    namespace='com.intel.ipdt',
    version="0.6.0.dev0",
    description=N_("Plainbox Provider for IPDT"),
    gettext_domain='plainbox-provider-ipdt',
)
