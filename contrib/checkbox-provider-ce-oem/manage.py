#!/usr/bin/env python3
# Copyright 2022 Canonical Ltd.

from plainbox.provider_manager import setup
from plainbox.provider_manager import N_

setup(
    name='checkbox-provider-ce-oem',
    namespace='com.canonical.qa.ceoem',
    version="0.1",
    description=N_("Checkbox provider for both IoT and PC devices"),
    gettext_domain='checkbox-provider-ce-oem',
)
