#!/usr/bin/env python3
from plainbox.provider_manager import setup, N_

# NOTE: one thing that you could do here, that makes a lot of sense,
# is to compute version somehow. This may vary depending on the
# context of your provider. Future version of PlainBox will offer git,
# bzr and mercurial integration using the versiontools library
# (optional)

setup(
    name="checkbox-provider-oem",
    namespace="com.canonical.contrib",
    version="0.4.0",
    description=N_("The checkbox oem provider"),
    gettext_domain="checkbox-provider-oem",
)
