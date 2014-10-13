# This file is part of Checkbox.
#
# Copyright 2014 Canonical Ltd.
# Written by:
#   Zygmunt Krynicki <zygmunt.krynicki@canonical.com>
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
"""
:mod:`plainbox.impl.device`  -- device classes
==============================================

This module contains implementations

"""
import logging
import os
import shlex
import subprocess
import sys

from plainbox.i18n import gettext as _
from plainbox.impl.ctrl import RootViaPkexecExecutionController
from plainbox.impl.ctrl import RootViaPTL1ExecutionController
from plainbox.impl.ctrl import RootViaSudoExecutionController
from plainbox.impl.ctrl import UserJobExecutionController


_logger = logging.getLogger("plainbox.device")


def get_os_release(path='/etc/os-release'):
    """
    Read and parse os-release(5) data

    :param path:
        (optional) alternate file to load and parse
    :returns:
        A dictionary with parsed data
    """
    with open(path, 'rt', encoding='UTF-8') as stream:
        return {
            key: value
            for key, value in (
                entry.split('=', 1) for entry in shlex.split(stream.read()))
        }


class LocalDevice:
    """
    A device that corresponds to the local machine (the one running plainbox)
    """

    def __init__(self, cookie):
        """
        Initialize a new device with the specified cookie
        """
        self._cookie = cookie

    @property
    def cookie(self):
        """
        Cookie of the device

        Cookie is an URL-like string that describes the current device.
        All devices have a cookie of some kind.
        """
        return self._cookie

    @classmethod
    def discover(cls):
        """
        Discover available devices

        :returns:
            A list of devices of this type that are available. Since this
            is a local device, the following cases are possible:

            On Linux, we return a device based on /etc/os-release
            On Windows, we return a device based on TBD
            On all other platforms (mac?) we return an empty list
        """
        # NOTE: sys.platform used to be 'linux2' on older pythons
        if sys.platform == 'linux' or sys.platform == 'linux2':
            return cls._discover_linux()
        elif sys.platform == 'win32':
            return cls._discover_windows()
        else:
            _logger.error(_("Unsupported platform: %s"), sys.platform)
            return []

    @classmethod
    def _discover_linux(cls):
        """
        A version of :meth:`discover()` that runs on Linux

        :returns:
            A list with one LocalDevice object based on discovered OS
            properties or an empty list if something goes wrong.

        This implementation uses /etc/os-release to figure out where it is
        currently running on. If that fails for any reason (/etc/os-release
        is pretty new by 2014's standards) we return an empty device list.
        """
        # Get /etc/os-release data
        try:
            os_release = get_os_release()
        except (OSError, IOError, ValueError) as exc:
            _logger.error("Unable to analyze /etc/os-release: %s", exc)
            return []
        for arch_probe_fn in (cls._arch_linux_dpkg, cls._arch_linux_rpm):
            try:
                arch = arch_probe_fn()
            except (OSError, subprocess.CalledProcessError):
                pass
            else:
                break
        else:
            arch = cls.arch_linux_uname()
        cookie = cls._cookie_linux_common(os_release, arch)
        return [cls(cookie)]

    @classmethod
    def _discover_windows(cls):
        return [cls("local://localhost/?os=win32")]

    @classmethod
    def _cookie_linux_common(cls, os_release, arch):
        """
        Compute a cookie for a common linux that adheres to os-release(5)

        :param os_release:
            The data structure returned by :func:`get_os_release()`
        :param arch:
            The name of the architecture
        :returns:
            A connection cookie (see below)

        Typical values returned by this method are:
         - "local://localhost/?os=linux&id=debian&version_id=7&arch=amd64"
         - "local://localhost/?os=linux&id=ubuntu&version_id=14.04&arch=amd64"
         - "local://localhost/?os=linux&id=ubunty&version_id=14.09&arch=amd64"
         - "local://localhost/os=linux&id=fedora&version_id=20&arch=x86_64"
        """
        return "local://localhost/?os={}&id={}&version_id={}&arch={}".format(
            "linux", os_release.get("ID", "Linux"),
            os_release.get("VERSION_ID", ""), arch)

    @classmethod
    def _arch_linux_dpkg(cls):
        """
        Query a dpkg-based system for the architecture name

        :returns:
            Debian architecture name, e.g. 'i386', 'amd64' or 'armhf'
        :raises OSError:
            If (typically) ``dpkg`` is not installed
        :raises subprocess.CalledProcessError:
            If dpkg fails for any reason

        The returned cookie depends on the output of::
            ``dpkg --print-architecture``
        """
        return subprocess.check_output(
            ['dpkg', '--print-architecture'], universal_newlines=True
        ).strip()

    @classmethod
    def _arch_linux_rpm(cls):
        """
        Query a rpm-based system for the architecture name

        :returns:
            Debian architecture name, e.g. 'i386', 'x86_64'
        :raises OSError:
            If (typically) ``rpm`` is not installed
        :raises subprocess.CalledProcessError:
            If rpm fails for any reason

        The returned cookie depends on the output of::
            ``rpm -E %_arch``
        """
        return subprocess.check_output(
            ['rpm', '-E', '%_arch'], universal_newlines=True
        ).strip()

    @classmethod
    def _arch_linux_uname(cls):
        """
        Query a linux system for the architecture name via uname(2)

        :returns:
            Architecture name, as returned by os.uname().machine
        """
        return os.uname().machine

    def push_provider(self, provider):
        """
        Push the given provider to this device
        """
        # TODO: raise ValueError if provider.arch is incompatible
        # with self.arch

    def compute_execution_ctrl_list(self, provider_list):
        return [
            RootViaPTL1ExecutionController(provider_list),
            RootViaPkexecExecutionController(provider_list),
            # XXX: maybe this one should be only used on command line
            RootViaSudoExecutionController(provider_list),
            UserJobExecutionController(provider_list),
        ]
