#!/usr/bin/env python3
from plainbox.provider_manager import setup
from plainbox.provider_manager import N_

setup(
    name='checkbox-provider-base',
    namespace='com.canonical.certification',
    version="2.7",
    description=N_("Checkbox provider base"),
    gettext_domain='checkbox-provider-base',
    strict=False, deprecated=False,
)
