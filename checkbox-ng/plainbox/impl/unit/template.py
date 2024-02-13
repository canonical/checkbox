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
:mod:`plainbox.impl.template` -- template unit
==============================================
"""
import itertools
import logging
import string

from plainbox.i18n import gettext as _
from plainbox.i18n import gettext_noop as N_
from plainbox.impl.decorators import instance_method_lru_cache
from plainbox.impl.resource import ExpressionFailedError
from plainbox.impl.resource import Resource
from plainbox.impl.resource import ResourceProgram
from plainbox.impl.resource import parse_imports_stmt
from plainbox.impl.secure.origin import Origin
from plainbox.impl.symbol import SymbolDef
from plainbox.impl.unit import all_units
from plainbox.impl.unit import concrete_validators
from plainbox.impl.unit import get_accessed_parameters
from plainbox.impl.unit.unit_with_id import UnitWithId
from plainbox.impl.unit.unit_with_id import UnitWithIdValidator
from plainbox.impl.unit.validators import CorrectFieldValueValidator
from plainbox.impl.unit.validators import PresentFieldValidator
from plainbox.impl.unit.validators import ReferenceConstraint
from plainbox.impl.unit.validators import UnitReferenceValidator
from plainbox.impl.unit.validators import UniqueValueValidator
from plainbox.impl.validation import Problem
from plainbox.impl.validation import Severity


__all__ = ['TemplateUnit']


logger = logging.getLogger("plainbox.unit.template")


class TemplateUnitValidator(UnitWithIdValidator):

    """Validator for template unit."""

    def check(self, unit):
        for issue in super().check(unit):
            yield issue
        # Apart from all the per-field checks, ensure that the unit,
        # if instantiated with fake resource, produces a valid target unit
        accessed_parameters = unit.get_accessed_parameters(
            force=True, template_engine=unit.template_engine)
        resource = Resource({
            key: key.upper()
            for key in set(itertools.chain(*accessed_parameters.values()))
        })
        try:
            new_unit = unit.instantiate_one(resource)
        except Exception as exc:
            self.error(unit, unit.Meta.fields.template_unit, Problem.wrong,
                       _("unable to instantiate template: {}").format(exc))
        else:
            # TODO: we may need some origin translation to correlate issues
            # back to the template.
            for issue in new_unit.check():
                self.issue_list.append(issue)
                yield issue

    def explain(self, unit, field, kind, message):
        """
        Lookup an explanatory string for a given issue kind

        :returns:
            A string (explanation) or None if the issue kind
            is not known to this method.

        This version overrides the base implementation to use the unit
        template_id, if it is available, when reporting issues.
        """
        if unit.template_partial_id is None:
            return super().explain(unit, field, kind, message)
        stock_msg = self._explain_map.get(kind)
        if stock_msg is None:
            return None
        return _("{unit} {id!a}, field {field!a}, {message}").format(
            unit=unit.tr_unit(), id=unit.template_partial_id, field=str(field),
            message=message or stock_msg)


class TemplateUnit(UnitWithId):

    """
    Template that can instantiate zero or more additional units.

    Templates are a generalized replacement to the ``local job`` system from
    Checkbox.  Instead of running a job definition that prints additional job
    definitions, a static template is provided. PlainBox has all the visibility
    of each of the fields in the template and can perform validation and other
    analysis without having to run any external commands.

    To instantiate a template a resource object must be provided. This adds a
    natural dependency from each template unit to a resource job definition
    unit. Actual instantiation allows PlainBox to create additional unit
    instance for each resource eligible record. Eligible records are either all
    records or a subset of records that cause the filter program to evaluate to
    True. The filter program uses the familiar resource program syntax
    available to normal job definitions.

    :attr _filter_program:
        Cached ResourceProgram computed (once) and returned by
        :meth:`get_filter_program()`
    """

    def __init__(self, data, origin=None, provider=None, raw_data=None,
                 parameters=None, field_offset_map=None):
        """
        Initialize a new TemplateUnit instance.

        :param data:
            Normalized data that makes up this job template
        :param origin:
            An (optional) Origin object. If omitted a fake origin object is
            created. Normally the origin object should be obtained from the
            RFC822Record object.
        :param provider:
            An (optional) Provider1 object. If omitted it defaults to None but
            the actual job template is not suitable for execution. All job
            templates are expected to have a provider.
        :param controller:
            An (optional) session state controller. If omitted a checkbox
            session state controller is implicitly used. The controller defines
            how this job influences the session it executes in.
        :param raw_data:
            An (optional) raw version of data, without whitespace
            normalization. If omitted then raw_data is assumed to be data.
        :param parameters:
            An (optional) dictionary of parameters. Parameters allow for unit
            properties to be altered while maintaining a single definition.
            This is required to obtain translated summary and description
            fields, while having a single translated base text and any
            variation in the available parameters.

        .. note::
            You should almost always use :meth:`from_rfc822_record()` instead.
        """
        if origin is None:
            origin = Origin.get_caller_origin()
        super().__init__(
            data, raw_data, origin, provider, parameters, field_offset_map)
        self._filter_program = None
        self._fake_resources = False

    @classmethod
    def instantiate_template(cls, data, raw_data, origin, provider, parameters,
                             field_offset_map):
        """
        Instantiate this unit from a template.

        The point of this method is to have a fixed API, regardless of what the
        API of a particular unit class ``__init__`` method actually looks like.

        It is easier to standardize on a new method that to patch all of the
        initializers, code using them and tests to have an uniform initializer.
        """
        # This assertion is a low-cost trick to ensure that we override this
        # method in all of the subclasses to ensure that the initializer is
        # called with correctly-ordered arguments.
        assert cls is TemplateUnit, \
            "{}.instantiate_template() not customized".format(cls.__name__)
        return cls(data, raw_data, origin, provider, parameters,
                   field_offset_map)

    def __str__(self):
        """String representation of Template unit objects."""
        return "{} <~ {}".format(self.id, self.resource_id)

    @property
    def unit(self):
        """
        The value of the unit field (overridden)

        The return value is always "template"
        """
        return "template"

    @property
    def resource_partial_id(self):
        """name of the referenced resource object."""
        text = self.template_resource
        if text is not None and "::" in text:
            return text.split("::", 1)[1]
        return text

    @property
    def resource_namespace(self):
        """namespace of the referenced resource object."""
        text = self.template_resource
        if text is not None and "::" in text:
            return text.split("::", 1)[0]
        elif self._provider is not None:
            return self._provider.namespace

    @property
    def resource_id(self):
        """fully qualified identifier of the resource object."""
        resource_partial_id = self.resource_partial_id
        if resource_partial_id is None:
            return None
        imports = self.get_imported_jobs()
        assert imports is not None
        for imported_resource_id, imported_alias in imports:
            if imported_alias == resource_partial_id:
                return imported_resource_id
        resource_namespace = self.resource_namespace
        if resource_namespace is None:
            return resource_partial_id
        else:
            return "{}::{}".format(resource_namespace, resource_partial_id)

    @classmethod
    def slugify_template_id(cls, _string=None):
        """
        Remove unwanted characters from a raw job id string.

        This helps exposing cleaner looking template ids when the id is
        generated from the id field by removing characters like '{', '}',
        and ' '.
        """
        if _string:
            valid_chars = frozenset(
                "-_.:/\\{}{}".format(string.ascii_letters, string.digits)
            )
            return "".join(c if c in valid_chars else "" for c in _string)

    @property
    def template_partial_id(self):
        """
        Identifier of this template, without the provider namespace.

        If the ``template-id`` field is not present in the unit definition,
        ``template_partial_id`` is computed from the ``partial_id`` attribute.
        """
        template_partial_id = self.get_record_value("template-id")
        if not template_partial_id:
            template_partial_id = self.slugify_template_id(self.partial_id)
        return template_partial_id

    @property
    def template_id(self):
        """Identifier of this template, with the provider namespace."""
        if self.provider and self.template_partial_id:
            return "{}::{}".format(self.provider.namespace,
                                   self.template_partial_id
                                   )
        else:
            return self.template_partial_id

    @property
    def template_resource(self):
        """value of the 'template-resource' field."""
        return self.get_record_value('template-resource')

    @property
    def template_filter(self):
        """
        value of the 'template-filter' field.

        This attribute stores the text of a resource program (optional) that
        select a subset of available resource objects.  If you wish to access
        the actual resource program call :meth:`get_filter_program()`. In both
        cases the value can be None.
        """
        return self.get_record_value('template-filter')

    @property
    def template_imports(self):
        """
        value of the 'template-imports' field.

        This attribute stores the text of a resource import that is specific
        to the template itself. In other words, it allows the template
        to access resources from any namespace.
        """
        return self.get_record_value('template-imports')

    @property
    def template_summary(self):
        """
        Value of the 'template-summary' field.

        This attribute stores the summary of a template, that is a human
        readable name for that template.
        """
        return self.get_record_value("template-summary")

    @instance_method_lru_cache(maxsize=None)
    def tr_template_summary(self):
        """
        Get the translated version of :meth:`template_summary`.
        """
        return self.get_translated_record_value("template-summary")

    @property
    def template_description(self):
        """
        Value of the 'template-description' field.

        This attribute stores the definition of a template which can be used
        to provide more information about this template.
        """
        return self.get_record_value("template-description")

    @instance_method_lru_cache(maxsize=None)
    def tr_template_description(self):
        """
        Get the translated version of :meth:`template_description`.
        """
        return self.get_translated_record_value("template-description")

    @property
    def template_unit(self):
        """
        value of the 'template-unit' field.

        This attribute stores the type of the unit that this template intends
        to instantiate. It defaults to 'job' for backwards compatibility and
        simplicity.
        """
        return self.get_record_value('template-unit', 'job')

    def get_imported_jobs(self):
        """
        Parse the 'imports' line and compute the imported symbols.

        Return generator for a sequence of pairs (job_id, identifier) that
        describe the imported job identifiers from arbitrary namespace.

        The syntax of each imports line is:

        IMPORT_STMT ::  "from" <NAMESPACE> "import" <PARTIAL_ID>
                      | "from" <NAMESPACE> "import" <PARTIAL_ID>
                         AS <IDENTIFIER>
        """
        imports = self.template_imports or ""
        return parse_imports_stmt(imports)

    def get_filter_program(self):
        """
        Get filter program compiled from the template-filter field.

        :returns:
            ResourceProgram created out of the text of the template-filter
            field.
        """
        if self.template_filter is not None and self._filter_program is None:
            self._filter_program = ResourceProgram(
                self.template_filter, self.resource_namespace,
                self.get_imported_jobs())
        return self._filter_program

    def get_target_unit_cls(self):
        """
        Get the Unit subclass that implements the instantiated unit.

        :returns:
            A subclass of Unit the template will try to instantiate. If there
            is no ``template-unit`` field in the template then a ``job``
            template is assumed.
        :raises KeyError:
            if the field 'template-unit' refers to unknown unit or is undefined

        .. note::
            Typically this will return a JobDefinition class but it's not the
            only possible value.
        """
        all_units.load()
        return all_units.get_by_name(self.template_unit).plugin_object

    def instantiate_all(self, resource_list, fake_resources=False):
        """
        Instantiate a list of job definitions.

        By creating one from each non-filtered out resource records.

        :param resource_list:
            A list of resource objects with the correct name
            (:meth:`template_resource`)
        :param fake_resources:
            An optional parameter to trigger test plan export execution mode
        :returns:
            A list of new Unit (or subclass) objects.
        """
        unit_cls = self.get_target_unit_cls()
        resources = []
        index = 0
        self._fake_resources = fake_resources
        for resource in resource_list:
            if self.should_instantiate(resource):
                index += 1
                resources.append(self.instantiate_one(resource,
                                                      unit_cls_hint=unit_cls,
                                                      index=index))
        return resources

    def instantiate_one(self, resource, unit_cls_hint=None, index=0):
        """
        Instantiate a single job out of a resource and this template.

        :param resource:
            A Resource object to provide template data
        :param unit_cls_hint:
            A unit class to instantiate
        :param index:
            An integer parameter representing the current loop index
        :returns:
            A new JobDefinition created out of the template and resource data.
        :raises AttributeError:
            If the template referenced a value not defined by the resource
            object.

        Fields starting with the string 'template-' are discarded. All other
        fields are interpolated by attributes from the resource object.
        References to missing resource attributes cause the process to fail.
        """
        # Look up the unit we're instantiating
        if unit_cls_hint is not None:
            unit_cls = unit_cls_hint
        else:
            unit_cls = self.get_target_unit_cls()
        assert unit_cls is not None
        # Filter out template- data fields as they are not relevant to the
        # target unit.
        data = {
            key: value for key, value in self._data.items()
            if not key.startswith('template-')
        }
        raw_data = {
            key: value for key, value in self._raw_data.items()
            if not key.startswith('template-')
        }
        # Only keep the template-engine field
        raw_data['template-engine'] = self.template_engine
        data['template-engine'] = raw_data['template-engine']
        # Override the value of the 'unit' field from 'template-unit' field
        data['unit'] = raw_data['unit'] = self.template_unit
        # XXX: extract raw dictionary from the resource object, there is no
        # normal API for that due to the way resource objects work.
        parameters = dict(object.__getattribute__(resource, '_data'))
        accessed_parameters = set(itertools.chain(*{get_accessed_parameters(
            value, template_engine=self.template_engine)
            for value in data.values()}))
        # Recreate the parameters with only the subset that will actually be
        # used by the template. Doing this filter can prevent exceptions like
        # DependencyDuplicateError where an unused resource property can differ
        # when resuming and bootstrapping sessions, causing job checksums
        # mismatches.
        # See https://bugs.launchpad.net/bugs/1561821
        parameters = {
            k: v for k, v in parameters.items() if k in accessed_parameters}
        if self._fake_resources:
            parameters = {k: k.upper() for k in accessed_parameters}
            for k in parameters:
                if k.endswith('_slug'):
                    parameters[k] = k.replace('_slug', '').upper()
            if 'index' in parameters:
                parameters['index'] = index
        # Add the special __index__ to the resource namespace variables
        parameters['__index__'] = index
        # Instantiate the class using the instantiation API
        return unit_cls.instantiate_template(
            data, raw_data, self.origin, self.provider, parameters,
            self.field_offset_map)

    def should_instantiate(self, resource):
        """
        Check if a job should be instantiated for a specific resource.

        :param resource:
            A Resource object to check
        :returns:
            True if a job should be instantiated for the resource object

        Determine if a job instance should be created using the specific
        resource object. This is the case if there is no filter or if the
        specified resource object would make the filter program evaluate to
        True.
        """
        if self._fake_resources:
            return True
        program = self.get_filter_program()
        if program is None:
            return True
        try:
            # NOTE: this is a little tricky. The interface for
            # evaluate_or_raise() is {str: List[Resource]} but we are being
            # called with Resource. The reason for that is that we wish to get
            # per-resource answer not an aggregate 'yes' or 'no'.
            return program.evaluate_or_raise({
                self.resource_id: [resource]
            })
        except ExpressionFailedError:
            return False

    class Meta:

        name = N_('template')

        class fields(SymbolDef):

            """Symbols for each field that a TemplateUnit can have."""

            template_id = "template-id"
            template_summary = "template-summary"
            template_description = "template-description"
            template_unit = 'template-unit'
            template_resource = 'template-resource'
            template_filter = 'template-filter'
            template_imports = 'template-imports'

        validator_cls = TemplateUnitValidator

        field_validators = {
            fields.template_id: [
                concrete_validators.untranslatable,
                concrete_validators.templateVariant,
                UniqueValueValidator(),
                # We want to have bare, namespace-less identifiers
                CorrectFieldValueValidator(
                    lambda value, unit: (
                        "::" not in unit.get_record_value("template-id")),
                    message=_("identifier cannot define a custom namespace"),
                    onlyif=lambda unit: unit.get_record_value("template-id")),
            ],
            fields.template_summary: [
                concrete_validators.translatable,
                PresentFieldValidator(severity=Severity.advice),
                CorrectFieldValueValidator(
                    lambda field: field.count("\n") == 0,
                    Problem.wrong, Severity.warning,
                    message=_("please use only one line"),
                    onlyif=lambda unit: unit.template_summary),
                CorrectFieldValueValidator(
                    lambda field: len(field) <= 80,
                    Problem.wrong, Severity.warning,
                    message=_("please stay under 80 characters"),
                    onlyif=lambda unit: unit.template_summary)
            ],
            fields.template_description: [
                concrete_validators.translatable,
            ],
            fields.template_unit: [
                concrete_validators.untranslatable,
            ],
            fields.template_resource: [
                concrete_validators.untranslatable,
                concrete_validators.present,
                UnitReferenceValidator(
                    lambda unit: (
                        [unit.resource_id] if unit.resource_id else []),
                    constraints=[
                        ReferenceConstraint(
                            lambda referrer, referee: referee.unit == 'job',
                            message=_("the referenced unit is not a job")),
                        ReferenceConstraint(
                            lambda referrer, referee: (
                                referee.plugin == 'resource'),
                            onlyif=lambda referrer, referee: (
                                referee.unit == 'job'),
                            message=_(
                                "the referenced job is not a resource job")),
                    ]),
                # TODO: should not refer to deprecated job,
                #       onlyif job itself is not deprecated
            ],
            fields.template_filter: [
                concrete_validators.untranslatable,
                # All templates need a valid (or empty) template filter
                CorrectFieldValueValidator(
                    lambda value, unit: unit.get_filter_program(),
                    onlyif=lambda unit: unit.template_filter is not None),
                # TODO: must refer to the same job as template-resource
            ],
            fields.template_imports: [
                concrete_validators.untranslatable,
                CorrectFieldValueValidator(
                    lambda value, unit: (
                        list(unit.get_imported_jobs()) is not None)),
                CorrectFieldValueValidator(
                    lambda value, unit: (
                        len(list(unit.get_imported_jobs())) in (0, 1)),
                    message=_("at most one import statement is allowed")),
                # TODO: must refer to known or possibly-known job
                # TODO: should not refer to deprecated jobs,
                #       onlyif job itself is not deprecated
            ],
        }
