#!/usr/bin/env python3

from plainbox.provider_manager import setup, N_

setup(
    name="com.canonical.certification:npu",
    version="1.0",
    description=N_("Checkbox provider for NPU testing"),
    gettext_domain="com_canonical_certification_npu",
)
