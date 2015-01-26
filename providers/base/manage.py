#!/usr/bin/env python3
from plainbox.provider_manager import setup
from plainbox.provider_manager import N_

setup(
    name='2013.com.canonical.certification:checkbox',
    version="0.19",
    description=N_("Checkbox provider"),
    gettext_domain='plainbox-provider-checkbox',
    strict=False, deprecated=False,
)
