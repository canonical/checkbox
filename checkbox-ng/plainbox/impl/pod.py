# encoding: utf-8
# This file is part of Checkbox.
#
# Copyright 2012-2015 Canonical Ltd.
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
Plain Old Data.

:mod:`plainbox.impl.pod`
========================

This module contains the :class:`POD` and :class:`Field` classes that simplify
creation of declarative struct-like data holding classes. POD classes get a
useful repr() method, useful initializer and accessors for each of the fields
defined inside. POD classes can be inherited (properly detecting any field
clashes)

Defining POD classes:

    >>> class Person(POD):
    ...     name = Field("name of the person", str, MANDATORY)
    ...     age = Field("age of the person", int)


Creating POD instances, positional arguments match field definition order:

    >>> joe = Person("joe", age=42)

Full-blown comparison (not only equality):

    >>> joe == Person("joe", 42)
    True

Reading and writing attributes also works (obviously):

    >>> joe.name
    'joe'
    >>> joe.age
    42
    >>> joe.age = 24
    >>> joe.age
    24

For a full description check out the documentation of the :class:`POD` and
:class:`Field`.
"""
from collections import OrderedDict
from collections import namedtuple
from functools import total_ordering
from logging import getLogger
from textwrap import dedent

from plainbox.i18n import gettext as _
from plainbox.vendor import morris

__all__ = ('POD', 'PODBase', 'podify', 'Field', 'MANDATORY', 'UNSET',
           'read_only_assign_filter', 'type_convert_assign_filter',
           'type_check_assign_filter', 'modify_field_docstring')


_logger = getLogger("plainbox.pod")


class _Singleton:

    """A simple object()-like singleton that has a more useful repr()."""

    def __repr__(self):
        return self.__class__.__name__


class MANDATORY(_Singleton):

    """
    Class for the special MANDATORY object.

    This object can be used as a value in :attr:`Field.initial`.

    Using ``MANDATORY`` on a field like that makes the explicit initialization
    of the field mandatory during POD initialization. Please use this value to
    require that the caller supplies a given argument to the POD you are
    working with.
    """


MANDATORY = MANDATORY()


class UNSET(_Singleton):

    """
    Class of the special UNSET object.

    Singleton that is implicitly assigned to the values of all fields during
    POD initialization. This way all fields will have a value, even early at
    the time a POD is initialized. This can be important if the POD is somehow
    repr()-ed or inspected in other means.

    This object is also used by the :func:`read_only_assign_filter` function.
    """


UNSET = UNSET()


class Field:

    """
    A field in a plain-old-data class.

    Each field declares one attribute that can be read and written to. Just
    like a C structure. Attributes are readable _and_ writable but there is a
    lot of flexibility in what happens.

    :attr name:
        Name of the field (this is how this field can be accessed on the class
        or instance that contains it). This gets set by
        :meth:`_FieldCollection.inspect_namespace()`
    :attr instance_attr:
        Name of the POD dictionary entry used as backing store. This is set the
        same as ``name`` above. By default that's just name prepended with the
        ``'_'`` character.
    :attr type:
        An optional type hit. This is not used by default but assign filters
        can inspect and use this for type checking. It can also be used for
        documenting the intent of the field.
    :attr __doc__:
        The docstring of the field, as initialized by the caller.
    :attr initial:
        Initial value of this field, can be changed by passing arguments to
        :meth:`POD.__init__()`. May be set to ``MANDATORY`` for a special
        meaning (see below).
    :attr initial_fn:
        If not None this is a callable that produces the ``initial`` value for
        each new POD object.
    :attr notify:
        If True, a on_{name}_changed
        A flag controlling if notification events are sent for each
        modification of POD data through field.
    :attr notify_fn:
        An (optional) function to use as the first responder to the change
        notification signal. This field is only used if the ``notify``
        attribute is set to ``True``.
    :attr assign_filter_list:
        An (optional) list of assignment filter functions.

    A field is initialized based on the arguments passed to the POD
    initializer. If no argument is passed that would correspond to a given
    field the *initial* value is used. The *initial* value is either a constant
    (reference) stored in the ``initial`` property of the field or the return
    value of the callable in ``initial_fn``. Please make sure to use
    ``initial_fn`` if the value is not immutable as otherwise the produced
    value may be unintentionally shared by multiple objects.

    If the ``initial`` value is the special constant ``MANDATORY`` then the
    corresponding field must be explicitly initialized by the POD initializer
    argument list or a TypeError is raised.

    The ``notify`` flag controls the existence of the ``on_{name}_changed(old,
    new)`` signal on the class that includes the field. Applications can
    connect to that signal to observe changes. The signal is fired whenever the
    newly-assigned value compares *unequal* to the value currently stored in
    the POD.

    The ``notify_fn`` is an optional function that is used instead of the
    default (internal) :meth:`on_changed()` method of the Field class itself.
    If specified it must have the same three-argument signature. It will be
    called whenever the value of the field changes. Note that it will also be
    called on the initial assignment, when the ``old`` argument it receives
    will be set to the special ``UNSET`` object.

    Lastly a docstring and type hint can be provided for documentation. The
    type check is not enforced.

    Assignment filters are used to inspect and optionally modify a value during
    assignment (including the assignment done on object initialization) and can
    be used for various operations (including type conversions and validation).
    Assignment filters are called whenever a field is used to write to a POD.

    Since assignment filters are arranged in a list and executed in-order, they
    can also be used to modify the value as it gets propagated through the list
    of filters.

    The signature of each filter is ``fn(pod, field, old_value, new_value)``.
    The return value is the value shown to the subsequent filter or finally
    assigned to the POD.
    """

    _counter = 0

    def __init__(self, doc=None, type=None, initial=None, initial_fn=None,
                 notify=False, notify_fn=None, assign_filter_list=None):
        """Initialize (define) a new POD field."""
        self.__doc__ = dedent(doc) if doc is not None else None
        self.type = type
        self.initial = initial
        self.initial_fn = initial_fn
        self.notify = notify
        self.notify_fn = notify_fn
        self.assign_filter_list = assign_filter_list
        self.name = None  # Set via :meth:`gain_name()`
        self.instance_attr = None  # ditto
        self.signal_name = None  # ditto
        doc_extra = []
        for fn in self.assign_filter_list or ():
            if hasattr(fn, 'field_docstring_ext'):
                doc_extra.append(fn.field_docstring_ext.format(field=self))
        if doc_extra:
            self.__doc__ += (
                '\n\nSide effects of assign filters:\n'
                + '\n'.join('  - {}'.format(extra) for extra in doc_extra))
        self.counter = self.__class__._counter
        self.__class__._counter += 1

    @property
    def change_notifier(self):
        """
        Decorator for changing the change notification function.

        This decorator can be used to define all the fields in one block and
        all the notification function in another block. It helps to make the
        code easier to read.

        Example::

            >>> class Person(POD):
            ...     name = Field()
            ...
            ...     @name.change_notifier
            ...     def _name_changed(self, old, new):
            ...         print("changed from {!r} to {!r}".format(old, new))
            >>> person = Person()
            changed from UNSET to None
            >>> person.name = "bob"
            changed from None to 'bob'

        .. note::
            Keep in mind that the decorated function is converted to a signal
            automatically. The name of the function is also irrelevant, the POD
            core automatically creates signals that have consistent names of
            ``on_{field}_changed()``.
        """
        def decorator(fn):
            self.notify = True
            self.notify_fn = fn
            return fn
        return decorator

    def __repr__(self):
        """Get a debugging representation of a field."""
        return "<{} name:{!r}>".format(self.__class__.__name__, self.name)

    @property
    def is_mandatory(self) -> bool:
        """Flag indicating if the field needs a mandatory initializer."""
        return self.initial is MANDATORY

    def gain_name(self, name: str) -> None:
        """
        Set field name.

        :param name:
            Name of the field as it appears in a class definition

        Method called at most once on each Field instance embedded in a
        :class:`POD` subclass. This method informs the field of the name it was
        assigned to in the class.
        """
        self.name = name
        self.instance_attr = "_{}".format(name)
        self.signal_name = "on_{}_changed".format(name)

    def alter_cls(self, cls: type) -> None:
        """
        Modify class definition this field belongs to.

        This method is called during class construction. It allows the field to
        alter the class and add the on_{field.name}_changed signal. The signal
        is only added if notification is enabled *and* if there is no such
        signal in the first place (this allows inheritance not to create
        separate but identically-named signals and allows signal handlers
        connected via the base class to work on child classes.
        """
        if not self.notify:
            return
        assert self.signal_name is not None
        if not hasattr(cls, self.signal_name):
            signal_def = morris.signal(
                self.notify_fn if self.notify_fn is not None
                else self.on_changed,
                signal_name='{}.{}'.format(cls.__name__, self.signal_name))
            setattr(cls, self.signal_name, signal_def)

    def __get__(self, instance: object, owner: type) -> "Any":
        """
        Get field value from an object or from a class.

        This method is part of the Python descriptor protocol.
        """
        if instance is None:
            return self
        else:
            return getattr(instance, self.instance_attr)

    def __set__(self, instance: object, new_value: "Any") -> None:
        """
        Set field value from on an object.

        This method is part of the Python descriptor protocol.

        Assignments respect the assign filter chain, that is, the new value is
        being pushed through the chain of callbacks (each has a chance to alter
        the value) until it is finally assigned. Any of the callbacks can raise
        an exception and abort the setting process.

        This can be used to implement simple type checking, value checking or
        even type and value conversions.
        """
        if self.assign_filter_list is not None or self.notify:
            old_value = getattr(instance, self.instance_attr, UNSET)
        # Run the value through assign filters
        if self.assign_filter_list is not None:
            for assign_filter in self.assign_filter_list:
                new_value = assign_filter(instance, self, old_value, new_value)
        # Do value modification check if change notification is enabled
        if self.notify and hasattr(instance, self.instance_attr):
            if new_value != old_value:
                setattr(instance, self.instance_attr, new_value)
                on_field_change = getattr(instance, self.signal_name)
                on_field_change(old_value, new_value)
        else:
            # Or just fire away
            setattr(instance, self.instance_attr, new_value)

    def on_changed(self, pod: "POD", old: "Any", new: "Any") -> None:
        """
        The first responder of the per-field modification signal.

        :param pod:
            The object that contains the modified values
        :param old:
            The old value of the field
        :param new:
            The new value of the field
        """
        _logger.debug("<%s %s>.%s(%r, %r)", pod.__class__.__name__, id(pod),
                      self.signal_name, old, new)


@total_ordering
class PODBase:

    """Base class for POD-like classes."""

    field_list = []
    namedtuple_cls = namedtuple('PODBase', '')

    def __init__(self, *args, **kwargs):
        """
        Initialize a new POD object.

        Positional arguments bind to fields in declaration order. Keyword
        arguments bind to fields in any order but fields cannot be initialized
        twice.

        :raises TypeError:
            If there are more positional arguments than fields to initialize
        :raises TypeError:
            If a keyword argument doesn't correspond to a field name.
        :raises TypeError:
            If a field is initialized twice (first with positional arguments,
            then again with keyword arguments).
        :raises TypeError:
            If a ``MANDATORY`` field is not initialized.
        """
        field_list = self.__class__.field_list
        # Set all of the instance attributes to the special UNSET value, this
        # is useful if something fails and the object is inspected somehow.
        # Then all the attributes will be still UNSET.
        for field in field_list:
            setattr(self, field.instance_attr, UNSET)
        # Check if the number of positional arguments is correct
        if len(args) > len(field_list):
            raise TypeError("too many arguments")
        # Initialize mandatory fields using positional arguments
        for field, field_value in zip(field_list, args):
            setattr(self, field.name, field_value)
        # Initialize fields using keyword arguments
        for field_name, field_value in kwargs.items():
            field = getattr(self.__class__, field_name, None)
            if not isinstance(field, Field):
                raise TypeError("no such field: {}".format(field_name))
            if getattr(self, field.instance_attr) is not UNSET:
                raise TypeError(
                    "field initialized twice: {}".format(field_name))
            setattr(self, field_name, field_value)
        # Initialize remaining fields using their default initializers
        for field in field_list:
            if getattr(self, field.instance_attr) is not UNSET:
                continue
            if field.is_mandatory:
                raise TypeError(
                    "mandatory argument missing: {}".format(field.name))
            if field.initial_fn is not None:
                field_value = field.initial_fn()
            else:
                field_value = field.initial
            setattr(self, field.name, field_value)

    def __repr__(self):
        """Get a debugging representation of a POD object."""
        return "{}({})".format(
            self.__class__.__name__,
            ', '.join([
                '{}={!r}'.format(field.name, getattr(self, field.name))
                for field in self.__class__.field_list]))

    def __eq__(self, other: "POD") -> bool:
        """
        Check that this POD is equal to another POD.

        POD comparison is implemented by converting them to tuples and
        comparing the two tuples.
        """
        if not isinstance(other, POD):
            return NotImplemented
        return self.as_tuple() == other.as_tuple()

    def __lt__(self, other: "POD") -> bool:
        """
        Check that this POD is "less" than an another POD.

        POD comparison is implemented by converting them to tuples and
        comparing the two tuples.
        """
        if not isinstance(other, POD):
            return NotImplemented
        return self.as_tuple() < other.as_tuple()

    def as_tuple(self) -> tuple:
        """
        Return the data in this POD as a tuple.

        Order of elements in the tuple corresponds to the order of field
        declarations.
        """
        return self.__class__.namedtuple_cls(*[
            getattr(self, field.name)
            for field in self.__class__.field_list
        ])

    def as_dict(self) -> dict:
        """
        Return the data in this POD as a dictionary.

        .. note::
            UNSET values are not added to the dictionary.
        """
        return {
            field.name: getattr(self, field.name)
            for field in self.__class__.field_list
            if getattr(self, field.name) is not UNSET
        }


class _FieldCollection:

    """
    Support class for constructing POD meta-data information.

    Helper class that simplifies :class:`PODMeta` code that harvests
    :class:`Field` instances during class construction. Looking at the
    namespace and a list of base classes come up with a list of Field objects
    that belong to the given POD.

    :attr field_list:
        A list of :class:`Field` instances
    :attr field_origin_map:
        A dictionary mapping from field name to the *name* of the class that
        defines it.
    """

    def __init__(self):
        self.field_list = []
        self.field_origin_map = {}  # field name -> defining class name

    def inspect_cls_for_decorator(self, cls: type) -> None:
        """Analyze a bare POD class."""
        self.inspect_base_classes(cls.__bases__)
        self.inspect_namespace(cls.__dict__, cls.__name__)

    def inspect_base_classes(self, base_cls_list: "List[type]") -> None:
        """
        Analyze base classes of a POD class.

        Analyze a list of base classes and check if they have consistent
        fields.  All analyzed fields are added to the internal data structures.

        :param base_cls_list:
            A list of classes to inspect. Only subclasses of POD are inspected.
        """
        for base_cls in base_cls_list:
            if not issubclass(base_cls, PODBase):
                continue
            base_cls_name = base_cls.__name__
            for field in base_cls.field_list:
                self.add_field(field, base_cls_name)

    def inspect_namespace(self, namespace: dict, cls_name: str) -> None:
        """
        Analyze namespace of a POD class.

        Analyze a namespace of a newly (being formed) class and check if it has
        consistent fields. All analyzed fields are added to the internal data
        structures.

        .. note::
            This method calls :meth:`Field.gain_name()` on all fields it finds.
        """
        fields = []
        for field_name, field in namespace.items():
            if not isinstance(field, Field):
                continue
            field.gain_name(field_name)
            fields.append(field)
        fields.sort(key=lambda field: field.counter)
        for field in fields:
            self.add_field(field, cls_name)

    def get_namedtuple_cls(self, name: str) -> type:
        """
        Create a new namedtuple that corresponds to the fields seen so far.

        :parm name:
            Name of the namedtuple class
        :returns:
            A new namedtuple class
        """
        return namedtuple(name, [field.name for field in self.field_list])

    def add_field(self, field: Field, base_cls_name: str) -> None:
        """
        Add a field to the collection.

        :param field:
            A :class:`Field` instance
        :param base_cls_name:
            The name of the class that defines the field
        :raises TypeError:
            If any of the base classes have overlapping fields.
        """
        assert field.name is not None
        field_name = field.name
        if field_name not in self.field_origin_map:
            self.field_origin_map[field_name] = base_cls_name
            self.field_list.append(field)
        else:
            raise TypeError("field {1}.{0} clashes with {2}.{0}".format(
                field_name, base_cls_name, self.field_origin_map[field_name]))


class PODMeta(type):

    """
    Meta-class for all POD classes.

    This meta-class is responsible for correctly handling field inheritance.
    This class sets up ``field_list`` and ``namedtuple_cls`` attributes on the
    newly-created class.
    """

    def __new__(mcls, name, bases, namespace):
        fc = _FieldCollection()
        fc.inspect_base_classes(bases)
        fc.inspect_namespace(namespace, name)
        namespace['field_list'] = fc.field_list
        namespace['namedtuple_cls'] = fc.get_namedtuple_cls(name)
        cls = super().__new__(mcls, name, bases, namespace)
        for field in fc.field_list:
            field.alter_cls(cls)
        return cls

    @classmethod
    def __prepare__(mcls, name, bases, **kwargs):
        """
        Get a namespace for defining new POD classes.

        Prepare the namespace for the definition of a class using PODMeta as a
        meta-class. Since we want to observe the order of fields, using an
        OrderedDict makes that task trivial.
        """
        return OrderedDict()


def podify(cls):
    """
    Decorator for POD classes.

    The decorator offers an alternative from using the POD class (with the
    PODMeta meta-class). Instead of using that, one can use the ``@podify``
    decorator on a PODBase-derived class.
    """
    if not isinstance(cls, type) or not issubclass(cls, PODBase):
        raise TypeError("cls must be a subclass of PODBase")
    fc = _FieldCollection()
    fc.inspect_cls_for_decorator(cls)
    cls.field_list = fc.field_list
    cls.namedtuple_cls = fc.get_namedtuple_cls(cls.__name__)
    for field in fc.field_list:
        field.alter_cls(cls)
    return cls


@total_ordering
class POD(PODBase, metaclass=PODMeta):

    """
    Base class that removes boilerplate from plain-old-data classes.

    Use POD as your base class and define :class:`Field` objects inside.  Don't
    define any __init__() (unless you really, really have to have one) and
    instead set appropriate attributes on the initializer of a particular field
    object.

    What you get for *free* is, all the properties (for each field),
    documentation, initializer, comparison methods (PODs have total ordering)
    and the __repr__() method.

    There are some additional methods, such as :meth:`as_tuple()` and
    :meth:`as_dict()` that may be of use in some circumstances.

    All fields in a single POD subclass are collected (including all of the
    fields in the parent classes) and arranged in a list. That list is
    available as ``POD.field_list``.

    In addition each POD class has an unique named tuple that corresponds to
    each field stored inside the POD, the named tuple is available as
    ``POD.namedtuple_cls``. The return value of :meth:`as_tuple()` actually
    uses that type.
    """


def modify_field_docstring(field_docstring_ext: str):
    """
    Decorator for altering field docstrings via assign filter functions.

    A decorator for assign filter functions that allows them to declaratively
    modify the docstring of the field they are used on.

    :param field_docstring_ext:
        A string compatible with python's str.format() method. The string
        should be one line long (newlines will look odd) and may reference any
        of the field attributes, as exposed by the {field} named format
        attribute.

    Example:

        >>> @modify_field_docstring("not even")
        ... def not_even(instance, field, old, new):
        ...     if new % 2 == 0:
        ...         raise ValueError("value cannot be even")
        ...     return new
    """
    def decorator(fn):
        fn.field_docstring_ext = field_docstring_ext
        return fn
    return decorator


@modify_field_docstring("constant (read-only after initialization)")
def read_only_assign_filter(
        instance: POD, field: Field, old: "Any", new: "Any") -> "Any":
    """
    An assign filter that makes a field read-only.

    The field can be only assigned if the old value is ``UNSET``, that is,
    during the initial construction of a POD object.

    :param instance:
        A subclass of :class:`POD` that contains ``field``
    :param field:
        The :class:`Field` being assigned to
    :param old:
        The current value of the field
    :param new:
        The proposed value of the field
    :returns:
        ``new``, as-is
    :raises AttributeError:
        if ``old`` is anything but the special object ``UNSET``
    """
    if old is UNSET:
        return new
    raise AttributeError(_(
        "{}.{} is read-only"
    ).format(instance.__class__.__name__, field.name))


const = read_only_assign_filter


@modify_field_docstring(
    "type-converted (value must be convertible to {field.type.__name__})")
def type_convert_assign_filter(
        instance: POD, field: Field, old: "Any", new: "Any") -> "Any":
    """
    An assign filter that converts the value to the field type.

    The field must have a valid python type object stored in the .type field.

    :param instance:
        A subclass of :class:`POD` that contains ``field``
    :param field:
        The :class:`Field` being assigned to
    :param old:
        The current value of the field
    :param new:
        The proposed value of the field
    :returns:
        ``new`` type-converted to ``field.type``.
    :raises ValueError:
        if ``new`` cannot be converted to ``field.type``
    """
    return field.type(new)


@modify_field_docstring(
    "type-checked (value must be of type {field.type.__name__})")
def type_check_assign_filter(
        instance: POD, field: Field, old: "Any", new: "Any") -> "Any":
    """
    An assign filter that type-checks the value according to the field type.

    The field must have a valid python type object stored in the .type field.

    :param instance:
        A subclass of :class:`POD` that contains ``field``
    :param field:
        The :class:`Field` being assigned to
    :param old:
        The current value of the field
    :param new:
        The proposed value of the field
    :returns:
        ``new``, as-is
    :raises TypeError:
        if ``new`` is not an instance of ``field.type``
    """
    if isinstance(new, field.type):
        return new
    raise TypeError("{}.{} requires objects of type {}".format(
        instance.__class__.__name__, field.name, field.type.__name__))


typed = type_check_assign_filter


@modify_field_docstring(
    "unset or type-checked (value must be of type {field.type.__name__})")
def unset_or_type_check_assign_filter(
        instance: POD, field: Field, old: "Any", new: "Any") -> "Any":
    """
    An assign filter that type-checks the value according to the field type.

    .. note::
        This filter allows (passes through) the special ``UNSET`` value as-is.

    The field must have a valid python type object stored in the .type field.

    :param instance:
        A subclass of :class:`POD` that contains ``field``
    :param field:
        The :class:`Field` being assigned to
    :param old:
        The current value of the field
    :param new:
        The proposed value of the field
    :returns:
        ``new``, as-is
    :raises TypeError:
        if ``new`` is not an instance of ``field.type``
    """
    if new is UNSET:
        return new
    return type_check_assign_filter(instance, field, old, new)


unset_or_typed = unset_or_type_check_assign_filter


class sequence_type_check_assign_filter:

    """
    Assign filter for typed sequences.

    An assign filter for typed sequences (lists or tuples) that must contain an
    object of the given type.
    """

    def __init__(self, item_type: type):
        """
        Initialize the assign filter with the given sequence item type.

        :param item_type:
            Desired type of each sequence item.
        """
        self.item_type = item_type

    @property
    def field_docstring_ext(self) -> str:
        return "type-checked sequence (items must be of type {})".format(
            self.item_type.__name__)

    def __call__(
            self, instance: POD, field: Field, old: "Any", new: "Any"
    ) -> "Any":
        """
        An assign filter that type-checks the value of all sequence elements.

        :param instance:
            A subclass of :class:`POD` that contains ``field``
        :param field:
            The :class:`Field` being assigned to
        :param old:
            The current value of the field
        :param new:
            The proposed value of the field
        :returns:
            ``new``, as-is
        :raises TypeError:
            if ``new`` is not an instance of ``field.type``
        """
        for item in new:
            if not isinstance(item, self.item_type):
                raise TypeError(
                    "{}.{} requires all sequence elements of type {}".format(
                        instance.__class__.__name__, field.name,
                        self.item_type.__name__))
        return new


typed.sequence = sequence_type_check_assign_filter


class unset_or_sequence_type_check_assign_filter(typed.sequence):

    """
    Assign filter for typed sequences.

    .. note::
        This filter allows (passes through) the special ``UNSET`` value as-is.

    An assign filter for typed sequences (lists or tuples) that must contain an
    object of the given type.
    """

    @property
    def field_docstring_ext(self) -> str:
        return (
            "unset or type-checked sequence (items must be of type {})"
        ).format(self.item_type.__name__)

    def __call__(
            self, instance: POD, field: Field, old: "Any", new: "Any"
    ) -> "Any":
        """
        An assign filter that type-checks the value of all sequence elements.

        .. note::
            This filter allows (passes through) the special ``UNSET`` value
            as-is.

        :param instance:
            A subclass of :class:`POD` that contains ``field``
        :param field:
            The :class:`Field` being assigned to
        :param old:
            The current value of the field
        :param new:
            The proposed value of the field
        :returns:
            ``new``, as-is
        :raises TypeError:
            if ``new`` is not an instance of ``field.type``
        """
        if new is UNSET:
            return new
        return super().__call__(instance, field, old, new)


unset_or_typed.sequence = unset_or_sequence_type_check_assign_filter


@modify_field_docstring("unique elements (sequence elements cannot repeat)")
def unique_elements_assign_filter(
        instance: POD, field: Field, old: "Any", new: "Any") -> "Any":
    """
    An assign filter that ensures a sequence has non-repeating items.

    :param instance:
        A subclass of :class:`POD` that contains ``field``
    :param field:
        The :class:`Field` being assigned to
    :param old:
        The current value of the field
    :param new:
        The proposed value of the field
    :returns:
        ``new``, as-is
    :raises ValueError:
        if ``new`` contains any duplicates
    """
    seen = set()
    for item in new:
        if new in seen:
            raise ValueError("Duplicate element: {!r}".format(item))
        seen.add(item)
    return new

unique = unique_elements_assign_filter
