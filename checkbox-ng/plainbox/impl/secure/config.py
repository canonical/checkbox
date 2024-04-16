# This file is part of Checkbox.
#
# Copyright 2013, 2014 Canonical Ltd.
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
:mod:`plainbox.impl.config` -- configuration
============================================

.. warning::

    THIS MODULE DOES NOT HAVE A STABLE PUBLIC API
"""

from abc import ABCMeta, abstractmethod
import collections
import configparser
import logging
import re
import shlex

from plainbox.i18n import gettext as _


logger = logging.getLogger("plainbox.config")


class INameTracking(metaclass=ABCMeta):
    """
    Interface for classes that are instantiated as a part of definition of
    another class. The purpose of this interface is to allow instances to learn
    about the name (python identifier) that was assigned to the instance at
    class definition time.

    Subclasses must define the _set_tracked_name() method.
    """

    @abstractmethod
    def _set_tracked_name(self, name):
        """
        Set the that corresponds to the symbol used in class definition. This
        can be a no-op if the name was already set by other means
        """


class ConfigMetaData:
    """
    Class containing meta-data about a Config class

    Sub-classes of this class are automatically added to each Config subclass
    as a Meta class-level attribute.

    This class has typically two attributes:

    :attr variable_list:
        A list of all Variable objects defined in the class
    :attr section_list:
        A list of all Section object defined in the class
    :attr filename_list:
        A list of config files (pathnames) to read on call to
        :meth:`Config.read`
    """

    variable_list = []
    section_list = []
    parametric_section_list = []
    filename_list = []


class UnsetType:
    """
    Class of the Unset object
    """

    def __str__(self):
        return _("unset")

    def __repr__(self):
        return "Unset"

    def __bool__(self):
        return False


Unset = UnsetType()


def understands_Unset(cls_or_func):
    """
    Decorator for marking validators as supporting the special Unset value.

    This decorator should be applied to every validator that natively supports
    Unset values. Without it, Unset is never validated.

    This decorator works by setting the ``understands_Unset`` attribute on the
    decorated object and returning it intact.
    """
    cls_or_func.understands_Unset = True
    return cls_or_func


class Variable(INameTracking):
    """
    Variable that can be used in a configuration systems
    """

    _KIND_CHOICE = (bool, int, float, str, list)

    def __init__(
        self,
        name=None,
        *,
        section="DEFAULT",
        kind=str,
        default=Unset,
        validator_list=None,
        help_text=None
    ):
        # Ensure kind is correct
        if kind not in self._KIND_CHOICE:
            raise ValueError(_("unsupported kind"))
        # Ensure that we have a validator_list, even if empty
        if validator_list is None:
            validator_list = []
        if validator_list and isinstance(validator_list[0], NotUnsetValidator):
            # XXX: Kludge ahead, beware!
            # Insert a KindValidator as the second validator to run
            # just after the NotUnsetValidator
            # TODO: To properly handle this without any special-casing we
            # should drop the implicit insertion of the KindValidator and
            # convert all users to properly order KindValidator and
            # NotUnsetValidator instances so that the error message is helpful
            # to the user. The whole idea is to validate Unset before we try to
            # validate the type.
            validator_list.insert(1, KindValidator)
        else:
            # Insert a KindValidator as the first validator to run
            validator_list.insert(0, KindValidator)
        # Assign all the attributes
        self._name = name
        self._section = section
        self._kind = kind
        self._default = default
        self._validator_list = validator_list
        self._help_text = help_text
        # Workaround for Sphinx breaking if __doc__ is a property
        self.__doc__ = self.help_text or self.__class__.__doc__

    def validate(self, value):
        """
        Check if the supplied value is valid for this variable.

        :param value:
            The proposed value
        :raises ValidationError:
            If the value was not valid in any way
        """
        for validator in self.validator_list:
            # Most validators don't want to deal with the unset type so let's
            # special case that.  Anything that is decorated with
            # @understands_Unset will have that attribute set to True.
            #
            # If the value _is_ unset and the validator doesn't claim to
            # support it then just skip it.
            if value is Unset and not getattr(
                validator, "understands_Unset", False
            ):
                continue
            message = validator(self, value)
            if message is not None:
                raise ValidationError(self, value, message)

    def _set_tracked_name(self, name):
        """
        Internal method used by :meth:`ConfigMeta.__new__`
        """
        if self._name is None:
            self._name = name

    @property
    def name(self):
        """
        name of this variable
        """
        return self._name

    @property
    def mangled_name(self):
        """
        name prefixed by the name of the section name and '__' to resolve
        conflicts between same name  variables living in different sections
        """
        return "{}__{}".format(self._section, self._name)

    @property
    def section(self):
        """
        name of the section this variable belongs to (in a configuration file)
        """
        return self._section

    @property
    def kind(self):
        """
        the "poor man's type", can be only str (default), bool, float or int
        """
        return self._kind

    @property
    def default(self):
        """
        a default value, if any
        """
        return self._default

    @property
    def validator_list(self):
        """
        a optional list of :class:`Validator` instances that are enforced on
        the value
        """
        return self._validator_list

    @property
    def help_text(self):
        """
        an optional help text associated with this variable
        """
        return self._help_text

    def __repr__(self):
        return "<Variable name:{!r}>".format(self.name)

    def __get__(self, instance, owner):
        """
        Get the value of a variable

        Missing variables return the default value
        """
        if instance is None:
            return self
        try:
            return instance._get_variable(self.mangled_name)
        except KeyError:
            return self.default

    def __set__(self, instance, new_value):
        """
        Set the value of a variable

        :raises ValidationError: if the new value is incorrect
        """
        # Check it against all validators
        self.validate(new_value)
        # Assign it to the backing store of the instance
        instance._set_variable(self.mangled_name, new_value)

    def __delete__(self, instance):
        # NOTE: this is quite confusing, this method is a companion to __get__
        # and __set__ but __del__ is entirely unrelated (object garbage
        # collected, do final cleanup) so don't think this is a mistake
        instance._del_variable(self.mangled_name)


class Section(INameTracking):
    """
    A section of a configuration file.
    """

    def __init__(self, name=None, *, help_text=None):
        self._name = name
        self._help_text = help_text
        # Workaround for Sphinx breaking if __doc__ is a property
        self.__doc__ = self.help_text or self.__class__.__doc__

    def _set_tracked_name(self, name):
        """
        Internal method used by :meth:`ConfigMeta.__new__()`
        """
        if self._name is None:
            self._name = name

    @property
    def name(self):
        """
        name of this section
        """
        return self._name

    @property
    def help_text(self):
        """
        an optional help text associated with this section
        """
        return self._help_text

    def __get__(self, instance, owner):
        if instance is None:
            return self
        try:
            return instance._get_section(self._name)
        except KeyError:
            return Unset

    def __set__(self, instance, new_value):
        instance._set_section(self.name, new_value)

    def __delete__(self, instance):
        instance._del_section(self.name)


class ParametricSection(Section):
    """
    A parametrized section of a configuration file.

    This is similar to :class:`Section`, but instead looks for an arbitrary
    number of sections beginning with ``name:``. E.g.:

    .. code-block:: none

        [foo:bar]
            somevar = someval
        [foo:baz]
            othervar = otherval

    yields a following list of dictionaries:

    .. code-block:: python

        [
            {'bar': {'somevar': 'someval'}},
            {'baz': {'othervar': 'otherval'}}
        ]
    """

    def __init__(self, name=None, *, help_text=None):
        super().__init__(name, help_text=help_text)


class ConfigMeta(type):
    """
    Meta class for all configuration classes.

    This meta class handles assignment of '_name' attribute to each
    :class:`Variable` instance created in the class body.

    It also accumulates such instances and assigns them to variable_list in a
    helper Meta class which is assigned back to the namespace
    """

    def __new__(mcls, name, bases, namespace, **kwargs):
        # Keep track of variables and sections from base class
        variable_list = []
        section_list = []
        parametric_section_list = []
        if "Meta" in namespace:
            if hasattr(namespace["Meta"], "variable_list"):
                variable_list = namespace["Meta"].variable_list[:]
            if hasattr(namespace["Meta"], "section_list"):
                section_list = namespace["Meta"].section_list[:]
            if hasattr(namespace["Meta"], "parametric_section_list"):
                parametric_section_list = namespace[
                    "Meta"
                ].parametric_section_list[:]
        # Discover all Variable and Section instances
        # defined in the class namespace
        for attr_name, attr_value in namespace.items():
            if isinstance(attr_value, INameTracking):
                attr_value._set_tracked_name(attr_name)
            if isinstance(attr_value, Variable):
                variable_list.append(attr_value)
            elif isinstance(attr_value, ParametricSection):
                parametric_section_list.append(attr_value)
            elif isinstance(attr_value, Section):
                section_list.append(attr_value)
        # Get or create the class of the 'Meta' object.
        #
        # This class should always inherit from ConfigMetaData and whatever the
        # user may have defined as Meta.
        Meta_name = "Meta"
        Meta_bases = (ConfigMetaData,)
        Meta_ns = {
            "variable_list": variable_list,
            "section_list": section_list,
            "parametric_section_list": parametric_section_list,
        }
        if "Meta" in namespace:
            user_Meta_cls = namespace["Meta"]
            if not isinstance(user_Meta_cls, type):
                raise TypeError("Meta must be a class")
            Meta_bases = (user_Meta_cls, ConfigMetaData)
        # Create a new type for the Meta class
        namespace["Meta"] = type.__new__(
            type(ConfigMetaData), Meta_name, Meta_bases, Meta_ns
        )
        # Create a new type for the Config subclass
        return type.__new__(mcls, name, bases, namespace)

    @classmethod
    def __prepare__(mcls, name, bases, **kwargs):
        return collections.OrderedDict()


class PlainBoxConfigParser(configparser.ConfigParser):
    """
    A subclass of ConfigParser with the following changes:

    - option names are not lower-cased
    - write() has deterministic ordering (sorted by name)
    - parsing list capability
    """

    def optionxform(self, option):
        """
        Overridden method from :class:`configparser.ConfigParser`.

        Returns `option` without any transformations
        """
        return option

    def write(self, fp, space_around_delimiters=True):
        """
        Write an .ini-format representation of the configuration state.

        If `space_around_delimiters` is True (the default), delimiters between
        keys and values are surrounded by spaces. The ordering of section and
        values within is deterministic.
        """
        if space_around_delimiters:
            d = " {} ".format(self._delimiters[0])
        else:
            d = self._delimiters[0]
        if self._defaults:
            self._write_section(
                fp, self.default_section, sorted(self._defaults.items()), d
            )
        for section in self._sections:
            self._write_section(
                fp, section, sorted(self._sections[section].items()), d
            )

    def getlist(
        self,
        section,
        option,
        *,
        raw=False,
        vars=None,
        fallback=configparser._UNSET,
        **kwargs
    ):
        return self._get(section, self._convert_to_list, option, **kwargs)

    def _convert_to_list(self, value):
        """Return list extracted from value.

        The ``value`` is split using ',' and ' ' as delimiters.
        """
        return shlex.split(value.replace(",", " "))


class Config(metaclass=ConfigMeta):
    """
    Base class for configuration systems

    :attr _var:
        storage backend for Variable definitions
    :attr _section:
        storage backend for Section definitions
    :attr _filename_list:
        list of pathnames to files that were loaded by the last call to
        :meth:`read()`
    :attr _problem_list:
        list of :class:`ValidationError` that were detected by the last call to
        :meth:`read()`
    """

    def __init__(self):
        """
        Initialize an empty Config object
        """
        self._var = {}
        self._section = {}
        self._filename_list = []
        self._problem_list = []

    @property
    def problem_list(self):
        """
        list of :class:`ValidationError` that were detected by the last call to
        :meth:`read()`
        """
        return self._problem_list

    @property
    def filename_list(self):
        """
        list of pathnames to files that were loaded by the last call to
        :meth:`read()`
        """
        return self._filename_list

    @classmethod
    def get(cls):
        """
        Get an instance of this Config class with all the configuration loaded
        from default locations. The locations are determined by
        Meta.filename_list attribute.

        :returns: fresh :class:`Config` instance

        """
        self = cls()
        self.read(cls.Meta.filename_list)
        return self

    def get_parser_obj(self):
        """
        Get a ConfigParser-like object with the same data.

        :returns:
            A :class:`PlainBoxConfigParser` object with all of the data copied
            from this :class:`Config` object.

        Since :class:`PlainBoxConfigParser` is a subclass of
        :class:`configparser.ConfigParser` it has a number of useful utility
        methods.  By using this function one can obtain a ConfigParser-like
        object and work with it directly.
        """
        parser = PlainBoxConfigParser(allow_no_value=True, delimiters=("="))
        # Write all variables that we know about
        for variable in self.Meta.variable_list:
            if (
                not parser.has_section(variable.section)
                and variable.section != "DEFAULT"
            ):
                parser.add_section(variable.section)
            value = variable.__get__(self, self.__class__)
            # Except Unset, we don't want that to convert to 'unset'
            if value is not Unset:
                if variable.kind == list:
                    value = ", ".join(value)
                parser.set(variable.section, variable.name, str(value))
        # Write all sections that we know about
        for section in self.Meta.section_list:
            if not parser.has_section(section.name):
                parser.add_section(section.name)
            for name, value in section.__get__(self, self.__class__).items():
                parser.set(section.name, name, str(value))
        for psection in self.Meta.parametric_section_list:
            for name, sec in psection.__get__(self, self.__class__).items():
                section_name = "{}:{}".format(psection.name, name)
                if not parser.has_section(section_name):
                    parser.add_section(section_name)
                for k, v in sec.items():
                    parser.set(section_name, k, str(v))
        return parser

    def read_string(self, string, reset=True):
        """
        Load settings from a string.

        :param string:
            The full text of INI-like configuration to parse and apply

        This method parses the string as an INI file using
        :class:`PlainBoxConfigParser` (a simple ConfigParser subclass that
        respects the case of key names).

        If any problem is detected during parsing (e.g. syntax errors) those
        are captured and added to the :attr:`Config.problem_list`.

        After parsing the string each :class:`Variable` and :class:`Section`
        defined in the :class:`Config` class is assigned with the data from the
        configuration data.

        Any variables that cannot be assigned and raise
        :class:`ValidationError` are ignored but the list of problems is saved.

        All unused configuration (extra variables that are not defined as
        either Variable or Section class) is silently ignored.

        .. note::
            This method resets :attr:`_problem_list`
            and :attr:`_filename_list`.
        """
        parser = PlainBoxConfigParser(allow_no_value=True, delimiters=("="))
        if reset:
            # Reset filename list and problem list
            self._filename_list = []
            self._problem_list = []
        # Try loading all of the config files
        parser.read(self._filename_list)
        try:
            parser.read_string(string)
        except configparser.Error as exc:
            self._problem_list.append(exc)
        # Try to validate everything
        try:
            self._read_commit(parser)
        except ValidationError as exc:
            self._problem_list.append(exc)

    def write(self, stream):
        """
        Write configuration data to a stream.

        :param stream:
            a file-like object that can be written to.

        This method recreates the content of all the configuration variables in
        a manner that can be subsequently read back.
        """
        self.get_parser_obj().write(stream)

    def read(self, filename_list):
        """
        Load and merge settings from many files.

        This method tries to open each file from the list of filenames, parse
        it as an INI file using :class:`PlainBoxConfigParser` (a simple
        ConfigParser subclass that respects the case of key names). The list of
        files actually accessed is saved as available as
        :attr:`Config.filename_list`.

        If any problem is detected during parsing (e.g. syntax errors) those
        are captured and added to the :attr:`Config.problem_list`.

        After all files are loaded each :class:`Variable` and :class:`Section`
        defined in the :class:`Config` class is assigned with the data from the
        merged configuration data.

        Any variables that cannot be assigned and raise
        :class:`ValidationError` are ignored but the list of problems is saved.

        All unused configuration (extra variables that are not defined as
        either Variable or Section class) is silently ignored.

        .. note::

            This method resets :attr:`_problem_list`
            and :attr:`_filename_list`.
        """
        parser = PlainBoxConfigParser(allow_no_value=True, delimiters=("="))
        # Reset filename list and problem list
        self._filename_list = []
        self._problem_list = []
        logger.info(_("Loading configuration from %s"), filename_list)
        self._filename_list = parser.read(filename_list)
        # Try to validate everything
        try:
            self._read_commit(parser)
        except ValidationError as exc:
            self._problem_list.append(exc)

    def _read_commit(self, parser):
        # Pick a reader function appropriate for the kind of variable
        reader_fn = {
            str: parser.get,
            bool: parser.getboolean,
            int: parser.getint,
            float: parser.getfloat,
            list: parser.getlist,
        }
        # Load all variables that we know about
        for variable in self.Meta.variable_list:
            # Access the variable in the configuration file
            try:
                value = reader_fn[variable.kind](
                    variable.section, variable.name
                )
            except (configparser.NoSectionError, configparser.NoOptionError):
                value = variable.default
            # Try to assign it
            try:
                variable.__set__(self, value)
            except ValidationError as exc:
                self.problem_list.append(exc)
        # Load all sections that we know about
        for section in self.Meta.section_list:
            try:
                # Access the section in the configuration file
                value = dict(parser.items(section.name))
            except configparser.NoSectionError:
                continue
            # Assign it
            section.__set__(self, value)
        # Load all parametric sections
        for parametric_section in self.Meta.parametric_section_list:
            matching_keys = [
                k
                for k in parser.keys()
                if k.startswith(parametric_section.name + ":")
            ]
            value = dict()
            for key in matching_keys:
                param = key[len(parametric_section.name) + 1 :]
                value[param] = dict(parser.items(key))
            parametric_section.__set__(self, value)

        # Validate the whole configuration object
        self.validate_whole()

    def _get_variable(self, name):
        """
        Internal method called by :meth:`Variable.__get__`
        """
        return self._var[name]

    def _set_variable(self, name, value):
        """
        Internal method called by :meth:`Variable.__set__`
        """
        self._var[name] = value

    def _del_variable(self, name):
        """
        Internal method called by :meth:`Variable.__delete__`
        """
        del self._var[name]

    def _get_section(self, name):
        """
        Internal method called by :meth:`Section.__get__`
        """
        return self._section[name]

    def _set_section(self, name, value):
        """
        Internal method called by :meth:`Section.__set__`
        """
        self._section[name] = value

    def _del_section(self, name):
        """
        Internal method called by :meth:`Section.__delete__`
        """
        del self._section[name]

    def validate_whole(self):
        """
        Validate the whole configuration object.

        This method may be overridden to provide whole-configuration
        validation. It is especially useful in cases when a pair or more of
        variables need to be validated together to be meaningful.

        The default implementation does nothing. Other implementations may
        raise :class:`ValidationError`.
        """


class ValidationError(ValueError):
    """
    Exception raised when configuration variables fail to validate
    """

    def __init__(self, variable, new_value, message):
        self.variable = variable
        self.new_value = new_value
        self.message = message

    def __str__(self):
        return self.message


class IValidator(metaclass=ABCMeta):
    """
    An interface for variable vale validators
    """

    @abstractmethod
    def __call__(self, variable, new_value):
        """
        Check if a value is appropriate for the variable.

        :returns: None if everything is okay
        :returns: string that describes the problem if the value cannot be used
        """


def KindValidator(variable, new_value):
    """
    A validator ensuring that values match the "kind" of the variable.
    """
    if not isinstance(new_value, variable.kind):
        return {
            bool: _("expected a boolean"),
            int: _("expected an integer"),
            float: _("expected a floating point number"),
            str: _("expected a string"),
            list: _("expected a list of strings"),
        }[variable.kind]


class PatternValidator(IValidator):
    """
    A validator ensuring that values match a given pattern
    """

    def __init__(self, pattern_text):
        self.pattern_text = pattern_text
        self.pattern = re.compile(pattern_text)

    def __call__(self, variable, new_value):
        if not self.pattern.match(new_value):
            return _("does not match pattern: {!r}").format(self.pattern_text)

    def __eq__(self, other):
        if isinstance(other, PatternValidator):
            return self.pattern_text == other.pattern_text
        else:
            return False


class ChoiceValidator(IValidator):
    """
    A validator ensuring that values are in a given set
    """

    def __init__(self, choice_list):
        self.choice_list = choice_list

    def __call__(self, variable, new_value):
        if new_value not in self.choice_list:
            return _("{} must be one of {}. Got '{}'").format(
                variable.name, ", ".join(self.choice_list), new_value
            )

    def __eq__(self, other):
        if isinstance(other, ChoiceValidator):
            return self.choice_list == other.choice_list
        else:
            return False


class SubsetValidator(IValidator):
    """A validator ensuring that value is a subset of a given set."""

    def __init__(self, superset):
        self.superset = set(superset)

    def __call__(self, variable, subset):
        if not set(subset).issubset(self.superset):
            return _("{} must be a subset of {}. Got {}").format(
                variable.name, self.superset, set(subset)
            )

    def __eq__(self, other):
        if isinstance(other, SubsetValidator):
            return self.superset == other.superset
        else:
            return False


class OneOrTheOtherValidator(IValidator):
    """
    A validator ensuring that values only from one or the other set are used.
    """

    def __init__(self, a_set, b_set):
        # the sets have to be disjoint
        assert not a_set & b_set
        self.a_set = set(a_set)
        self.b_set = set(b_set)

    def __call__(self, variable, values):
        has_common_with_a = bool(self.a_set & set(values))
        has_common_with_b = bool(self.b_set & set(values))
        if has_common_with_a and has_common_with_b:
            return _(
                "{} can only use values from {} or from {}".format(
                    variable.name, self.a_set, self.b_set
                )
            )

    def __eq__(self, other):
        if isinstance(other, OneOrTheOtherValidator):
            return self.a_set == other.a_set and self.b_set == other.b_set


@understands_Unset
class NotUnsetValidator(IValidator):
    """
    A validator ensuring that values are set

    ..note::
        Due to the way validators work this validator *must* be the first
        one in any validator list in order to work. Otherwise the implicit
        :func:`KindValidator` will take precedence and the check will most
        likely fail as None or Unset are not of the expected type of the
        configuration variable being worked with.
    """

    def __init__(self, msg=None):
        if msg is None:
            msg = _("must be set to something")
        self.msg = msg

    def __call__(self, variable, new_value):
        if new_value is Unset:
            return self.msg

    def __eq__(self, other):
        if isinstance(other, NotUnsetValidator):
            return self.msg == other.msg
        else:
            return False


class NotEmptyValidator(IValidator):
    """
    A validator ensuring that values aren't empty
    """

    def __init__(self, msg=None):
        if msg is None:
            msg = _("cannot be empty")
        self.msg = msg

    def __call__(self, variable, new_value):
        if new_value == "":
            return self.msg

    def __eq__(self, other):
        if isinstance(other, NotEmptyValidator):
            return self.msg == other.msg
        else:
            return False
