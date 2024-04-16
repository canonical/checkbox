#!/usr/bin/env python3
# encoding: utf-8
# Copyright 2015 Canonical Ltd.
# Written by:
#   Shawn Wang <shawn.wang@canonical.com>
#   Zygmunt Krynicki <zygmunt.krynicki@canonical.com>
#   Jonathan Cave <jonathan.cave@canonical.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License version 3,
# as published by the Free Software Foundation.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

"""
dkms_info provides device package information.

supported package types:
 - dkms (Dynamic Kernel Module Support): provides kernel modules
 - non-dkms: packages that with modaliases header and don't exist in dkms list
  - hardware modalias: might be unused dkms or config package
  - oemalias: It is like non-dkms(w/o modalias)
supported output format:
 - onelines: one line per packages with matched modaliases information
 - dumps: json output (fully information)
"""

import argparse
import fnmatch
import functools
import email.parser
import io
import json
import logging
import os
import subprocess
import sys


_logger = logging.getLogger(None)


@functools.lru_cache()
def get_system_module_list():
    """
    Use lsmod to list current kernel modules.

    :returns:
        A list of module names that are loaded into the current kernel.
    """
    _logger.info("Looking at inserted kernel modules")
    modules = []
    with io.open("/proc/modules", "rt", encoding="UTF-8") as stream:
        for line in stream.readlines():
            modules.append(line.split()[0].strip())
    return modules


@functools.lru_cache()
def get_system_modaliases():
    r"""
    List machine modaliases.

    :returns:
        dict of hardware modaliases.
        key: modalias_type
        value: list of modalias_string
    """
    _logger.info("Looking for modalias files in /sys/devices")

    result = {}
    name = "modalias"
    for root, dirs, files in os.walk("/sys/devices/"):
        if name in files:
            with io.open(
                os.path.join(root, name), "rt", encoding="UTF-8"
            ) as stream:
                data = stream.read().strip()
                pattern_array = data.split(":", 1)
                if len(pattern_array) < 2:
                    _logger.warning(
                        "skip pattern {}, not a valid modalias".format(data)
                    )
                    continue
                (modalias_type, modalias_string) = pattern_array

                if modalias_type not in result:
                    result[modalias_type] = []
                if modalias_string not in result[modalias_type]:
                    result[modalias_type].append(modalias_string)
    return result


def get_installed_dkms_modules():
    """
    Query dkms_status from /var/lib/dkms/.

    An installed dkms module has the below directory.
    /var/lib/dkms/<dkms_name>/<dkms_ver>/<kernel_ver>

    :returns:
        list of (<dkms_name>, <dkms_ver>)
    """
    _dkmses = []
    _logger.info("Querying dkms database")

    path = "/var/lib/dkms/"
    for root, dirs, files in os.walk(path):
        if os.uname().release in dirs:
            dkms = root[len(path) :].split("/")
            if len(dkms) != 2:
                continue
            _dkmses.append(dkms)
    return _dkmses


@functools.lru_cache()
def match_patterns(patterns):
    """
    Check modalias patterns matched with modalias, or type is oemalias.

    oemalias is a special pattern_type for oem.
    :param patterns:
        list of modalias pattern from debian package.
    :returns:
        list of modalias pattern matched with hardware modalias
    """
    _logger.info("Looking for modalias objects matching")
    matched = []
    if not patterns:
        return matched
    hw_modaliases = get_system_modaliases()
    for pattern in patterns:
        pattern_array = pattern.split(":", 1)
        if len(pattern_array) < 2:
            _logger.info("skip pattern {}, can't find type".format(pattern))
            continue

        (pattern_type, pattern_string) = pattern_array

        if pattern_type == "oemalias":
            matched.append(pattern)
        if pattern_type not in hw_modaliases:
            continue
        for item in hw_modaliases[pattern_type]:
            if fnmatch.fnmatch(item, pattern_string):
                matched.append(pattern)
    return matched


class DkmsPackage(object):
    """
    Handle DKMS type device package, DKMS is a kernel module framework.

    It generate modules for installed kernel or different kernel versions.
    The dkms modules will be copied to /lib/modulesa/`uname -r`/updates/dkms/.
    Those modules might be load by modaliases information.
    """

    def __init__(self, name, version):
        """
        init of DkmsPackage, define all the attribute.

        :param name:
            DKMS module name
        :param version:
            DKMS module version
        """
        self.dkms_name = name
        self.dkms_ver = version
        self.pkg_name = self._query_package()
        self.kernel_ver = os.uname().release
        self.arch = os.uname().machine
        self.mods = self._list_modules()
        self.install_mods = self._list_install_modules()
        self.pkg = None

    def _query_package(self):
        """
        Query debian package of dkms.

        Use dpkg -S to check dkms src path of debian package.

        :return:
            string of package name or None
        """
        path = "/usr/src/{}-{}/dkms.conf".format(self.dkms_name, self.dkms_ver)
        _logger.info("Looking for packages that provide: %s", path)
        dpkg_info_root = "/var/lib/dpkg/info"
        for fn in os.listdir(dpkg_info_root):
            if not fn.endswith(".list"):
                continue
            with io.open(
                os.path.join(dpkg_info_root, fn), "rt", encoding="UTF-8"
            ) as stream:
                if path in stream.read():
                    return fn[: -len(".list")]
        return None

    def _list_modules(self):
        """
        List all the kernel modules that provide by the dkms package.

        Module name (.ko) with "-" will be replace to "_" when module loaded.

        :param path:
            The directory to look at.
        :return:
            List of kernel modules
        """
        path = "/var/lib/dkms/{}/{}/{}/{}/module".format(
            self.dkms_name, self.dkms_ver, self.kernel_ver, self.arch
        )
        _logger.info("Looking for kernel modules in %s", path)
        result = []
        for module_file in os.listdir(path):
            (module, extension) = os.path.splitext(module_file)
            if extension == ".ko":
                result.append(module.replace("-", "_"))
        return result

    def _list_install_modules(self):
        """
        Return a dict of install_modules.

        key is installed module name
        value is tuple of matched patterns

        :return:
            Dict of installed dkms modules
        """
        install_mods = {}
        for m in self.mods:
            if m not in get_system_module_list():
                continue
            _logger.info("Inspecting module %s", m)

            output = subprocess.check_output(
                ["modinfo", m], universal_newlines=True
            )
            aliases = []
            for line in output.splitlines():
                if not line.startswith("alias:"):
                    continue

                key, value = line.split(":", 1)
                aliases.append(value.strip())

            install_mods[m] = match_patterns(tuple(aliases))
        return install_mods


def _headers_to_dist(pkg_str):
    """
    Convert rft822 headers string to dict.

    :param headers:
        deb822 headers object
    :return:
        dict, the key is lowercase of deb822 headers key
    """

    header = email.parser.Parser().parsestr(pkg_str)
    target = {}
    for key in header.keys():
        target[key.lower()] = header[key]
    return target


class DebianPackageHandler(object):
    """Use rtf822(email) to handle the package information from file_object."""

    def __init__(self, extra_pkgs=[], file_object=None):
        """
        DebianPackageHandler.

        :param file_object:
           default file open from /var/lib/dpkg/status,
           where stored system package information
        """
        if file_object is None:
            file_object = io.open(
                "/var/lib/dpkg/status", "rt", encoding="UTF-8"
            )
        self._file_object = file_object
        self.extra_pkgs = extra_pkgs
        self.pkgs = self._get_device_pkgs()

    def _gen_all_pkg_strs(self):
        """
        Get package information in /var/lib/dpkg/status.

        :returns:
           A generator of debian package.
        """
        _logger.info("Loading information about all packages")
        for pkg_str in self._file_object.read().split("\n\n"):
            yield pkg_str

    def _get_device_pkgs(self):
        """
        Only device packages have debian package header 'Modaliases'.

        This method get packages with the key ``modaliases``.
        Use the method instead of get_all_pkgs for performance issues.

        :returns:
           A list of dict , the dict is converted from debian package header.
        """

        _logger.info("Looking for packages providing modaliases")
        result = {}

        for pkg_str in self._gen_all_pkg_strs():

            for pkg in self.extra_pkgs:
                if pkg.pkg_name is None:
                    continue
                pstr = "Package: {}".format(pkg.pkg_name)
                if pstr in pkg_str:
                    _logger.info(
                        "Gathering information of package, {}".format(
                            pkg.pkg_name
                        )
                    )
                    pkg.pkg = _headers_to_dist(pkg_str)
                    break
            else:
                if "Modaliases:" in pkg_str:
                    pkg = _headers_to_dist(pkg_str)

                    (modalias_header, pattern_str) = (
                        pkg["modaliases"].strip(")").split("(")
                    )
                    patterns = pattern_str.split(", ")
                    patterns.sort()
                    pkg["match_patterns"] = match_patterns(tuple(patterns))

                    dpkgf = "/var/lib/dpkg/info/{}.list".format(pkg["package"])
                    with io.open(dpkgf, "rt", encoding="UTF-8") as stream:
                        if "/dkms.conf" in stream.read():
                            pkg["unused_dkms"] = True
                    result[pkg["package"]] = pkg
        return result

    def to_json(self):
        return json.dumps(
            {"dkms": self.extra_pkgs, "non-dkms": self.pkgs},
            default=lambda o: o.__dict__,
            sort_keys=True,
            indent=4,
        )

    def to_outline(self):
        result = ""
        for pkg in self.extra_pkgs:
            if pkg.pkg is None:
                continue
            result = "{}\n{}_{}: {}".format(
                result, pkg.pkg_name, pkg.pkg["version"], pkg.install_mods
            )
        for pkg_name, pkg in self.pkgs.items():
            extra_str = ""
            if "unused_dkms" in pkg:
                extra_str = "- "
            result = "{}\n{}{}_{}: {}".format(
                result,
                extra_str,
                pkg_name,
                pkg["version"],
                pkg["match_patterns"],
            )
        return result


class DeviceInfo:
    """
    Implementation of the dkms-info command.

    dkms_info provides device package information.

    @EPILOG@

    supported package types:
     - dkms (Dynamic Kernel Module Support): provides kernel modules
     - non-dkms: packages that with modaliases header and don't exist in dkms
       list
     - hardware modalias: might be unused dkms or config package
     - oemalias: It is like non-dkms(w/o modalias)

    supported output formats:
     - onelines: one line per packages with matched modaliases information
     - dumps: json output (fully information)
    """

    def main(self):
        """Invoke dkms-info."""
        parser = argparse.ArgumentParser()
        parser.add_argument(
            "--format",
            default="onelines",
            choices=["summary", "json"],
            help=(
                "Choose output format type: "
                "summary (one line per packages) "
                "or json (json format, fully information)"
            ),
        )
        parser.add_argument(
            "--output",
            default=None,
            help=("Output filename to store the output date"),
        )
        args = parser.parse_args()

        logging.basicConfig(
            level=logging.INFO, format="[%(relativeCreated)06dms] %(message)s"
        )
        _logger.info("Started")

        dkms_pkgs = []
        for dkms_name, dkms_ver in get_installed_dkms_modules():
            dkms_pkg = DkmsPackage(dkms_name, dkms_ver)
            dkms_pkgs.append(dkms_pkg)

        output = sys.stdout
        if args.output is not None:
            output = open(args.output, "wt", encoding="UTF-8")

        pkg_handler = DebianPackageHandler(extra_pkgs=dkms_pkgs)
        if args.format == "summary":
            output.write(pkg_handler.to_outline())
        else:
            output.write(pkg_handler.to_json())
        _logger.info("Data collected")


if __name__ == "__main__":
    DeviceInfo().main()
