#!/usr/bin/env python3
# Copyright 2019 Canonical Ltd.
# All rights reserved.

from plainbox.provider_manager import setup
from plainbox.provider_manager import N_

setup(
    name='checkbox-provider-edgex',
    namespace='com.canonical.certification',
    version="0.1",
    description=N_("Checkbox Provider for EdgeX tests"),
    gettext_domain='checkbox-provider-edgex',
)
