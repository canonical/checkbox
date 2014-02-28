PlainBox Configuration System
=============================

PlainBox has a modular configuration system. The system allows one to define
static configuration models that are composed of variables. This is all
implemented in :mod:`plainbox.impl.secure.config` as two classes
:class:`plainbox.impl.secure.config.Config` and
:class:`plainbox.impl.secure.config.Variable`::

>>> from plainbox.impl.secure.config import Config, Variable

Configuration models
^^^^^^^^^^^^^^^^^^^^

Each subclass of :class:`plainbox.impl.secure.config.Config` defines a new
configuration model. The model is composed of named variables and sections
defined as members of the class using a quasi-declarative syntax::

    >>> class AppConfig(Config):
    ...     log_level = Variable()
    ...     log_file = Variable()

If you've ever used Django this will fell just like models and fields.

Using Config objects and Variables
----------------------------------

Each configuration class can be simply instantiated and used as an object with
attributes::

    >>> config = AppConfig()

Accessing any of the Variable attributes is handled and actually access data in
an underlying in-memory storage::

    >>> config.log_level = 'DEBUG'
    >>> assert config.log_level == 'DEBUG'

Writes are validated (see validators below), reads go to the backing store and,
if missing, pick the default from the variable declaration. By default values
are not constrained in any way.

The Unset value
---------------

Apart from handling arbitrary values, variables can store the ``Unset`` value,
which is of the special ``UnsetType``. Unset variables are used as the implicit
default values so understanding them is important.

The ``Unset`` value is always false in a boolean context. This makes it easier
to accommodate but applications are still expected to handle it correctly. One
way to do that is to provide a default value for **every** variable used.
Another is to use the :class:`~plainbox.impl.secure.config.NotUnsetValidator`
to prevent such values from reaching the application.

Using Variable with custom default values
-----------------------------------------

Each variable has a default value that is used when variable is accessed but
was not assigned or loaded from a config file before. By default that value is
a special :class:`~plainbox.impl.secure.config.Unset` object, but it can be
changed using the ``default`` keyword argument::

    >>> class AppConfig(Config):
    ...     log_level = Variable(default='INFO')
    ...     log_file = Variable()

Here a freshly instantiated AppConfig class has a value in the ``log_level``
attribute. Note that there is a difference between values that have been
assigned and values that are loaded from defaults, as it will be explained
later::

    >>> config = AppConfig()
    >>> assert config.log_level == "INFO'

Using Variables with custom sections
------------------------------------

Each variable has section name that is used to lookup data in a INI-like config
file. By default that section is set to ``'DEFAULT'``.

Particular variables can be assigned to a non-default section. This can help
managing multiple groups of unrelated settings in one class / file. To specify
a section simply use the ``section`` keyword::

    >>> class AppConfig(Config):
    ...     log_level = Variable(section='logging', default='WARNING')
    ...     log_file = Variable(
    ...         section='logging',
    ...         default='/var/log/plainbox.log')
    ...     debug = Variable(default=False)

Using sections has no impact on how particular variables are used by the
application, it is only an utility for managing complexity.

Using Variable with custom kind
-------------------------------

Variables cannot hold values of arbitrary python type. In fact only a fixed
list of types are supported and allowed, those are: ``str``, ``bool``, ``int``
and ``float``. By default all variables are treated as strings.

Different *kind* can be selected with the ``kind`` keyword argument. Setting it
to a type (as listed above) will have two effects:

1) Only values of that type will be allowed upon assignment. This acts as an
   implicit validator. It is also true for using the default ``str`` kind.
2) When reading configuration files from disk, the content of the file will be
   interpreted accordingly.

Let's expand our example to indicate that the ``debug`` variable is actually a
boolean::

    >>> class AppConfig(Config):
    ...     log_level = Variable(section='logging', default='WARNING')
    ...     log_file = Variable(
    ...         section='logging',
    ...         default='/var/log/plainbox.log')
    ...     debug = Variable(default=False, kind=bool)

Specifying Custom Validators
----------------------------

As mentioned above in the kind section, values are validated upon assignment.
By default all values are validated to check if the value is appropriate for
the variable ``kind``

In certain cases additional constraints may be necessary. Those can be
expressed as any callable object (function, method or anything else with a
``__call__`` method). Let's expand the example to ensure that ``log_level`` is
only one of fixed possible choices::

    >>> class ChoiceValidator:
    ...
    ...     def __init__(self, choices):
    ...         self.choices = choices
    ...
    ...     def __call__(self, variable, value):
    ...         if value not in self.choices:
    ...             return "unspported value"

Each time the check() method returns None, it is assumed that everything is
okay. Otherwise the returned string is used as a message and
:class:`plainbox.impl.secure.config.ValidationError` is raised.

To use the new validator simply pass it to the ``validator_list`` keyword
argument::

    >>> class AppConfig(Config):
    ...     log_level = Variable(
    ...         section='logging',
    ...         default='WARNING',
    ...         validator_list=[
    ...             ChoiceValidator([
    ...                 "DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"])])
    ...
    ...     log_file = Variable(
    ...         section='logging',
    ...         default='/var/log/plainbox.log')
    ...
    ...     debug = Variable(default=False, kind=bool)


.. note::

    Validators that want to see the ``Unset`` value need to be explicitly
    tagged, otherwise they will never see that value (they will not be called)
    but can assume that the value is of correct type (bool, int, float or str).

    If you need to write a validator that understands and somehow handles the
    Unset value, decorate it with the
    :func:`~plainbox.impl.secure.config.understands_Unset` decorator.

Using Section objects
---------------------

Sometimes there is a necessity to allow the user to add arbitrary key=value
data to the configuration file. This is possible using the
:class:`plainbox.impl.secure.config.Section` class. Consider this example::

    >>> class AppConfig(Config):
    ...     log_level = Variable(
    ...         section='logging',
    ...         default='WARNING',
    ...         validator_list=[
    ...             ChoiceValidator([
    ...                 "DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"])])
    ...
    ...     log_file = Variable(
    ...         section='logging',
    ...         default='/var/log/plainbox.log')
    ...
    ...     debug = Variable(default=False, kind=bool)
    ...
    ...     logger_levels = Section()

This is the same application config example we've been using. This time it's
extended with a ``logger_levels`` attribute. The intent for this attribute is
to allow the user to customise the logging level for any named logger. This
could be implemented by iterating over all the values of that section and
setting the level accordingly.

.. note::
    Accessing Section objects returns a dictionary of the key-value pairs that
    were defined in that section.

Loading configuration from file
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Configuration objects are not of much use without being able to load data from
actual files. This is fully supported using just one call to
:meth:`plainbox.impl.secure.config.Config.read()`. Read takes a list of files
to read as argument and tries to parse and load data from each existing file.
Missing files are silently ignored.

Because configuration files may be corrupted, have typos, incorrectly specified
values or other human-caused mistakes. The read() operation never fails as the
application probably does not want to block on errors unconditionally. Instead
after calling read() the application may inspect two instance attributes:
:attr:`plainbox.impl.secure.config.Config.problem_list` and
:attr:`plainbox.impl.secure.config.Config.filename_list`. They contain the list
of exceptions raised while trying to load and use the configuration files and
the list of files that were actually loaded, respectively.

The Config.Meta class
^^^^^^^^^^^^^^^^^^^^^

Each Config class or subclass has a special Meta class as an attribute. This is
*not* about the python metaclass system. This is a special helper class that
contains a list of meta-data about each Config class.

The Meta class has several attributes that are used internally but can be
sometimes useful for applications.

Meta.variable_list
------------------

This attribute holds a list of all the Variable objects defined in the parent
Config class. The order is maintained exactly as defined by the source code.

Meta.section_list
-----------------

This attribute holds a list of all the Section objects defined in the parent
Config class. The order is maintained exactly as defined in the source code.

Meta.filename_list
------------------

This attribute is an empty list by default. The intent is to hold a list of all
the possible pathnames that the configuration should be loaded from. This field
is used by :func:`plainbox.impl.secure.config.Config.get()` method.

Typically this field is specified in a custom version of the Meta class to
encode where the configuration files are typically stored.

Notes on subclassing Meta
-------------------------

A Config sub-class can define a custom Meta class with any attributes that may
be desired. That class will be merged with an internal
:class:`plainbox.impl.secure.config.ConfigMetaData` class. In effect the actual
Meta attribute will be a new type that inherits from both the custom class that
was specified in the source code and the standard ConfigMetaData class.

This mechanism is fully transparent to the user. There is no need to explicitly
inherit from ConfigMetaData directly.

The Unset value
^^^^^^^^^^^^^^^

The config system uses a special value :obj:`plainbox.impl.secure.config.Unset`
which is the only instance of :class:`plainbox.impl.secure.config.UnsetType`.
Unset is used instead of ``None`` as an implicit default for each ``Variable``

The only thing that ``Unset`` is special for is that it evaluates to false in a
boolean context.
