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
:mod:`plainbox.impl.dbus_ex.service` -- DBus Service Extensions
===============================================================
"""

import logging
import threading
import weakref

from plainbox.impl.signal import Signal
import _dbus_bindings
import dbus
import dbus.exceptions
import dbus.service

from checkbox_ng.dbus_ex import INTROSPECTABLE_IFACE
from checkbox_ng.dbus_ex import OBJECT_MANAGER_IFACE
from checkbox_ng.dbus_ex import PROPERTIES_IFACE
# Note: use our own version of the decorators because
# vanilla versions choke on annotations
from checkbox_ng.dbus_ex.decorators import method, signal


# This is the good old standard python property decorator
_property = property

__all__ = [
    'Interface',
    'Object',
    'method',
    'property',
    'signal',
]

logger = logging.getLogger("checkbox.ng.dbus_ex")


class InterfaceType(dbus.service.InterfaceType):
    """
    Subclass of :class:`dbus.service.InterfaceType` that also handles
    properties.
    """

    def _reflect_on_property(cls, func):
        reflection_data = (
            '    <property name="{}" type="{}" access="{}"/>\n').format(
                func._dbus_property, func._signature,
                func.dbus_access_flag)
        return reflection_data


#Subclass of :class:`dbus.service.Interface` that also handles properties
Interface = InterfaceType('Interface', (dbus.service.Interface,), {})


class property:
    """
    property that handles DBus stuff
    """

    def __init__(self, signature, dbus_interface, dbus_property=None,
                 setter=False):
        """
        Initialize new dbus_property with the given interface name.

        If dbus_property is not specified it is set to the name of the
        decorated method. In special circumstances you may wish to specify
        alternate dbus property name explicitly.

        If setter is set to True then the implicit decorated function is a
        setter, not the default getter. This allows to define write-only
        properties.
        """
        self.__name__ = None
        self.__doc__ = None
        self._signature = signature
        self._dbus_interface = dbus_interface
        self._dbus_property = dbus_property
        self._getf = None
        self._setf = None
        self._implicit_setter = setter

    def __repr__(self):
        return "<dbus.service.property {!r}>".format(self.__name__)

    @_property
    def dbus_access_flag(self):
        """
        access flag of this DBus property

        :returns: either "readwrite", "read" or "write"
        :raises TypeError: if the property is ill-defined
        """
        if self._getf and self._setf:
            return "readwrite"
        elif self._getf:
            return "read"
        elif self._setf:
            return "write"
        else:
            raise TypeError(
                "property provides neither readable nor writable")

    @_property
    def dbus_interface(self):
        """
        name of the DBus interface of this DBus property
        """
        return self._dbus_interface

    @_property
    def dbus_property(self):
        """
        name of this DBus property
        """
        return self._dbus_property

    @_property
    def signature(self):
        """
        signature of this DBus property
        """
        return self._signature

    @_property
    def setter(self):
        """
        decorator for setter functions

        This property can be used to decorate additional method that
        will be used as a property setter. Otherwise properties cannot
        be assigned.
        """
        def decorator(func):
            self._setf = func
            return self
        return decorator

    @_property
    def getter(self):
        """
        decorator for getter functions

        This property can be used to decorate additional method that
        will be used as a property getter. It is only provider for parity
        as by default, the @dbus.service.property() decorator designates
        a getter function. This behavior can be controlled by passing
        setter=True to the property initializer.
        """
        def decorator(func):
            self._getf = func
            return self
        return decorator

    def __call__(self, func):
        """
        Decorate a getter function and return the property object

        This method sets __name__, __doc__ and _dbus_property.
        """
        self.__name__ = func.__name__
        if self.__doc__ is None:
            self.__doc__ = func.__doc__
        if self._dbus_property is None:
            self._dbus_property = func.__name__
        if self._implicit_setter:
            return self.setter(func)
        else:
            return self.getter(func)

    def __get__(self, instance, owner):
        if instance is None:
            return self
        else:
            if self._getf is None:
                raise dbus.exceptions.DBusException(
                    "property is not readable")
            return self._getf(instance)

    def __set__(self, instance, value):
        if self._setf is None:
            raise dbus.exceptions.DBusException(
                "property is not writable")
        self._setf(instance, value)

    # This little helper is here is to help :meth:`Object.Introspect()`
    # figure out how to handle properties.
    _dbus_is_property = True


class Object(Interface, dbus.service.Object):
    """
    dbus.service.Object subclass that providers additional features.

    This class providers the following additional features:

    * Implementation of the PROPERTIES_IFACE. This includes the methods
      Get(), Set(), GetAll() and the signal PropertiesChanged()

    * Implementation of the OBJECT_MANAGER_IFACE. This includes the method
      GetManagedObjects() and signals InterfacesAdded() and
      InterfacesRemoved().

    * Tracking of object-path-to-object association using the new
      :meth:`find_object_by_path()` method

    * Selective activation of any of the above interfaces using
      :meth:`should_expose_interface()` method.

    * Improved version of the INTROSPECTABLE_IFACE that understands properties
    """

    def __init__(self, conn=None, object_path=None, bus_name=None):
        dbus.service.Object.__init__(self, conn, object_path, bus_name)
        self._managed_object_list = []

    # [ Public DBus methods of the INTROSPECTABLE_IFACE interface ]

    @method(
        dbus_interface=INTROSPECTABLE_IFACE,
        in_signature='', out_signature='s',
        path_keyword='object_path', connection_keyword='connection')
    def Introspect(self, object_path, connection):
        """
        Return a string of XML encoding this object's supported interfaces,
        methods and signals.
        """
        logger.debug("Introspect(object_path=%r)", object_path)
        reflection_data = (
            _dbus_bindings.DBUS_INTROSPECT_1_0_XML_DOCTYPE_DECL_NODE)
        reflection_data += '<node name="%s">\n' % object_path
        interfaces = self._dct_entry
        for (name, funcs) in interfaces.items():
            # Allow classes to ignore certain interfaces This is useful because
            # this class implements all kinds of methods internally (for
            # simplicity) but does not really advertise them all directly
            # unless asked to.
            if not self.should_expose_interface(name):
                continue
            reflection_data += '  <interface name="%s">\n' % (name)
            for func in funcs.values():
                if getattr(func, '_dbus_is_method', False):
                    reflection_data += self.__class__._reflect_on_method(func)
                elif getattr(func, '_dbus_is_signal', False):
                    reflection_data += self.__class__._reflect_on_signal(func)
                elif getattr(func, '_dbus_is_property', False):
                    reflection_data += (
                        self.__class__._reflect_on_property(func))
            reflection_data += '  </interface>\n'
        for name in connection.list_exported_child_objects(object_path):
            reflection_data += '  <node name="%s"/>\n' % name
        reflection_data += '</node>\n'
        logger.debug("Introspect() returns: %s", reflection_data)
        return reflection_data

    # [ Public DBus methods of the PROPERTIES_IFACE interface ]

    @dbus.service.method(
        dbus_interface=dbus.PROPERTIES_IFACE,
        in_signature="ss", out_signature="v")
    def Get(self, interface_name, property_name):
        """
        Get the value of a property @property_name on interface
        @interface_name.
        """
        logger.debug(
            "%r.Get(%r, %r) -> ...",
            self, interface_name, property_name)
        try:
            props = self._dct_entry[interface_name]
        except KeyError:
            raise dbus.exceptions.DBusException(
                dbus.PROPERTIES_IFACE,
                "No such interface {}".format(interface_name))
        try:
            prop = props[property_name]
        except KeyError:
            raise dbus.exceptions.DBusException(
                dbus.PROPERTIES_IFACE,
                "No such property {}:{}".format(
                    interface_name, property_name))
        try:
            value = prop.__get__(self, self.__class__)
        except dbus.exceptions.DBusException as exc:
            logger.error(
                "%r.Get(%r, %r) -> (exception) %r",
                self, interface_name, property_name, exc)
            raise
        except Exception as exc:
            logger.exception(
                "runaway exception from Get(%r, %r)",
                interface_name, property_name)
            raise dbus.exceptions.DBusException(
                dbus.PROPERTIES_IFACE,
                "Unable to get property interface/property {}:{}: {!r}".format(
                    interface_name, property_name, exc))
        else:
            logger.debug(
                "%r.Get(%r, %r) -> %r",
                self, interface_name, property_name, value)
            return value

    @dbus.service.method(
        dbus_interface=dbus.PROPERTIES_IFACE,
        in_signature="ssv", out_signature="")
    def Set(self, interface_name, property_name, value):
        logger.debug(
            "%r.Set(%r, %r, %r) -> ...",
            self, interface_name, property_name, value)
        try:
            props = self._dct_entry[interface_name]
        except KeyError:
            raise dbus.exceptions.DBusException(
                dbus.PROPERTIES_IFACE,
                "No such interface {}".format(interface_name))
        try:
            # Map the real property name
            prop = {
                prop.dbus_property: prop
                for prop in props.values()
                if isinstance(prop, property)
            }[property_name]
            if not isinstance(prop, property):
                raise KeyError(property_name)
        except KeyError:
            raise dbus.exceptions.DBusException(
                dbus.PROPERTIES_IFACE,
                "No such property {}:{}".format(
                    interface_name, property_name))
        try:
            prop.__set__(self, value)
        except dbus.exceptions.DBusException:
            raise
        except Exception as exc:
            logger.exception(
                "runaway exception from %r.Set(%r, %r, %r)",
                self, interface_name, property_name, value)
            raise dbus.exceptions.DBusException(
                dbus.PROPERTIES_IFACE,
                "Unable to set property {}:{}: {!r}".format(
                    interface_name, property_name, exc))
        logger.debug(
            "%r.Set(%r, %r, %r) -> None",
            self, interface_name, property_name, value)

    @dbus.service.method(
        dbus_interface=dbus.PROPERTIES_IFACE,
        in_signature="s", out_signature="a{sv}")
    def GetAll(self, interface_name):
        logger.debug("%r.GetAll(%r)", self, interface_name)
        try:
            props = self._dct_entry[interface_name]
        except KeyError:
            raise dbus.exceptions.DBusException(
                dbus.PROPERTIES_IFACE,
                "No such interface {}".format(interface_name))
        result = {}
        for prop in props.values():
            if not isinstance(prop, property):
                continue
            prop_name = prop.dbus_property
            try:
                prop_value = prop.__get__(self, self.__class__)
            except:
                logger.exception(
                    "Unable to read property %r from %r", prop, self)
            else:
                result[prop_name] = prop_value
        return result

    @dbus.service.signal(
        dbus_interface=dbus.PROPERTIES_IFACE,
        signature='sa{sv}as')
    def PropertiesChanged(
            self, interface_name, changed_properties, invalidated_properties):
        logger.debug(
            "PropertiesChanged(%r, %r, %r)",
            interface_name, changed_properties, invalidated_properties)

    # [ Public DBus methods of the OBJECT_MANAGER_IFACE interface ]

    @dbus.service.method(
        dbus_interface=OBJECT_MANAGER_IFACE,
        in_signature="", out_signature="a{oa{sa{sv}}}")
    def GetManagedObjects(self):
        logger.debug("%r.GetManagedObjects() -> ...", self)
        result = {}
        for obj in self._managed_object_list:
            logger.debug("Looking for stuff exported by %r", obj)
            result[obj] = {}
            for iface_name in obj._dct_entry.keys():
                props = obj.GetAll(iface_name)
                if len(props):
                    result[obj][iface_name] = props
        logger.debug("%r.GetManagedObjects() -> %r", self, result)
        return result

    @dbus.service.signal(
        dbus_interface=OBJECT_MANAGER_IFACE,
        signature='oa{sa{sv}}')
    def InterfacesAdded(self, object_path, interfaces_and_properties):
        logger.debug("%r.InterfacesAdded(%r, %r)",
                     self, object_path, interfaces_and_properties)

    @dbus.service.signal(
        dbus_interface=OBJECT_MANAGER_IFACE, signature='oas')
    def InterfacesRemoved(self, object_path, interfaces):
        logger.debug("%r.InterfacesRemoved(%r, %r)",
                     self, object_path, interfaces)

    # [ Overridden methods of dbus.service.Object ]

    def add_to_connection(self, connection, path):
        """
        Version of dbus.service.Object.add_to_connection() that keeps track of
        all object paths.
        """
        with self._object_path_map_lock:
            # Super-call add_to_connection(). This can fail which is
            # okay as we haven't really modified anything yet.
            super(Object, self).add_to_connection(connection, path)
            # Touch self.connection, this will fail if the call above failed
            # and self._connection (mind the leading underscore) is still None.
            # It will also fail if the object is being exposed on multiple
            # connections (so self._connection is _MANY). We are interested in
            # the second check as _MANY connections are not supported here.
            self.connection
            # If everything is okay, just add the specified path to the
            # _object_path_to_object_map.
            self._object_path_to_object_map[path] = self

    def remove_from_connection(self, connection=None, path=None):
        with self._object_path_map_lock:
            # Touch self.connection, this triggers a number of interesting
            # checks, in particular checks for self._connection (mind the
            # leading underscore) being _MANY or being None. Both of those
            # throw an AttributeError that we can simply propagate at this
            # point.
            self.connection
            # Create a copy of locations. This is required because locations
            # are modified by remove_from_connection() which can also fail.  If
            # we were to use self.locations here directly we would have to undo
            # any changes if remove_from_connection() raises an exception.
            # Instead it is easier to first super-call remove_from_connection()
            # and then do what we need to at this layer, after
            # remove_from_connection() finishes successfully.
            locations_copy = list(self.locations)
            # Super-call remove_from_connection()
            super(Object, self).remove_from_connection(connection, path)
            # If either path or connection are none then treat them like
            # match-any wild-cards. The same logic is implemented in the
            # superclass version of this method.
            if path is None or connection is None:
                # Location is a tuple of at least two elements, connection and
                # path. There may be other elements added later so let's not
                # assume this is a simple pair.
                for location in locations_copy:
                    location_conn = location[0]
                    location_path = location[1]
                    # If (connection matches or is None)
                    # and (path matches or is None)
                    # then remove that association
                    if ((location_conn == connection or connection is None)
                            and (path == location_path or path is None)):
                        del self._object_path_to_object_map[location_path]
            else:
                # If connection and path were specified, just remove the
                # association from the specified path.
                del self._object_path_to_object_map[path]

    # [ Custom Extension Methods ]

    def should_expose_interface(self, iface_name):
        """
        Check if the specified interface should be exposed.

        This method controls which of the interfaces are visible as implemented
        by this Object. By default objects don't implement any interface expect
        for PEER_IFACE. There are two more interfaces that are implemented
        internally but need to be explicitly exposed: the PROPERTIES_IFACE and
        OBJECT_MANAGER_IFACE.

        Typically subclasses should NOT override this method, instead
        subclasses should define class-scope HIDDEN_INTERFACES as a
        frozenset() of classes to hide and remove one of the entries found in
        _STD_INTERFACES from it to effectively enable that interface.
        """
        return iface_name not in self.HIDDEN_INTERFACES

    @classmethod
    def find_object_by_path(cls, object_path):
        """
        Find and return the object that is exposed as object_path on any
        connection. Using multiple connections is not supported at this time.

        .. note::
            This obviously only works for objects exposed from the same
            application. The main use case is to have a way to lookup object
            paths that may be passed as arguments and also originate in the
            same application.
        """
        # XXX: ideally this would be per-connection method.
        with cls._object_path_map_lock:
            return cls._object_path_to_object_map[object_path]

    @_property
    def managed_objects(self):
        """
        list of of managed objects.

        This collection is a part of the OBJECT_MANAGER_IFACE. While it can be
        manipulated directly (technically) it should only be manipulated using
        :meth:`add_managed_object()`, :meth:`add_manage_object_list()`,
        :meth:`remove_managed_object()` and
        :meth:`remove_managed_object_list()` as they send appropriate DBus
        signals.
        """
        return self._managed_object_list

    def add_managed_object(self, obj):
        self.add_managed_object_list([obj])

    def remove_managed_object(self, obj):
        self.remove_managed_object_list([obj])

    def add_managed_object_list(self, obj_list):
        logger.debug("Adding managed objects: %s", obj_list)
        for obj in obj_list:
            if not isinstance(obj, Object):
                raise TypeError("obj must be of type {!r}".format(Object))
        old = self._managed_object_list
        new = list(old)
        new.extend(obj_list)
        self._managed_object_list = new
        self._on_managed_objects_changed(old, new)

    def remove_managed_object_list(self, obj_list):
        logger.debug("Removing managed objects: %s", obj_list)
        for obj in obj_list:
            if not isinstance(obj, Object):
                raise TypeError("obj must be of type {!r}".format(Object))
        old = self._managed_object_list
        new = list(old)
        for obj in obj_list:
            new.remove(obj)
        self._managed_object_list = new
        self._on_managed_objects_changed(old, new)

    # [ Custom Private Implementation Data ]

    _STD_INTERFACES = frozenset([
        INTROSPECTABLE_IFACE,
        OBJECT_MANAGER_IFACE,
        # TODO: peer interface is not implemented in this class
        # PEER_IFACE,
        PROPERTIES_IFACE
    ])

    HIDDEN_INTERFACES = frozenset([
        OBJECT_MANAGER_IFACE,
        PROPERTIES_IFACE
    ])

    # Lock protecting access to _object_path_to_object_map.
    # XXX: ideally this would be a per-connection attribute
    _object_path_map_lock = threading.Lock()

    # Map of object_path -> dbus.service.Object instances
    # XXX: ideally this would be a per-connection attribute
    _object_path_to_object_map = weakref.WeakValueDictionary()

    # [ Custom Private Implementation Methods ]

    @_property
    def _dct_key(self):
        """
        the key indexing this Object in Object.__class__._dbus_class_table
        """
        return self.__class__.__module__ + '.' + self.__class__.__name__

    @_property
    def _dct_entry(self):
        """
        same as self.__class__._dbus_class_table[self._dct_key]
        """
        return self.__class__._dbus_class_table[self._dct_key]

    @Signal.define
    def _on_managed_objects_changed(self, old_objs, new_objs):
        logger.debug("%r._on_managed_objects_changed(%r, %r)",
                     self, old_objs, new_objs)
        for obj in frozenset(new_objs) - frozenset(old_objs):
            ifaces_and_props = {}
            for iface_name in obj._dct_entry.keys():
                try:
                    props = obj.GetAll(iface_name)
                except dbus.exceptions.DBusException as exc:
                    logger.warning("Caught %r", exc)
                else:
                    ifaces_and_props[iface_name] = props
            self.InterfacesAdded(obj.__dbus_object_path__, ifaces_and_props)
        for obj in frozenset(old_objs) - frozenset(new_objs):
            ifaces = list(obj._dct_entry.keys())
            self.InterfacesRemoved(obj.__dbus_object_path__, ifaces)


class ObjectWrapper(Object):
    """
    Wrapper for a single python object which makes it easier to expose over
    DBus as a service. The object should be injected into something that
    extends dbus.service.Object class.

    The class maintains an association between each wrapper and native object
    and offers methods for converting between the two.
    """

    # Lock protecting access to _native_id_to_wrapper_map
    _native_id_map_lock = threading.Lock()

    # Man of id(wrapper.native) -> wrapper
    _native_id_to_wrapper_map = weakref.WeakValueDictionary()

    def __init__(self, native, conn=None, object_path=None, bus_name=None):
        """
        Create a new wrapper for the specified native object
        """
        super(ObjectWrapper, self).__init__(conn, object_path, bus_name)
        with self._native_id_map_lock:
            self._native_id_to_wrapper_map[id(native)] = self
        self._native = native

    @_property
    def native(self):
        """
        native python object being wrapped by this wrapper
        """
        return self._native

    @classmethod
    def find_wrapper_by_native(cls, native):
        """
        Find the wrapper associated with the specified native object
        """
        with cls._native_id_map_lock:
            return cls._native_id_to_wrapper_map[id(native)]
