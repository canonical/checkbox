# This file is part of Checkbox.
#
# Copyright 2012-2014 Canonical Ltd.
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
:mod:`plainbox.impl.unit.unit` -- unit definition
=================================================
"""

import abc
import collections
import hashlib
import json
import logging
import string

from plainbox.i18n import gettext as _
from plainbox.impl.secure.origin import Origin
from plainbox.impl.secure.rfc822 import normalize_rfc822_value
from plainbox.impl.symbol import Symbol
from plainbox.impl.symbol import SymbolDef
from plainbox.impl.symbol import SymbolDefMeta
from plainbox.impl.symbol import SymbolDefNs
from plainbox.impl.unit import get_accessed_parameters
from plainbox.impl.unit._legacy import UnitLegacyAPI
from plainbox.impl.unit.validators import IFieldValidator
from plainbox.impl.unit.validators import MultiUnitFieldIssue
from plainbox.impl.unit.validators import PresentFieldValidator
from plainbox.impl.unit.validators import TemplateInvariantFieldValidator
from plainbox.impl.unit.validators import UnitFieldIssue
from plainbox.impl.unit.validators import UntranslatableFieldValidator
from plainbox.impl.validation import Problem
from plainbox.impl.validation import Severity

__all__ = ['Unit', 'UnitValidator']


logger = logging.getLogger("plainbox.unit")


class UnitValidator:
    """
    Validator class for basic :class:`Unit` type

    Typically validators are not used directly. Instead, please call
    :meth:`Unit.check()` and iterate over the returned issues.

    :attr issue_list:
        A list of :class`plainbox.impl.validate.Issue`
    """

    def __init__(self):
        """
        Initialize a new validator
        """
        self.issue_list = []

    def check(self, unit):
        """
        Check a specific unit for correctness

        :param unit:
            The :class:`Unit` to check
        :returns:
            A generator yielding subsequent issues
        """
        for field_validator, field in self.make_field_validators(unit):
            for issue in field_validator.check(self, unit, field):
                yield issue

    def check_in_context(self, unit, context):
        """
        Check a specific unit for correctness in a broader context

        :param unit:
            The :class:`Unit` to check
        :param context:
            A :class:`UnitValidationContext` to use as context
        :returns:
            A generator yielding subsequent issues
        """
        for field_validator, field in self.make_field_validators(unit):
            for issue in field_validator.check_in_context(
                    self, unit, field, context):
                yield issue

    def make_field_validators(self, unit):
        """
        Convert unit meta-data to a sequence of validators

        :returns:
            A generator for pairs (field_validator, field) where
            field_validator is an instance of :class:`IFieldValidator` and
            field is a symbol with the field name.
        """
        for field, spec in sorted(unit.Meta.field_validators.items()):
            if isinstance(spec, type):
                validator_list = [spec]
            elif isinstance(spec, list):
                validator_list = spec
            else:
                raise TypeError(_(
                    "{}.Meta.fields[{!r}] is not a validator"
                ).format(unit.__class__.__name__, field))
            for index, spec in enumerate(validator_list):
                # If it's a validator class, instantiate it
                if isinstance(spec, type) \
                        and issubclass(spec, IFieldValidator):
                    yield spec(), field
                # If it's a validator instance, just return it
                elif isinstance(spec, IFieldValidator):
                    yield spec, field
                else:
                    raise TypeError(_(
                        "{}.Meta.fields[{!r}][{}] is not a validator"
                    ).format(unit.__class__.__name__, field, index))

    def advice(self, unit, field, kind, message=None, *, offset=0,
               origin=None):
        """
        Shortcut for :meth:`report_issue` with severity=Severity.advice
        """
        return self.report_issue(
            unit, field, kind, Severity.advice, message,
            offset=offset, origin=origin)

    def warning(self, unit, field, kind, message=None, *, offset=0,
                origin=None):
        """
        Shortcut for :meth:`report_issue` with severity=Severity.warning
        """
        return self.report_issue(
            unit, field, kind, Severity.warning, message,
            offset=offset, origin=origin)

    def error(self, unit, field, kind, message=None, *, offset=0, origin=None):
        """
        Shortcut for :meth:`report_issue` with severity=Severity.error
        """
        return self.report_issue(
            unit, field, kind, Severity.error, message,
            offset=offset, origin=origin)

    def report_issue(self, unit, field, kind, severity, message=None,
                     *, offset=0, origin=None):
        """
        Helper method that aids in adding issues

        :param unit:
            A :class:`Unit` that the issue refers to or a list of such objects
        :param field:
            Name of the field the issue is specific to
        :param kind:
            Type of the issue, this can be an arbitrary
            symbol. If it is not known to the :meth:`explain()`
            then a message must be provided or a ValueError
            will be raised.
        :param severity:
            A symbol that represents the severity of the issue.
            See :class:`plainbox.impl.validation.Severity`.
        :param message:
            An (optional) message to use instead of a stock message.
            This argument is required if :meth:`explain()` doesn't know
            about the specific value of ``kind`` used
        :param offset:
            An (optional, keyword-only) offset within the field itself.
            If specified it is used to point to a specific line in a multi-line
            field.
        :param origin:
            An (optional, keyword-only) origin to use to report the issue.
            If specified it totally overrides all implicit origin detection.
            The ``offset`` is not applied in this case.
        :returns:
            The reported issue
        :raises ValueError:
            if ``kind`` is not known to :meth:`explain()` and
            ``message`` is None.
        """
        # compute the actual message
        message = self.explain(
            unit[0] if isinstance(unit, list) else unit, field, kind, message)
        if message is None:
            raise ValueError(
                _("unable to deduce message and no message provided"))
        # compute the origin
        if isinstance(unit, list):
            cls = MultiUnitFieldIssue
            if origin is None:
                origin = unit[0].origin
                if field in unit[0].field_offset_map:
                    origin = origin.with_offset(
                        unit[0].field_offset_map[field] + offset
                    ).just_line()
                elif '_{}'.format(field) in unit[0].field_offset_map:
                    if origin is None:
                        origin = origin.with_offset(
                            unit[0].field_offset_map['_{}'.format(field)]
                            + offset).just_line()
        else:
            cls = UnitFieldIssue
            if origin is None:
                origin = unit.origin
                if field in unit.field_offset_map:
                    origin = origin.with_offset(
                        unit.field_offset_map[field] + offset
                    ).just_line()
                elif '_{}'.format(field) in unit.field_offset_map:
                    if origin is None:
                        origin = origin.with_offset(
                            unit.field_offset_map['_{}'.format(field)]
                            + offset).just_line()
        issue = cls(message, severity, kind, origin, unit, field)
        self.issue_list.append(issue)
        return issue

    def explain(self, unit, field, kind, message):
        """
        Lookup an explanatory string for a given issue kind

        :returns:
            A string (explanation) or None if the issue kind
            is not known to this method.
        """
        stock_msg = self._explain_map.get(kind)
        if message or stock_msg:
            return _("field {field!a}, {message}").format(
                field=str(field), message=message or stock_msg)

    _explain_map = {
        Problem.missing: _("required field missing"),
        Problem.wrong: _("incorrect value supplied"),
        Problem.useless: _("definition useless in this context"),
        Problem.deprecated: _("deprecated field used"),
        Problem.constant: _("value must be variant (parametrized)"),
        Problem.variable: _("value must be invariant (unparametrized)"),
        Problem.unknown_param: _("field refers to unknown parameter"),
        Problem.not_unique: _("field value is not unique"),
        Problem.expected_i18n: _("field should be marked as translatable"),
        Problem.unexpected_i18n: (
            _("field should not be marked as translatable")),
        Problem.syntax_error: _("syntax error inside the field"),
        Problem.bad_reference: _("bad reference to another unit"),
    }


class UnitType(abc.ABCMeta):
    """
    Meta-class for all Units

    This metaclass is responsible for collecting meta-data about particular
    units and exposing them in the special 'Meta' attribute of each class.

    It also handles Meta inheritance so that SubUnit.Meta inherits from
    Unit.Meta even if it was not specified directly.
    """

    def __new__(mcls, name, bases, ns):
        # mro = super().__new__(mcls, name, bases, ns).__mro__
        base_meta_list = [
            base.Meta for base in bases if hasattr(base, 'Meta')]
        our_meta = ns.get('Meta')
        if our_meta is not None and base_meta_list:
            new_meta_ns = dict(our_meta.__dict__)
            new_meta_ns['__doc__'] = """
                Collection of meta-data about :class:`{}`

                This class is partially automatically generated.
                It always inherits the Meta class of the base unit type.

                This class has (at most) three attributes:

                    `field_validators`:
                        A dictionary mapping from each field to a list of
                        :class:`IFieldvalidator:` that check that particular
                        field for correctness.

                    `fields`:
                        A :class`SymbolDef` with a symbol for each field that
                        this unit defines. This does not include dynamically
                        created fields that are not a part of the unit itself.

                    `validator_cls`:
                        A :class:`UnitValidator` subclass that can be used to
                        check this unit for correctness
            """.format(name)
            new_meta_bases = tuple(base_meta_list)
            # Merge custom field_validators with base unit validators
            if 'field_validators' in our_meta.__dict__:
                merged_validators = dict()
                for base_meta in base_meta_list:
                    if hasattr(base_meta, 'field_validators'):
                        merged_validators.update(base_meta.field_validators)
                merged_validators.update(our_meta.field_validators)
                new_meta_ns['field_validators'] = merged_validators
            # Merge fields with base unit fields
            if 'fields' in our_meta.__dict__:
                # Look at all the base Meta classes and collect each
                # Meta.fields class as our (real) list of base classes.
                assert our_meta.fields.__bases__ == (SymbolDef,)
                merged_fields_bases = [
                    base_meta.fields
                    for base_meta in base_meta_list
                    if hasattr(base_meta, 'fields')]
                # If there are no base classes then let's just inherit from the
                # base SymbolDef class (not that we're actually ignoring any
                # base classes on the our_meta.fields class as it can only be
                # SymbolDef and nothing else is supported or makes sense.
                if not merged_fields_bases:
                    merged_fields_bases.append(SymbolDef)
                # The list of base fields needs to be a tuple
                merged_fields_bases = tuple(merged_fields_bases)
                # Copy all of the Symbol objects out of the our_meta.field
                # class that we're re-defining.
                merged_fields_ns = SymbolDefNs()
                for sym_name in dir(our_meta.fields):
                    sym = getattr(our_meta.fields, sym_name)
                    if isinstance(sym, Symbol):
                        merged_fields_ns[sym_name] = sym
                merged_fields_ns['__doc__'] = """
                A symbol definition containing all fields used by :class:`{}`

                This class is partially automatically generated. It always
                inherits from the Meta.fields class of the base unit class.
                """.format(name)
                # Create a new class in place of the 'fields' defined in
                # our_meta.fields.
                fields = SymbolDefMeta(
                    'fields', merged_fields_bases, merged_fields_ns)
                fields.__qualname__ = '{}.Meta.fields'.format(name)
                new_meta_ns['fields'] = fields
            # Ensure that Meta.name is explicitly defined
            if 'name' not in our_meta.__dict__:
                raise TypeError(_(
                    "Please define 'name' in {}.Meta"
                ).format(name))
            ns['Meta'] = type('Meta', new_meta_bases, new_meta_ns)
        ns['fields'] = ns['Meta'].fields
        return super().__new__(mcls, name, bases, ns)


class Unit(UnitLegacyAPI, metaclass=UnitType):
    """
    Units are representations of data loaded from RFC822 definitions

    Units are used by plainbox to represent various important objects loaded
    from the filesystem. All units have identical representation (RFC822
    records) but each unit type has different semantics.

    .. warning::
        There is no metaclass to do it automatically yet so please be aware
        that the Unit.Meta class (which is a collection of metadata, not a
        meta-class) needs to be manually inherited in each subclass of the Unit
        class.
    """

    def __init__(self, data, raw_data=None, origin=None, provider=None,
                 parameters=None, field_offset_map=None, virtual=False):
        """
        Initialize a new unit

        :param data:
            A dictionary of normalized data. This data is suitable for normal
            application usage. It is not suitable for gettext lookups as the
            original form is lost by the normalization process.
        :param raw_data:
            A dictionary of raw data (optional). Defaults to data. Values in
            this dictionary are in their raw form, as they were loaded from a
            unit file. This data is suitable for gettext lookups.
        :param origin:
            An (optional) Origin object. If omitted a fake origin object is
            created. Normally the origin object should be obtained from the
            RFC822Record object.
        :param parameters:
            An (optional) dictionary of parameters. Parameters allow for unit
            properties to be altered while maintaining a single definition.
            This is required to obtain translated summary and description
            fields, while having a single translated base text and any
            variation in the available parameters.
        :param field_offset_map:
            An optional dictionary with offsets (in line numbers) of each
            field.  Line numbers are relative to the value of origin.line_start
        :param virtual:
            An optional flag marking this unit as "virtual". It can be used
            to annotate units synthetized by PlainBox itself so that certain
            operations can treat them differently. It also helps with merging
            non-virtual and virtual units.
        """
        if raw_data is None:
            raw_data = data
        if origin is None:
            origin = Origin.get_caller_origin()
        if field_offset_map is None:
            field_offset_map = {field: 0 for field in data}
        self._data = data
        self._raw_data = raw_data
        self._origin = origin
        self._field_offset_map = field_offset_map
        self._provider = provider
        self._checksum = None
        self._parameters = parameters
        self._virtual = virtual

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
        assert cls is Unit, \
            "{}.instantiate_template() not customized".format(cls.__name__)
        return cls(data, raw_data, origin, provider, parameters,
                   field_offset_map)

    def __eq__(self, other):
        if not isinstance(other, Unit):
            return False
        return self.checksum == other.checksum

    def __ne__(self, other):
        if not isinstance(other, Unit):
            return True
        return self.checksum != other.checksum

    def __hash__(self):
        return hash(self.checksum)

    @property
    def unit(self):
        """
        the value of the unit field

        This property _may_ be overridden by certain subclasses but this
        behavior is not generally recommended.
        """
        return self.get_record_value('unit')

    def tr_unit(self):
        """
        Translated (optionally) value of the unit field (overridden)

        The return value is always 'self.Meta.name' (translated)
        """
        return _(self.Meta.name)

    @property
    def origin(self):
        """
        The Origin object associated with this Unit
        """
        return self._origin

    @property
    def field_offset_map(self):
        """
        The field-to-line-number-offset mapping.

        A dictionary mapping field name to offset (in lines) relative to the
        origin where that field definition commences.

        Note: the return value may be None
        """
        return self._field_offset_map

    @property
    def provider(self):
        """
        The provider object associated with this Unit
        """
        return self._provider

    @property
    def parameters(self):
        """
        The mapping of parameters supplied to this Unit

        This may be either a dictionary or None.

        .. seealso::
            :meth:`is_parametric()`
        """
        return self._parameters

    @property
    def virtual(self):
        """
        Flag indicating if this unit is a virtual unit

        Virtual units are created (synthetised) by PlainBox and don't exist
        in any one specific file as normal units do.
        """
        return self._virtual

    @property
    def is_parametric(self):
        """
        If true, then this unit is parametric

        Parametric units are instances of a template. To know which fields are
        constant and which are parametrized call the support method
        :meth:`get_accessed_parametes()`
        """
        return self._parameters is not None

    def get_accessed_parameters(self, *, force=False):
        """
        Get a set of attributes accessed from each template attribute

        :param force (keyword-only):
            If specified then it will operate despite being invoked on a
            non-parametric unit.  This is only intended to be called by
            TemplateUnit to inspect what the generated unit looks like in the
            early validation code.
        :returns:
            A dictionary of sets with names of attributes accessed by each
            template field. Note that for non-parametric Units the return value
            is always a dictionary of empty sets, regardless of how they actual
            parameter values look like.

        This function computes a dictionary of sets mapping from each template
        field (except from fields starting with the string 'template-') to a
        set of all the resource object attributes accessed by that element.
        """
        if force or self.is_parametric:
            return {
                key: get_accessed_parameters(value)
                for key, value in self._data.items()
            }
        else:
            return {key: frozenset() for key in self._data}

    @classmethod
    def from_rfc822_record(cls, record, provider=None):
        """
        Create a new Unit from RFC822 record. The resulting instance may not be
        valid but will always be created.

        :param record:
            A RFC822Record object
        :returns:
            A new Unit
        """
        # Strip the trailing newlines form all the raw values coming from the
        # RFC822 parser. We don't need them and they don't match gettext keys
        # (xgettext strips out those newlines)
        changed_raw_data = {
            key: value.rstrip('\n')
            for key, value in record.raw_data.items()
        }
        return cls(record.data, origin=record.origin,
                   raw_data=changed_raw_data, provider=provider,
                   field_offset_map=record.field_offset_map)

    def get_record_value(self, name, default=None):
        """
        Obtain the normalized value of the specified record attribute

        :param name:
            Name of the field to access
        :param default:
            Default value, used if the field is not defined in the unit
        :returns:
            The value of the field, possibly with parameters inserted, or the
            default value
        :raises:
            KeyError if the field is parametrized but parameters are incorrect
        """
        value = self._data.get('_{}'.format(name))
        if value is None:
            value = self._data.get('{}'.format(name), default)
        if value is not None and self.is_parametric:
            value = string.Formatter().vformat(value, (), self.parameters)
        return value

    def get_raw_record_value(self, name, default=None):
        """
        Obtain the raw value of the specified record attribute

        :param name:
            Name of the field to access
        :param default:
            Default value, used if the field is not defined in the unit
        :returns:
            The raw value of the field, possibly with parameters inserted, or
            the default value
        :raises:
            KeyError if the field is parametrized but parameters are incorrect

        The raw value may have additional whitespace or indentation around the
        text. It will also not have the magic RFC822 dots removed. In general
        the text will be just as it was parsed from the unit file.
        """
        value = self._raw_data.get('_{}'.format(name))
        if value is None:
            value = self._raw_data.get('{}'.format(name), default)
        if value is not None and self.is_parametric:
            value = string.Formatter().vformat(value, (), self.parameters)
        return value

    def get_translated_record_value(self, name, default=None):
        """
        Obtain the translated value of the specified record attribute

        :param name:
            Name of the field/attribute to access
        :param default:
            Default value, used if the field is not defined in the unit
        :returns:
            The (perhaps) translated value of the field with (perhaps)
            parameters inserted, or the default value. The idea is to return
            the best value we can but there are no guarantees on returning a
            translated value.
        :raises:
            KeyError if the field is parametrized but parameters are incorrect
            This may imply that the unit is invalid but it may also imply that
            translations are broken. A malicious translation can break
            formatting and prevent an otherwise valid unit from working.
        """
        # Try to access the marked-for-translation record
        msgid = self._raw_data.get('_{}'.format(name))
        if msgid is not None:
            # We now have a translatable message that we can look up in the
            # provider translation database.
            msgstr = self.get_translated_data(msgid)
            assert msgstr is not None
            # We now have the translation _or_ the untranslated msgid again.
            # We can now normalize it so that it looks nice:
            msgstr = normalize_rfc822_value(msgstr)
            # We can now feed it through the template system to get parameters
            # inserted.
            if self.is_parametric:
                # This should not fail if the unit validates okay but it still
                # might fail due to broken translations. Perhaps we should
                # handle exceptions here and hint that this might be the cause
                # of the problem?
                msgstr = string.Formatter().vformat(
                    msgstr, (), self.parameters)
            return msgstr
        # If there was no marked-for-translation value then let's just return
        # the normal (untranslatable) version.
        msgstr = self._data.get(name)
        if msgstr is not None:
            # NOTE: there is no need to normalize anything as we already got
            # the non-raw value here.
            if self.is_parametric:
                msgstr = string.Formatter().vformat(
                    msgstr, (), self.parameters)
            return msgstr
        # If we have nothing better let's just return the default value
        return default

    def is_translatable_field(self, name):
        """
        Check if a field is marked as translatable

        :param name:
            Name of the field to check
        :returns:
            True if the field is marked as translatable, False otherwise
        """
        return '_{}'.format(name) in self._data

    def qualify_id(self, some_id):
        """
        Transform some unit identifier to be fully qualified

        :param some_id:
            A potentially unqualified unit identifier
        :returns:
            A fully qualified unit identifier

        This method uses the namespace of the associated provider to transform
        unqualified unit identifiers to qualified identifiers. Qualified
        identifiers are left alone.
        """
        if "::" not in some_id and self.provider is not None:
            return "{}::{}".format(self.provider.namespace, some_id)
        else:
            return some_id

    @property
    def checksum(self):
        """
        Checksum of the unit definition.

        This property can be used to compute the checksum of the canonical form
        of the unit definition. The canonical form is the UTF-8 encoded JSON
        serialization of the data that makes up the full definition of the unit
        (all keys and values). The JSON serialization uses no indent and
        minimal separators.

        The checksum is defined as the SHA256 hash of the canonical form.
        """
        if self._checksum is None:
            self._checksum = self._compute_checksum()
        return self._checksum

    def _compute_checksum(self):
        """
        Compute the value for :attr:`checksum`.
        """
        # Ideally we'd use simplejson.dumps() with sorted keys to get
        # predictable serialization but that's another dependency. To get
        # something simple that is equally reliable, just sort all the keys
        # manually and ask standard json to serialize that..
        sorted_data = collections.OrderedDict(sorted(self._data.items()))
        # Define a helper function to convert symbols to strings for the
        # purpose of computing the checksum's canonical representation.

        def default_fn(obj):
            if isinstance(obj, Symbol):
                return str(obj)
            raise TypeError
        # Compute the canonical form which is arbitrarily defined as sorted
        # json text with default indent and separator settings.
        canonical_form = json.dumps(
            sorted_data, indent=None, separators=(',', ':'),
            default=default_fn)
        text = canonical_form.encode('UTF-8')
        # Parametric units also get a copy of their parameters stored as an
        # additional piece of data
        if self.is_parametric:
            sorted_parameters = collections.OrderedDict(
                sorted(self.parameters.items()))
            canonical_parameters = json.dumps(
                sorted_parameters, indent=None, separators=(',', ':'),
                default=default_fn)
            text += canonical_parameters.encode('UTF-8')
        # Compute the sha256 hash of the UTF-8 encoding of the canonical form
        # and return the hex digest as the checksum that can be displayed.
        return hashlib.sha256(text).hexdigest()

    def get_translated_data(self, msgid):
        """
        Get a localized piece of data

        :param msgid:
            data to translate
        :returns:
            translated data obtained from the provider if this unit has one,
            msgid itself otherwise.
        """
        if msgid and self._provider:
            return self._provider.get_translated_data(msgid)
        else:
            return msgid

    def get_normalized_translated_data(self, msgid):
        """
        Get a localized piece of data and filter it with RFC822 parser
        normalization

        :param msgid:
            data to translate
        :returns:
            translated and normalized data obtained from the provider if this
            unit has one, msgid itself otherwise.
        """
        msgstr = self.get_translated_data(msgid)
        if msgstr is not None:
            return normalize_rfc822_value(msgstr)
        else:
            return msgid

    def check(self, *, context=None, live=False):
        """
        Check this unit for correctness

        :param context:
            A keyword-only argument, if specified it should be a
            :class:`UnitValidationContext` instance used to validate a number
            of units together.
        :param live:
            A keyword-only argument, if True the return value is a generator
            that yields subsequent issues. Otherwise (default) the return value
            is buffered and returned as a list. Checking everything takes
            considerable time, for responsiveness, consider using live=True.
        :returns:
            A list of issues or a generator yielding subsequent issues. Each
            issue is a :class:`plainbox.impl.validation.Issue`.
        """
        if live:
            return self._check_gen(context)
        else:
            return list(self._check_gen(context))

    def _check_gen(self, context):
        validator = self.Meta.validator_cls()
        for issue in validator.check(self):
            yield issue
        if context is not None:
            for issue in validator.check_in_context(self, context):
                yield issue

    class Meta:
        """
        Class containing additional meta-data about this unit.

        :attr name:
            Name of this unit as it can appear in unit definition files
        :attr fields:
            A :class:`plainbox.impl.symbol.SymbolDef` with a symbol for each of
            the fields used by this unit.
        :attr validator_cls:
            A custom validator class specific to this unit
        :attr field_validators:
            A dictionary mapping each field to a list of field validators
        """

        name = 'unit'

        class fields(SymbolDef):
            """
            Unit defines only one field, the 'unit'
            """
            unit = 'unit'

        validator_cls = UnitValidator

        field_validators = {
            fields.unit: [
                # We don't want anyone marking unit type up for translation
                UntranslatableFieldValidator,
                # We want each instantiated template to define same unit type
                TemplateInvariantFieldValidator,
                # We want to gently advise everyone to mark all units with
                # and explicit unit type so that we can disable default 'job'
                PresentFieldValidator(
                    severity=Severity.advice,
                    message=_("unit should explicitly define its type")),
            ]
        }
