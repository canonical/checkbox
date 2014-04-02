#!/usr/bin/env python3
# This file is part of Checkbox.
#
# Copyright 2014 Canonical Ltd.
# Written by:
#   Sylvain Pineau <sylvain.pineau@canonical.com>
#
# Checkbox is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License version 3,
# as published by the Free Software Foundation.

#
# Checkbox is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Checkbox.  If not, see <http://www.gnu.org/licenses/>.

from distutils.ccompiler import new_compiler
from distutils.errors import LinkError
from glob import glob
import os

from DistUtilsExtra.command import build_extra
import DistUtilsExtra.auto

with open("README.rst", encoding="UTF-8") as stream:
    LONG_DESCRIPTION = stream.read()

DATA_FILES = [
    ("/usr/lib/plainbox-providers-1/plainbox-resources/bin",
        glob("provider_bin/*")),
    ("/usr/share/plainbox-providers-1", ["plainbox-resources.provider"])
]


class Build(build_extra.build_extra):

    def run(self):
        # Build our own POTFILES.in as DistUtilsExtra does not include rfc822
        # files automatically
        with open('po/POTFILES.in', 'w') as potfiles_in:
            potfiles_in.write('[encoding: UTF-8]\n')
            for f in glob("provider_jobs/*"):
                potfiles_in.write('[type: gettext/rfc822deb] ' + f + '\n')
            for f in glob("provider_bin/*"):
                potfiles_in.write(f + '\n')

        build_extra.build_extra.run(self)

        cc = new_compiler()
        for source in glob('provider_bin/*.c'):
            executable = os.path.splitext(source)[0]
            try:
                cc.link_executable(
                    [source], executable,
                    libraries=["rt", "pthread", "nl-3", "nl-genl-3"],
                    # Enforce security with CFLAGS + LDFLAGS
                    # See dpkg-buildflags
                    extra_preargs=[
                        "-O2", "-fstack-protector",
                        "--param=ssp-buffer-size=4", "-Wformat",
                        "-Werror=format-security",
                        "-Wl,-Bsymbolic-functions",
                        "-Wl,-z,relro",
                        "-I/usr/include/libnl3"])
            except LinkError as e:
                print('Please install libnl-genl-3-dev on Debian systems')
                raise

        os.unlink('po/POTFILES.in')


DistUtilsExtra.auto.setup(
    # To work as expected, the provider content lives in directories starting
    # with provider_ so that DistUtilsExtra auto features avoid putting files
    # in /usr/bin and /usr/share automatically.
    name="plainbox-provider-resource-generic",
    version="0.3",
    url="https://launchpad.net/checkbox/",
    author="Sylvain Pineau",
    author_email="sylvain.pineau@canonical.com",
    license="GPLv3",
    description="PlainBox resources provider",
    long_description=LONG_DESCRIPTION,
    data_files=DATA_FILES,
    cmdclass={'build': Build},
    )
