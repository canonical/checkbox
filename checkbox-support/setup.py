#!/usr/bin/env python3
# This file is part of Checkbox.
#
# Copyright 2014 Canonical Ltd.
# Written by:
#   Sylvain Pineau <sylvain.pineau@canonical.com>
#
# CloudBox is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# CloudBox is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with CloudBox.  If not, see <http://www.gnu.org/licenses/>.

import os
import sys

from io import open  # For compatibility with Python 2.7
from setuptools import setup, find_packages

if "test" in sys.argv:
    # Reset locale for setup.py test
    os.environ["LANG"] = ""
    os.environ["LANGUAGE"] = ""
    os.environ["LC_ALL"] = "C.UTF-8"

base_dir = os.path.dirname(__file__)

# Load the README.rst file relative to the setup file
with open(os.path.join(base_dir, "README.rst"), encoding="UTF-8") as stream:
    long_description = stream.read()

setup(
    name="checkbox-support",
    version="2.7",
    url="https://launchpad.net/checkbox/",
    packages=find_packages(),
    test_suite='checkbox_support.tests.test_suite',
    author="Sylvain Pineau",
    author_email="sylvain.pineau@canonical.com",
    license="GPLv3",
    description="CheckBox support library",
    long_description=long_description,
    package_data={"checkbox_support": ["parsers/cputable"]},
    install_requires=["pyparsing >= 2.2.0", "requests >= 1.0", "distro >= 1.0"]
    + (["configparser"] if sys.version_info.major == 2 else [])
    + (["requests_unixsocket >= 0.1.2"] if sys.version_info >= (3, 5) else [])
    + (["importlib_metadata"] if sys.version_info < (3, 8) else []),
    include_package_data=True,
    entry_points={
        'plainbox.parsers': [
            "pactl-list=checkbox_support.parsers.pactl:parse_pactl_output",
            "udevadm=checkbox_support.parsers.udevadm:parse_udevadm_output",
            ("modprobe=checkbox_support.parsers.modprobe:parse_modprobe_d"
             "_output"),
            ("pci-subsys-id=checkbox_support.parsers.pci_config:parse_pci"
             "_subsys_id"),
            "dkms-info=checkbox_support.parsers.dkms_info:parse_dkms_info",
            ("dmidecode=checkbox_support.parsers.dmidecode:parse_dmidecode"
             "_output"),
            ("modinfo=checkbox_support.parsers.modinfo:parse_modinfo"
             "_attachment_output"),
            ("buildstamp=checkbox_support.parsers.image_info:parse_buildstamp"
             "_attachment_output"),
            ("recovery-info=checkbox_support.parsers.image_info:parse_recovery"
             "_info_attachment_output"),
            ("bto=checkbox_support.parsers.image_info:parse_bto_attachment"
             "_output"),
            ("kernelcmdline=checkbox_support.parsers.kernel_cmdline:parse"
             "_kernel_cmdline"),
        ],
        'console_scripts': [
            ("checkbox-support-run_watcher="
                "checkbox_support.scripts.run_watcher:main"),
            ("checkbox-support-fwts_test="
                "checkbox_support.scripts.fwts_test:main"),
            ("checkbox-support-usb_read_write="
                "checkbox_support.scripts.usb_read_write:run_read_write_test"),
            ("checkbox-support-nmea_test="
                "checkbox_support.scripts.nmea_test:main"),
            ("checkbox-support-snap_connect="
                "checkbox_support.scripts.snap_connect:main"),
            ("checkbox-support-eddystone_scanner="
                "checkbox_support.scripts.eddystone_scanner:main"),
            ("checkbox-support-lsusb="
                "checkbox_support.scripts.lsusb:main"),
            ("checkbox-support-parse=checkbox_support.parsers:main"),
            ("checkbox-support-zapper-proxy="
                "checkbox_support.scripts.zapper_proxy:main"),
        ],
    },
)
