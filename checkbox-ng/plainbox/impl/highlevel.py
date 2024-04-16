# This file is part of Checkbox.
#
# Copyright 2013 Canonical Ltd.
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
:mod:`plainbox.impl.highlevel` -- High-level API
================================================
"""

from collections import OrderedDict
import logging

from plainbox.impl.session.storage import WellKnownDirsHelper


logger = logging.getLogger("plainbox.highlevel")


class PlainBoxObject:
    """
    A thin wrapper around some other plainbox object.
    """

    def __init__(self, impl, name=None, group=None, children=None, attrs=None):
        """
        Initialize a new PlainBoxObject with the specified internal
        implementation object and some meta-data.

        :param impl:
            The implementation object (internal API)
        :param name:
            Human-visible name of this object
        :param group:
            Human-visible group (class) this object belongs to
        :param children:
            A list of children that this object has
        :param attrs:
            A list of attributes that this object has
        """
        self._impl = impl
        self._name = name
        if children is None:
            children = []
        self._children = children
        self._group = group
        if attrs is None:
            attrs = {}
        self._attrs = attrs

    def __str__(self):
        """
        String for of this object

        :returns:
            :attr:`name`.
        """
        return self.name

    def __iter__(self):
        """
        Iterate over all of the children
        """
        return iter(self._children)

    @property
    def name(self):
        """
        name of this object

        This may be an abbreviated form that assumes the group is displayed
        before the name. It will probably take a few iterations before we get
        right names (and other, additional properties) for everything.
        """
        return self._name

    @property
    def group(self):
        """
        group this object belongs to.

        This is a way to distinguish high-level "classes" that may not map
        one-to-one to a internal python class.
        """
        return self._group

    @property
    def children(self):
        """
        A list of children that this object has

        This list is mutable and is always guaranteed to exist.
        """
        return self._children

    @property
    def attrs(self):
        """
        A mapping of key-value attributes that this object has

        This mapping is mutable and is always guaranteed to exist.
        """
        return self._attrs


class Explorer:
    """
    Class simplifying discovery of various PlainBox objects.
    """

    OBJECT_TYPES = [
        "category",
        "exporter",
        "job",
        "manifest entry",
        "packaging meta-data",
        "template",
        "test plan",
        "file",
        "provider",
        "storage",
        "service",
        "all-jobs",
    ]

    def __init__(self, provider_list=None):
        """
        Initialize a new Explorer

        :param provider_list:
            List of providers that this explorer will know about.
            Defaults to nothing (BYOP - bring your own providers)
        """
        if provider_list is None:
            provider_list = []
        self.provider_list = provider_list

    def get_object_tree(self):
        """
        Get a tree of :class:`PlainBoxObject` that represents everything that
        PlainBox knows about.

        :returns:
            A :class:`PlainBoxObject` that represents the explorer
            object itself, along with all the children reachable from it.

        This function computes the following set of data::

            the explorer itself
                - all providers
                    - all jobs
                    - all executables
                - all repositories
                    - all storages
        """
        service_obj = PlainBoxObject(
            self, name="service object", group="service"
        )
        # Milk each provider for jobs and test plans
        for provider in self.provider_list:
            provider_obj = PlainBoxObject(
                provider,
                group="provider",
                name=provider.name,
                attrs=OrderedDict(
                    (
                        (
                            "broken_i18n",
                            provider.description == provider.tr_description(),
                        ),
                        ("name", provider.name),
                        ("namespace", provider.namespace),
                        ("version", provider.version),
                        ("description", provider.description),
                        ("tr_description", provider.tr_description()),
                        ("jobs_dir", provider.jobs_dir),
                        ("units_dir", provider.units_dir),
                        ("data_dir", provider.data_dir),
                        ("locale_dir", provider.locale_dir),
                        ("gettext_domain", provider.gettext_domain),
                        ("base_dir", provider.base_dir),
                    )
                ),
            )
            for unit in provider.unit_list:
                provider_obj.children.append(self._unit_to_obj(unit))
            service_obj.children.append(provider_obj)
        for storage in WellKnownDirsHelper.get_storage_list():
            storage_obj = PlainBoxObject(
                storage,
                group="storage",
                name=storage.location,
                attrs=OrderedDict(
                    (
                        ("location", storage.location),
                        ("session_file", storage.session_file),
                    )
                ),
            )
            service_obj.children.append(storage_obj)
        return service_obj

    def _unit_to_obj(self, unit):
        # Yes, this should be moved to member methods
        if unit.Meta.name == "test plan":
            return self._test_plan_to_obj(unit)
        elif unit.Meta.name == "job":
            return self._job_to_obj(unit)
        elif unit.Meta.name == "category":
            return self._category_to_obj(unit)
        elif unit.Meta.name == "file":
            return self._file_to_obj(unit)
        elif unit.Meta.name == "template":
            return self._template_to_obj(unit)
        elif unit.Meta.name == "manifest entry":
            return self._manifest_entry_to_obj(unit)
        elif unit.Meta.name == "packaging meta-data":
            return self._packaging_meta_data_to_obj(unit)
        elif unit.Meta.name == "exporter":
            return self._exporter_entry_to_obj(unit)
        else:
            raise NotImplementedError(unit.Meta.name)

    def _job_to_obj(self, unit):
        return PlainBoxObject(
            unit,
            group=unit.Meta.name,
            name=unit.id,
            attrs=OrderedDict(
                (
                    (
                        "broken_i18n",
                        unit.summary == unit.tr_summary()
                        or unit.description == unit.tr_description(),
                    ),
                    ("id", unit.id),
                    ("partial_id", unit.partial_id),
                    ("summary", unit.summary),
                    ("tr_summary", unit.tr_summary()),
                    ("raw_summary", unit.get_raw_record_value("summary")),
                    ("description", unit.description),
                    (
                        "raw_description",
                        unit.get_raw_record_value("description"),
                    ),
                    ("tr_description", unit.tr_description()),
                    ("plugin", unit.plugin),
                    ("command", unit.command),
                    ("user", unit.user),
                    ("environ", unit.environ),
                    ("estimated_duration", unit.estimated_duration),
                    ("depends", unit.depends),
                    ("requires", unit.requires),
                    ("origin", str(unit.origin)),
                )
            ),
        )

    def _test_plan_to_obj(self, unit):
        return PlainBoxObject(
            unit,
            group=unit.Meta.name,
            name=unit.id,
            attrs=OrderedDict(
                (
                    (
                        "broken_i18n",
                        unit.name == unit.tr_name()
                        or unit.description == unit.tr_description(),
                    ),
                    ("id", unit.id),
                    ("include", unit.include),
                    ("exclude", unit.exclude),
                    ("name", unit.name),
                    ("tr_name", unit.tr_name()),
                    ("description", unit.description),
                    ("tr_description", unit.tr_description()),
                    ("estimated_duration", unit.estimated_duration),
                    ("icon", unit.icon),
                    ("category_overrides", unit.category_overrides),
                    ("virtual", unit.virtual),
                    ("origin", str(unit.origin)),
                )
            ),
        )

    def _category_to_obj(self, unit):
        return PlainBoxObject(
            unit,
            group=unit.Meta.name,
            name=unit.id,
            attrs=OrderedDict(
                (
                    ("broken_i18n", unit.name == unit.tr_name()),
                    ("id", unit.id),
                    ("name", unit.name),
                    ("tr_name", unit.tr_name()),
                    ("origin", str(unit.origin)),
                )
            ),
        )

    def _file_to_obj(self, unit):
        return PlainBoxObject(
            unit,
            group=unit.Meta.name,
            name=unit.path,
            attrs=OrderedDict(
                (
                    ("path", unit.path),
                    ("role", str(unit.role)),
                    ("origin", str(unit.origin)),
                )
            ),
        )

    def _template_to_obj(self, unit):
        return PlainBoxObject(
            unit,
            group=unit.Meta.name,
            name=unit.template_id,
            attrs=OrderedDict(
                (
                    ("id", unit.id),
                    ("partial_id", unit.partial_id),
                    ("template_id", unit.template_id),
                    ("template_unit", unit.template_unit),
                    ("template_resource", unit.template_resource),
                    ("template_filter", unit.template_filter),
                    ("template_imports", unit.template_imports),
                    ("origin", str(unit.origin)),
                )
            ),
        )

    def _manifest_entry_to_obj(self, unit):
        return PlainBoxObject(
            unit,
            group=unit.Meta.name,
            name=unit.id,
            attrs=OrderedDict(
                (
                    ("id", unit.id),
                    ("name", unit.name),
                    ("tr_name", unit.tr_name()),
                    ("value_type", unit.value_type),
                    ("value_unit", unit.value_unit),
                    ("resource_key", unit.resource_key),
                    ("origin", str(unit.origin)),
                )
            ),
        )

    def _packaging_meta_data_to_obj(self, unit):
        return PlainBoxObject(
            unit,
            group=unit.Meta.name,
            name=unit.os_id,
            attrs=OrderedDict(
                (
                    ("os_id", unit.os_id),
                    ("os_version_id", unit.os_version_id),
                    ("origin", str(unit.origin)),
                )
            ),
        )

    def _exporter_entry_to_obj(self, unit):
        return PlainBoxObject(
            unit,
            group=unit.Meta.name,
            name=unit.id,
            attrs=OrderedDict(
                (
                    ("id", unit.id),
                    ("summary", unit.summary),
                    ("tr_summary", unit.tr_summary()),
                )
            ),
        )
