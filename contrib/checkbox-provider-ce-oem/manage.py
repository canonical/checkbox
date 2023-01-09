#!/usr/bin/env python3
# Copyright 2022 Canonical Ltd.
# All rights reserved.

"""Management script for the arm provider."""

from plainbox.provider_manager import setup
from plainbox.provider_manager import N_

setup(
    name='checkbox-provider-arm',
    namespace='com.canonical.qa.arm',
    version="0.1",
    description=N_("Checkbox Provider for ARM platforms"),
    gettext_domain='checkbox-provider-arm',
)
