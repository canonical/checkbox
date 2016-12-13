#!/usr/bin/env python3
from plainbox.provider_manager import InstallCommand
from plainbox.provider_manager import manage_py_extension
from plainbox.provider_manager import setup
from plainbox.provider_manager import N_

import os, shutil

@manage_py_extension
class InstallPyModules(InstallCommand):
    """
    copy additional (non executable) Python module needed by the bin scripts
    
    @EPILOG@

    This command copies non executable Python module needed by a script written
    to test Bluetooth connectivity.
    """
    # Fixes lp:1612080
    name = 'install'

    def invoked(self, ns):
        super().invoked(ns)
        dest_map = self._get_dest_map(ns.layout, ns.prefix)
        provider = self.get_provider()
        shutil.copy(
            os.path.join(provider.bin_dir, 'bt_helper.py'),
            ns.root + dest_map['bin'])

setup(
    name='plainbox-provider-checkbox',
    namespace='2013.com.canonical.certification',
    version="0.34.0.dev0",
    description=N_("Checkbox provider"),
    gettext_domain='plainbox-provider-checkbox',
    strict=False, deprecated=False,
)
