#!/usr/bin/env python3
import os
import shutil
import subprocess

from plainbox.provider_manager import N_
from plainbox.provider_manager import SourceDistributionCommand
from plainbox.provider_manager import manage_py_extension
from plainbox.provider_manager import setup


@manage_py_extension
class SourceDistributionCommandExt(SourceDistributionCommand):
    # Overridden version of SourceDistributionCommand that handles autotools
    __doc__ = SourceDistributionCommand.__doc__
    _GENERATED_ITEMS = [
        'INSTALL',
        'Makefile.in',
        'aclocal.m4',
        'compile',
        'config.h.in',
        'configure',
        'depcomp',
        'install-sh',
        'missing',
    ]

    @property
    def src_dir(self):
        return os.path.join(self.definition.location, "src")

    def invoked(self, ns):
        # Update the configure script
        subprocess.check_call(['autoreconf', '-i'], cwd=self.src_dir)
        # Remove autom4te.cache, we don't need it in our source tarballs
        # http://www.gnu.org/software/autoconf/manual/autoconf-2.64/html_node/Autom4te-Cache.html
        shutil.rmtree(os.path.join(self.src_dir, 'autom4te.cache'))
        # Generate the source tarball
        super().invoked(ns)
        # Remove generated autotools stuff
        for item in self._GENERATED_ITEMS:
            os.remove(os.path.join(self.src_dir, item))

setup(
    name='checkbox-provider-resource',
    namespace='com.canonical.certification',
    version="2.7",
    description=N_("Checkbox provider resource"),
    gettext_domain='checkbox-provider-resource',
    strict=False, deprecated=False,
)
