# This file is part of Checkbox.
#
# Copyright 2013 Canonical Ltd.
# Written by:
#   Zygmunt Krynicki <zygmunt.krynicki@canonical.com>
#
# Checkbox is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
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

        :cvar variable_list:
            A list of all Variable objects defined in the class

        :cvar section_list:
            A list of all Section object defined in the class

        :cvar filename_list:
            A list of config files (pathnames) to read on call to
            :meth:`Config.read`
    """
    variable_list = []
    section_list = []
    filename_list = []


class UnsetType:
    """
    Class of the Unset object
    """

    def __str__(self):
        return "unset"

    def __repr__(self):
        return "Unset"


Unset = UnsetType()


class Variable(INameTracking):
    """
    Variable that can be used in a configuration systems
    """

    _KIND_CHOICE = (bool, int, float, str)

    def __init__(self, name=None, *, section='DEFAULT', kind=str,
                 default=Unset, validator_list=None, help_text=None):
        # Ensure kind is correct
        if kind not in self._KIND_CHOICE:
            raise ValueError("unsupported kind")
        # Ensure that we have a validator_list, even if empty
        if validator_list is None:
            validator_list = []
        # Insert a KindValidator as the first validator to run
        validator_list.insert(0, KindValidator)
        # Assign all the attributes
        self._name = name
        self._section = section
        self._kind = kind
        self._default = default
        self._validator_list = validator_list
        self._help_text = help_text
        self._validate_default_value()
        # Workaround for Sphinx breaking if __doc__ is a property
        self.__doc__ = self.help_text or self.__class__.__doc__

    def _validate_default_value(self):
        """
        Validate the default value, unless it is Unset
        """
        if self.default is Unset:
            return
        for validator in self.validator_list:
            message = validator(self, self.default)
            if message is not None:
                raise ValidationError(self, self.default, message)

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
            return instance._get_variable(self._name)
        except KeyError:
            return self.default

    def __set__(self, instance, new_value):
        """
        Set the value of a variable

        :raises ValidationError: if the new value is incorrect
        """
        # Check it against all validators
        for validator in self.validator_list:
            message = validator(self, new_value)
            if message is not None:
                raise ValidationError(self, new_value, message)
        # Assign it to the backing store of the instance
        instance._set_variable(self.name, new_value)

    def __delete__(self, instance):
        # NOTE: this is quite confusing, this method is a companion to __get__
        # and __set__ but __del__ is entirely unrelated (object garbage
        # collected, do final cleanup) so don't think this is a mistake
        instance._del_variable(self._name)


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
        Internal method used by :meth:`ConfigMeta.__new__`
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
        if 'Meta' in namespace:
            if hasattr(namespace['Meta'], 'variable_list'):
                variable_list = namespace['Meta'].variable_list[:]
            if hasattr(namespace['Meta'], 'section_list'):
                section_list = namespace['Meta'].section_list[:]
        # Discover all Variable and Section instances
        # defined in the class namespace
        for name, item in namespace.items():
            if isinstance(item, INameTracking):
                item._set_tracked_name(name)
            if isinstance(item, Variable):
                variable_list.append(item)
            elif isinstance(item, Section):
                section_list.append(item)
        # Get or create the class of the 'Meta' object.
        #
        # This class should always inherit from ConfigMetaData and whatever the
        # user may have defined as Meta.
        Meta_name = "Meta"
        Meta_bases = (ConfigMetaData,)
        Meta_ns = {
            'variable_list': variable_list,
            'section_list': section_list
        }
        if 'Meta' in namespace:
            user_Meta_cls = namespace['Meta']
            if not isinstance(user_Meta_cls, type):
                raise TypeError("Meta must be a class")
            Meta_bases = (user_Meta_cls, ConfigMetaData)
        # Create a new type for the Meta class
        namespace['Meta'] = type.__new__(
            type(ConfigMetaData), Meta_name, Meta_bases, Meta_ns)
        # Create a new type for the Config subclass
        return type.__new__(mcls, name, bases, namespace)

    @classmethod
    def __prepare__(mcls, name, bases, **kwargs):
        return collections.OrderedDict()


class PlainBoxConfigParser(configparser.ConfigParser):
    """
    A simple ConfigParser subclass that does not lowercase
    key names.
    """
    def optionxform(self, option):
        return option


class Config(metaclass=ConfigMeta):
    """
    Base class for configuration systems

    :ivar _var:
        storage backend for Variable definitions

    :ivar _section:
        storage backend for Section definitions

    :ivar _filename_list:
        list of pathnames to files that were loaded by the last call to
        :meth:`read()`

    :ivar _problem_list:
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
            This method resets :ivar:`_problem_list` and
            :ivar:`_filename_list`.
        """
        parser = PlainBoxConfigParser()
        # Reset filename list and problem list
        self._filename_list = []
        self._problem_list = []
        # Try loading all of the config files
        try:
            self._filename_list = parser.read(filename_list)
        except configparser.Error as exc:
            self._problem_list.append(exc)
        # Pick a reader function appropriate for the kind of variable
        reader_fn = {
            str: parser.get,
            bool: parser.getboolean,
            int: parser.getint,
            float: parser.getfloat
        }
        # Load all variables that we know about
        for variable in self.Meta.variable_list:
            # Access the variable in the configuration file
            try:
                value = reader_fn[variable.kind](
                    variable.section, variable.name)
            except configparser.NoSectionError:
                continue
            except configparser.NoOptionError:
                continue
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
        return "expected a {}".format(variable.kind.__name__)


class PatternValidator(IValidator):
    """
    A validator ensuring that values match a given pattern
    """

    def __init__(self, pattern_text):
        self.pattern_text = pattern_text
        self.pattern = re.compile(pattern_text)

    def __call__(self, variable, new_value):
        if not self.pattern.match(new_value):
            return "does not match pattern: {!r}".format(self.pattern_text)
