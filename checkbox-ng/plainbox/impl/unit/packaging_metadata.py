# This file is part of Checkbox.
#
# Copyright 2012-2016 Canonical Ltd.
# Written by:
#   Zygmunt Krynicki <zygmunt.krynicki@canonical.com>
#   Maciej Kisielewski <maciej.kisielewski@canonical.com>
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
Packaging Meta-Data Unit.

This module contains the implementation of the packaging meta-data unit.  This
unit can be used to describe a dependency in system packaging.  This can be
used to associate jobs with system-level dependencies so that those
dependencies can be automatically added to the appropriate system packaging
meta-data.

For example, consider this unit::

    plugin: shell
    id: virtualization/xen_ok
    requires: package.name == 'libvirt-bin'
    user: root
    estimated_duration: 1.0
    command: virsh -c xen:/// domstate Domain-0
    _description:
     Test to verify that the Xen Hypervisor is running.
    _summary:
     Verify Xen is running

This unit, depends on the ``virsh`` executable. This has to be ensured during
packaging or the test won't be able to execute correctly. To avoid having to
carefully track this at packaging time (where one may have to review many jobs)
it's better to express this inside the provider, as a unit.

A packaging meta-data unit that does exactly this, looks like this::

    unit: packaging meta-data
    os-id: debian
    os-version: 8
    Depends: libvirt-bin

    unit: packaging meta-data
    os-id: fedora
    os-version: 21
    Requires: libvirt-client

Having this additional data, one can generate runtime dependencies for a given
unit using management commands::

    ./manage.py packaging

This command uses the operating-system-specific driver to introspect the system
and see if each of the packaging meta-data unit is applicable.  There are
several strategies, they are tried in order, they are:

    - id and version match
    - id match
    - id_like match

The base Linux distribution driver parses the ``/etc/os-release`` file, looks
at the ``ID``, ``ID_VERSION`` and optionally the ``ID_LIKE`` fields.  They are
used as a standard way to determine the distribution for which packaging
meta-data is being collected for.

The *id and version match* strategy requires that both the ``os-id`` and
``os-dependencies`` fields are present and that they match the ``ID`` and
``ID_VERSION`` values. This strategy allows the test maintainer to express each
dependency accurately for each operating system they wish to support.

The *id match* strategy is only used when the ``os-version`` is not defined.
It is useful when a single definition is applicable to many subsequent
releases.  This is especially useful when job works well with sufficiently old
version of a third party dependency and there is no need to repeatedly re-state
the same dependency for each later release of the operating system.

The *id_like match* strategy is only used as a last resort and can be seen as a
weaker *id match* strategy. This  time the ``os-id`` field is compared to the
``ID_LIKE`` field (if present). It is useful for working with Debian
derivatives, like Ubuntu.

Each matching packaging meta-data unit is then passed to the driver to generate
packaging meta-data. The driver suitable for Debian-like systems, uses the
following three fields from the unit ``Depends``, ``Suggests``, ``Recommends``.
They can be accessed in packaging directly using the ``${plainbox:Depends}``,
``${plainbox:Suggests}`` and ``${plainbox:Recommends}`` syntax that is similar
to ``${misc:Depends}``.

To use it for packaging, place the following rule in your ``debian/rules``
file::

    override_dh_gencontrol:
        python3 manage.py packaging
        dh_gencontrol

And add the following header to one of the binary packages that contains the
actual provider::

    X-Plainbox-Provider: yes

A driver suitable for Fedora might be developed later so at this time it is
not documented.
"""
import abc
import errno
import logging
from packaging import version
import operator
import re
import shlex
import sys

from plainbox.i18n import gettext as _
from plainbox.impl.symbol import SymbolDef
from plainbox.impl.unit import concrete_validators
from plainbox.impl.unit.validators import UniqueValueValidator
from plainbox.impl.unit.unit import Unit

_logger = logging.getLogger("plainbox.unit.packaging")


__all__ = ('PackagingMetaDataUnit', 'get_packaging_driver', 'get_os_release')


class PackagingMetaDataUnit(Unit):

    """
    Unit representing a dependency between some unit and system packaging.

    This unit can be used to describe a dependency in system packaging.  This
    can be used to associate jobs with system-level dependencies so that those
    dependencies can be automatically added to the appropriate system packaging
    meta-data.
    """

    @property
    def os_id(self):
        """Identifier of the operating system."""
        return self.get_record_value(self.Meta.fields.os_id)

    @property
    def os_version_id(self):
        """Version of the operating system."""
        return self.get_record_value(self.Meta.fields.os_version_id)

    @property
    def Depends(self):
        """Package dependencies"""
        return self.get_record_value(self.Meta.fields.Depends)

    @property
    def Recommends(self):
        """Package recommendations"""
        return self.get_record_value(self.Meta.fields.Recommends)

    @property
    def Suggests(self):
        """Package suggestions"""
        return self.get_record_value(self.Meta.fields.Suggests)


    class Meta:

        name = 'packaging meta-data'

        class fields(SymbolDef):

            """Symbols for each field of a packaging meta-data unit."""

            os_id = 'os-id'
            os_version_id = 'os-version-id'
            Depends = 'Depends'
            Recommends = 'Recommends'
            Suggests = 'Suggests'

        field_validators = {
            fields.os_id: [
                concrete_validators.untranslatable,
                concrete_validators.present,
            ],
            fields.os_version_id: [
                concrete_validators.untranslatable,
            ],
            fields.Depends: [
                UniqueValueValidator(),
            ],
            fields.Recommends: [
                UniqueValueValidator(),
            ],
            fields.Suggests: [
                UniqueValueValidator(),
            ],
        }

    def __str__(self):
        parts = [_("Operating System: {}").format(self.os_id)]
        if self.os_id == 'debian' or self.os_id == 'ubuntu':
            if self.Depends:
                parts.append(_("Depends: {}").format(self.Depends))
            if self.Recommends:
                parts.append(_("Recommends: {}").format(self.Recommends))
            if self.Suggests:
                parts.append(_("Suggests: {}").format(self.Suggests))
        else:
            parts.append("...")
        return ', '.join(parts)


class PackagingDriverError(Exception):

    """Base for all packaging driver exceptions."""


class NoPackagingDetected(PackagingDriverError):

    """Exception raised when packaging cannot be found."""


class NoApplicableBinaryPackages(PackagingDriverError):

    """Exception raised when no applicable binary packages are found."""


class IPackagingDriver(metaclass=abc.ABCMeta):

    """Interface for all packaging drivers."""

    @abc.abstractmethod
    def __init__(self, os_release: 'Dict[str, str]'):
        """
        Initialize the packaging driver.

        :param os_release:
            The dictionary that represents the contents of the
            ``/etc/os-release`` file. Using this file the packaging driver can
            infer information about the target operating system that the
            packaging will be built for.

            This assumes that packages are built natively, not through a
            cross-compiler of some sort where the target distribution is
            different from the host distribution.
        """

    @abc.abstractmethod
    def inspect_provider(self, provider: 'Provider1') -> None:
        """
        Inspect a provider looking for packaging meta-data.

        :param provider:
            A provider object to look at. All of the packaging meta-data units
            there are inspected, if they are applicable (see
            :meth:`is_applicable()`. Information from applicable units is
            collected using the :meth:`collect()` method.
        """

    @abc.abstractmethod
    def is_applicable(self, unit: Unit) -> bool:
        """
        Check if the given unit is applicable for collecting.

        :param unit:
            The unit to inspect. This doesn't have to be a packaging meta-data
            unit. In fact, all units are checked with this method.
        :returns:
            True if the unit is applicable for collection.

        Packaging meta-data units that have certain properties are applicable.
        Refer to the documentation of the module for details.
        """

    @abc.abstractmethod
    def collect(self, unit: Unit) -> None:
        """
        Collect information from the given applicable unit.

        :param unit:
            The unit to collect information from. This is usually expressed as
            additional fields that are specific to the type of native packaging
            for the system.

        Collected information is recorded and made available for the
        :meth:`modify_packaging_tree()` method later.
        """

    @abc.abstractmethod
    def inspect_packaging(self) -> None:
        """
        Inspect the packaging tree for additional information.

        :raises NoPackagingDetected:
            Exception raised when packaging cannot be found.
        :raises NoApplicableBinaryPackages:
            Exception raised when no applicable binary packages are found.

        This method looks at the packaging system located in the current
        directory. This can be the ``debian/`` directory, a particular
        ``.spec`` file or anything else. Information obtained from the package
        is used to infer additional properties that can aid in the packaging
        process.
        """

    @abc.abstractmethod
    def modify_packaging_tree(self) -> None:
        """
        Modify the packaging tree with information from the packaging units.

        This method uses all of the available information collected from
        particular packaging meta-data units and from the native packaging to
        modify the packaging. Additional dependencies may be injected in
        appropriate places. Please refer to the documentation specific to your
        packaging system for details.
        """


class PackagingDriverBase(IPackagingDriver):

    """Base implementation of a packaging driver."""

    def __init__(self, os_release: 'Dict[str, str]'):
        self.os_release = os_release

    def is_applicable(self, unit: Unit) -> bool:
        if unit.Meta.name != PackagingMetaDataUnit.Meta.name:
            return False

        # Check each strategy and log accordingly
        if self._is_id_version_match(unit):
            _logger.debug(_("Strategy successful: ID and Version ID match"))
            return True
        if self._is_id_match(unit):
            _logger.debug(_("Strategy successful: ID match, no Version ID required"))
            return True
        if self._is_id_like_match(unit):
            _logger.debug(_("Strategy successful: ID_LIKE match, no Version ID required"))
            return True

        _logger.debug(_("All strategies unsuccessful"))
        return False

    def inspect_provider(self, provider: 'Provider1') -> None:
        for unit in provider.unit_list:
            if self.is_applicable(unit):
                self.collect(unit)

    def _is_id_version_match(self, unit):
        if not unit.os_version_id:
            return False
        return (
            'ID' in self.os_release and
            unit.os_id == self.os_release['ID'] and
            'VERSION_ID' in self.os_release and
            self._compare_versions(unit.os_version_id, self.os_release['VERSION_ID'])
        )

    def _is_id_match(self, unit):
        return (
            'ID' in self.os_release and
            unit.os_id == self.os_release['ID'] and
            unit.os_version_id is None
        )

    def _is_id_like_match(self, unit):
        return (
            'ID_LIKE' in self.os_release and
            unit.os_id == self.os_release['ID_LIKE'] and
            unit.os_version_id is None
        )

    @staticmethod
    def _compare_versions(comparison_str, system_version):
        # Extract the operator and the version from the comparison string
        # Make the operator optional and default to '=='
        match = re.match(
            r"^\s*(==|>=|<=|>|<|!=)?\s*([\d\.a-zA-Z]+)\s*$", comparison_str
        )

        if not match:
            raise SystemExit(
                "Invalid version comparison string: {}".format(comparison_str)
            )
        operator_match, version_match = match.groups()

        # Default to '==' if no operator is provided
        operators = {
            None: operator.eq,
            '==': operator.eq,
            '>=': operator.ge,
            '<=': operator.le,
            '>': operator.gt,
            '<': operator.lt,
            '!=': operator.ne
        }

        system_ver = version.parse(system_version)
        target_ver = version.parse(version_match)

        return operators[operator_match](system_ver, target_ver)


class NullPackagingDriver(PackagingDriverBase):

    """
    Null implementation of a packaging driver.

    This driver just does nothing at all. It is used as a fall-back when
    nothing better is detected.
    """

    def is_applicable(self, unit: Unit) -> bool:
        return False

    def collect(self, unit: Unit) -> None:
        pass

    def inspect_packaging(self) -> None:
        pass

    def modify_packaging_tree(self) -> None:
        pass


NULL_DRIVER = NullPackagingDriver({})


class DebianPackagingDriver(PackagingDriverBase):

    """
    Debian implementation of a packaging driver.

    This packaging driver looks for binary packages (as listed by
    ``debian/control``) that contain the header ``X-Plainbox-Provider: yes``.
    Each such package will have additional substitution variables in the form
    of ``${plainbox:Depends}``, ``${plainbox:Suggests}`` and
    ``${plainbox:Recommends}``. The variables are filled with data from all the
    packaging meta-data units present in the provider.
    """

    def __init__(self, os_release: 'Dict[str, str]'):
        super().__init__(os_release)
        self._depends = []
        self._suggests = []
        self._recommends = []
        self._pkg_list = []

    def inspect_packaging(self) -> None:
        self._pkg_list.extend(self._gen_provider_packages())
        if self._pkg_list:
            return
        raise NoApplicableBinaryPackages(_(
            "There are no applicable binary packages.\n"
            "Add 'X-Plainbox-Provider: yes' to each binary package that "
            "contains a provider"))

    def modify_packaging_tree(self) -> None:
        for pkg in self._pkg_list:
            self._write_pkg_substvars(pkg)

    def collect(self, unit: Unit) -> None:
        def rel_list(field):
            relations = unit.get_record_value(field, '').replace('\n', ' ')
            return (
                rel.strip()
                for rel in re.split(', *', relations)
                if rel.strip()
            )
        self._depends.extend(rel_list('Depends'))
        self._suggests.extend(rel_list('Suggests'))
        self._recommends.extend(rel_list('Recommends'))

    def _write_pkg_substvars(self, pkg):
        fname = 'debian/{}.substvars'.format(pkg)
        _logger.info(_("Writing %s"), fname)
        # NOTE: we're appending to that file
        with open(fname, 'at', encoding='UTF-8') as stream:
            if self._depends:
                print('plainbox:Depends={}'.format(
                    ', '.join(self._depends)), file=stream)
            if self._suggests:
                print('plainbox:Suggests={}'.format(
                    ', '.join(self._suggests)), file=stream)
            if self._recommends:
                print('plainbox:Recommends={}'.format(
                    ', '.join(self._recommends)), file=stream)

    def _gen_provider_packages(self):
        try:
            _logger.info(_("Loading debian/control"))
            with open('debian/control', 'rt', encoding='UTF-8') as stream:
                from debian.deb822 import Deb822
                for para in Deb822.iter_paragraphs(stream.readlines()):
                    if 'Package' not in para:
                        continue
                    if para.get('X-Plainbox-Provider') != 'yes':
                        continue
                    pkg = para['Package']
                    _logger.info(_("Found binary provider package: %s"), pkg)
                    yield pkg
        except OSError as exc:
            if exc.errno == errno.ENOENT:
                raise NoPackagingDetected(_(
                    "There is no appropriate packaging in this directory.\n"
                    "The file debian/control could not be found"))


def get_packaging_driver() -> IPackagingDriver:
    """Get the packaging driver appropriate for the current platform."""
    if sys.platform.startswith("linux"):
        os_release = get_os_release()
        if (os_release.get('ID') == 'debian' or
                os_release.get('ID_LIKE') == 'debian'):
            _logger.info(_("Using Debian packaging driver"))
            return DebianPackagingDriver(os_release)
    _logger.info(_("Using null packaging driver"))
    return NULL_DRIVER


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
