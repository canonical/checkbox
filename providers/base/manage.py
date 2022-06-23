#!/usr/bin/env python3
from plainbox.provider_manager import setup
from plainbox.provider_manager import N_

setup(
    name='plainbox-provider-checkbox',
    namespace='com.canonical.certification',
    version="0.65.0rc2",
    description=N_("Checkbox provider"),
    gettext_domain='plainbox-provider-checkbox',
    strict=False, deprecated=False,
)
