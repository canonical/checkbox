#!/usr/bin/env python3
import plainbox

from plainbox.provider_manager import setup
from plainbox.provider_manager import N_

setup(
    name='checkbox-provider-base',
    namespace='com.canonical.certification',
    version=plainbox.__version__,
    description=N_("Checkbox provider base"),
    gettext_domain='checkbox-provider-base',
    strict=False, deprecated=False,
)
