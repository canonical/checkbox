#!/usr/bin/env python3
from plainbox.provider_manager import setup, N_

setup(
    name="tutorial",
    namespace="com.canonical.certification",
    version="1.0",
    description=N_("The Checkbox Tutorial provider"),
    gettext_domain="com_canonical_certification_tutorial",
)
