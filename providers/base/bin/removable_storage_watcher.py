#!/usr/bin/env python3

import argparse
import collections
import copy
import dbus
import logging
import os
import sys
import threading

import gi
gi.require_version('GUdev', '1.0')
from gi.repository import GObject, GUdev  # noqa: E402

from checkbox_support.dbus import connect_to_system_bus         # noqa: E402
from checkbox_support.dbus.udisks2 import UDisks2Model          # noqa: E402
from checkbox_support.dbus.udisks2 import UDisks2Observer       # noqa: E402
from checkbox_support.dbus.udisks2 import is_udisks2_supported  # noqa: E402
from checkbox_support.dbus.udisks2 import lookup_udev_device    # noqa: E402
from checkbox_support.dbus.udisks2 import (                     # noqa: E402
    map_udisks1_connection_bus)  # noqa: E402
from checkbox_support.heuristics.udisks2 import is_memory_card  # noqa: E402
from checkbox_support.parsers.udevadm import CARD_READER_RE     # noqa: E402
from checkbox_support.parsers.udevadm import GENERIC_RE         # noqa: E402
from checkbox_support.parsers.udevadm import FLASH_RE           # noqa: E402
from checkbox_support.scripts.zapper_proxy import (             # noqa: E402
    zapper_run)
from checkbox_support.udev import get_interconnect_speed        # noqa: E402
from checkbox_support.udev import get_udev_block_devices        # noqa: E402

# Record representing properties of a UDisks1 Drive object needed by the
# UDisks1 version of the watcher implementation
UDisks1DriveProperties = collections.namedtuple(
    'UDisks1DriveProperties', 'file bus speed model vendor media')

# Delta record that encapsulates difference:
# delta_dir -- directon of the difference, either DELTA_DIR_PLUS or
#              DELTA_DIR_MINUS
# value -- the actual value being removed or added, either InterfaceDelta or
# PropertyDelta instance, see below
DeltaRecord = collections.namedtuple("DeltaRecord", "delta_dir value")

# Delta value for representing interface changes
InterfaceDelta = collections.namedtuple(
    "InterfaceDelta",
    "delta_type object_path iface_name")

# Delta value for representing property changes
PropertyDelta = collections.namedtuple(
    "PropertyDelta",
    "delta_type object_path iface_name prop_name prop_value")

# Tokens that encode additions and removals
DELTA_DIR_PLUS = '+'
DELTA_DIR_MINUS = '-'

# Tokens that encode interface and property deltas
DELTA_TYPE_IFACE = 'i'
DELTA_TYPE_PROP = 'p'


def format_bytes(size):
    """
    Format size to be easily read by humans

    The result is disk-size compatible (using multiples of 10
    rather than 2) string like "4.5GB"
    """
    for index, prefix in enumerate(" KMGTPEZY", 0):
        factor = 10 ** (index * 3)
        if size // factor <= 1000:
            break
    return "{}{}B".format(size // factor, prefix.strip())


class UDisks1StorageDeviceListener:

    def __init__(self, system_bus, loop, action, devices, minimum_speed,
                 memorycard):
        self._action = action
        self._devices = devices
        self._minimum_speed = minimum_speed
        self._memorycard = memorycard
        self._bus = system_bus
        self._loop = loop
        self._error = False
        self._change_cache = []

    def check(self, timeout):
        udisks = 'org.freedesktop.UDisks'
        if self._action == 'insert':
            signal = 'DeviceAdded'
            logging.debug("Adding signal listener for %s.%s", udisks, signal)
            self._bus.add_signal_receiver(self.add_detected,
                                          signal_name=signal,
                                          dbus_interface=udisks)
        elif self._action == 'remove':
            signal = 'DeviceRemoved'
            logging.debug("Adding signal listener for %s.%s", udisks, signal)
            self._bus.add_signal_receiver(self.remove_detected,
                                          signal_name=signal,
                                          dbus_interface=udisks)

        self._starting_devices = self.get_existing_devices()
        logging.debug("Starting with the following devices: %r",
                      self._starting_devices)

        def timeout_callback():
            print("%s seconds have expired "
                  "waiting for the device to be inserted." % timeout)
            self._error = True
            self._loop.quit()

        logging.debug("Adding timeout listener, timeout=%r", timeout)
        GObject.timeout_add_seconds(timeout, timeout_callback)
        logging.debug("Starting event loop...")
        self._loop.run()

        return self._error

    def verify_device_change(self, changed_devices, message=""):
        logging.debug("Verifying device change: %s", changed_devices)
        # Filter the applicable bus types, as provided on the command line
        # (values of self._devices can be 'usb', 'firewire', etc)
        desired_bus_devices = [
            device
            for device in changed_devices
            if device.bus in self._devices]
        logging.debug("Desired bus devices: %s", desired_bus_devices)
        for dev in desired_bus_devices:
            if self._memorycard:
                if (
                    dev.bus != 'sdio' and
                    not FLASH_RE.search(dev.media) and
                    not CARD_READER_RE.search(dev.model) and
                    not GENERIC_RE.search(dev.vendor)
                ):
                    logging.debug(
                        "The device does not seem to be a memory"
                        " card (bus: %r, model: %r), skipping",
                        dev.bus, dev.model)
                    return
                print(message % {'bus': 'memory card', 'file': dev.file})
            else:
                if (
                    FLASH_RE.search(dev.media) or
                    CARD_READER_RE.search(dev.model) or
                    GENERIC_RE.search(dev.vendor)
                ):
                    logging.debug("The device seems to be a memory"
                                  " card (bus: %r (model: %r), skipping",
                                  dev.bus, dev.model)
                    return
                print(message % {'bus': dev.bus, 'file': dev.file})
            if self._minimum_speed:
                if dev.speed >= self._minimum_speed:
                    print("with speed of %(speed)s bits/s "
                          "higher than %(min_speed)s bits/s" %
                          {'speed': dev.speed,
                           'min_speed': self._minimum_speed})
                else:
                    print("ERROR: speed of %(speed)s bits/s lower "
                          "than %(min_speed)s bits/s" %
                          {'speed': dev.speed,
                           'min_speed': self._minimum_speed})
                    self._error = True
            logging.debug("Device matches requirements, exiting event loop")
            self._loop.quit()

    def job_change_detected(self, devices, job_in_progress, job_id,
                            job_num_tasks, job_cur_task_id,
                            job_cur_task_percentage):
        logging.debug("UDisks1 reports a job change has been detected:"
                      " devices: %s, job_in_progress: %s, job_id: %s,"
                      " job_num_tasks: %s, job_cur_task_id: %s,"
                      " job_cur_task_percentage: %s",
                      devices, job_in_progress, job_id, job_num_tasks,
                      job_cur_task_id, job_cur_task_percentage)
        if job_id == "FilesystemMount":
            if devices in self._change_cache:
                logging.debug("Ignoring filesystem mount,"
                              " the device is present in change cache")
                return
            logging.debug("Adding devices to change cache: %r", devices)
            self._change_cache.append(devices)
            logging.debug("Starting devices were: %s", self._starting_devices)
            current_devices = self.get_existing_devices()
            logging.debug("Current devices are: %s", current_devices)
            inserted_devices = list(set(current_devices) -
                                    set(self._starting_devices))
            logging.debug("Computed inserted devices: %s", inserted_devices)
            if self._memorycard:
                message = "Expected memory card device %(file)s inserted"
            else:
                message = "Expected %(bus)s device %(file)s inserted"
            self.verify_device_change(inserted_devices, message=message)

    def add_detected(self, added_path):
        logging.debug("UDisks1 reports device has been added: %s", added_path)
        logging.debug("Resetting change_cache to []")
        self._change_cache = []
        signal_name = 'DeviceJobChanged'
        dbus_interface = 'org.freedesktop.UDisks'
        logging.debug("Adding signal listener for %s.%s",
                      dbus_interface, signal_name)
        self._bus.add_signal_receiver(self.job_change_detected,
                                      signal_name=signal_name,
                                      dbus_interface=dbus_interface)

    def remove_detected(self, removed_path):
        logging.debug("UDisks1 reports device has been removed: %s",
                      removed_path)

        logging.debug("Starting devices were: %s", self._starting_devices)
        current_devices = self.get_existing_devices()
        logging.debug("Current devices are: %s", current_devices)
        removed_devices = list(set(self._starting_devices) -
                               set(current_devices))
        logging.debug("Computed removed devices: %s", removed_devices)
        self.verify_device_change(
            removed_devices,
            message="Removable %(bus)s device %(file)s has been removed")

    def get_existing_devices(self):
        logging.debug("Getting existing devices from UDisks1")
        ud_manager_obj = self._bus.get_object("org.freedesktop.UDisks",
                                              "/org/freedesktop/UDisks")
        ud_manager = dbus.Interface(ud_manager_obj, 'org.freedesktop.UDisks')
        existing_devices = []
        for dev in ud_manager.EnumerateDevices():
            try:
                device_obj = self._bus.get_object("org.freedesktop.UDisks",
                                                  dev)
                device_props = dbus.Interface(device_obj,
                                              dbus.PROPERTIES_IFACE)
                udisks = 'org.freedesktop.UDisks.Device'
                _device_file = device_props.Get(udisks, "DeviceFile")
                _bus = device_props.Get(udisks, "DriveConnectionInterface")
                _speed = device_props.Get(udisks, "DriveConnectionSpeed")
                _parent_model = ''
                _parent_media = ''
                _parent_vendor = ''

                if device_props.Get(udisks, "DeviceIsPartition"):
                    parent_obj = self._bus.get_object(
                        "org.freedesktop.UDisks",
                        device_props.Get(udisks, "PartitionSlave"))
                    parent_props = dbus.Interface(
                        parent_obj, dbus.PROPERTIES_IFACE)
                    _parent_model = parent_props.Get(udisks, "DriveModel")
                    _parent_vendor = parent_props.Get(udisks, "DriveVendor")
                    _parent_media = parent_props.Get(udisks, "DriveMedia")

                if not device_props.Get(udisks, "DeviceIsDrive"):
                    device = UDisks1DriveProperties(
                        file=str(_device_file),
                        bus=str(_bus),
                        speed=int(_speed),
                        model=str(_parent_model),
                        vendor=str(_parent_vendor),
                        media=str(_parent_media))
                    existing_devices.append(device)

            except dbus.DBusException:
                pass

        return existing_devices


def udisks2_objects_delta(old, new):
    """
    Compute the delta between two snapshots of udisks2 objects

    The objects are encoded as {s:{s:{s:v}}} where the first dictionary maps
    from DBus object path to a dictionary that maps from interface name to a
    dictionary that finally maps from property name to property value.

    The result is a generator of DeltaRecord objects that encodes the changes:
        * the 'delta_dir' is either DELTA_DIR_PLUS or DELTA_DIR_MINUS
        * the 'value' is a tuple that differs for interfaces and properties.
          Interfaces use the format (DELTA_TYPE_IFACE, object_path, iface_name)
          while properties use the format (DELTA_TYPE_PROP, object_path,
          iface_name, prop_name, prop_value)

    Interfaces are never "changed", they are only added or removed. Properties
    can be changed and this is encoded as removal followed by an addition where
    both differ only by the 'delta_dir' and the last element of the 'value'
    tuple.
    """
    # Traverse all objects, old or new
    all_object_paths = set()
    all_object_paths |= old.keys()
    all_object_paths |= new.keys()
    for object_path in sorted(all_object_paths):
        old_object = old.get(object_path, {})
        new_object = new.get(object_path, {})
        # Traverse all interfaces of each object, old or new
        all_iface_names = set()
        all_iface_names |= old_object.keys()
        all_iface_names |= new_object.keys()
        for iface_name in sorted(all_iface_names):
            if iface_name not in old_object and iface_name in new_object:
                # Report each ADDED interface
                assert iface_name in new_object
                delta_value = InterfaceDelta(
                    DELTA_TYPE_IFACE, object_path, iface_name)
                yield DeltaRecord(DELTA_DIR_PLUS, delta_value)
                # Report all properties ADDED on that interface
                for prop_name, prop_value in new_object[iface_name].items():
                    delta_value = PropertyDelta(DELTA_TYPE_PROP, object_path,
                                                iface_name, prop_name,
                                                prop_value)
                    yield DeltaRecord(DELTA_DIR_PLUS, delta_value)
            elif iface_name not in new_object and iface_name in old_object:
                # Report each REMOVED interface
                assert iface_name in old_object
                delta_value = InterfaceDelta(
                    DELTA_TYPE_IFACE, object_path, iface_name)
                yield DeltaRecord(DELTA_DIR_MINUS, delta_value)
                # Report all properties REMOVED on that interface
                for prop_name, prop_value in old_object[iface_name].items():
                    delta_value = PropertyDelta(DELTA_TYPE_PROP, object_path,
                                                iface_name, prop_name,
                                                prop_value)
                    yield DeltaRecord(DELTA_DIR_MINUS, delta_value)
            else:
                # Analyze properties of each interface that existed both in old
                # and new object trees.
                assert iface_name in new_object
                assert iface_name in old_object
                old_props = old_object[iface_name]
                new_props = new_object[iface_name]
                all_prop_names = set()
                all_prop_names |= old_props.keys()
                all_prop_names |= new_props.keys()
                # Traverse all properties, old or new
                for prop_name in sorted(all_prop_names):
                    if prop_name not in old_props and prop_name in new_props:
                        # Report each ADDED property
                        delta_value = PropertyDelta(
                            DELTA_TYPE_PROP, object_path, iface_name,
                            prop_name, new_props[prop_name])
                        yield DeltaRecord(DELTA_DIR_PLUS, delta_value)
                    elif prop_name not in new_props and prop_name in old_props:
                        # Report each REMOVED property
                        delta_value = PropertyDelta(
                            DELTA_TYPE_PROP, object_path, iface_name,
                            prop_name, old_props[prop_name])
                        yield DeltaRecord(DELTA_DIR_MINUS, delta_value)
                    else:
                        old_value = old_props[prop_name]
                        new_value = new_props[prop_name]
                        if old_value != new_value:
                            # Report each changed property
                            yield DeltaRecord(DELTA_DIR_MINUS, PropertyDelta(
                                DELTA_TYPE_PROP, object_path, iface_name,
                                prop_name, old_value))
                            yield DeltaRecord(DELTA_DIR_PLUS, PropertyDelta(
                                DELTA_TYPE_PROP, object_path, iface_name,
                                prop_name, new_value))


class UDisks2StorageDeviceListener:
    """
    Implementation of the storage device listener concept for UDisks2 backend.
    Loosely modeled on the UDisks-based implementation above.

    Implementation details
    ^^^^^^^^^^^^^^^^^^^^^^

    The class, once configured reacts to asynchronous events from the event
    loop. Those are either DBus signals or GLib timeout.

    The timeout, if reached, terminates the test and fails with an appropriate
    end-user message. The user is expected to manipulate storage devices while
    the test is running.

    DBus signals (that correspond to UDisks2 DBus signals) cause callbacks into
    this code. Each time a signal is reported "delta" is computed and verified
    to determine if there was a successful match. The delta contains a list or
    DeltaRecord objects that encode difference (either addition or removal) and
    the value of the difference (interface name or interface property value).
    This delta is computed by udisks2_objects_delta(). The delta is then passed
    to _validate_delta() which has a chance to end the test but also prints
    diagnostic messages in verbose mode. This is very useful for understanding
    what the test actually sees occurring.

    Insertion/removal detection strategy
    ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

    Compared to initial state, the following changes objects need to be
    detected

    * At least one UDisks2 object with the following _all_ interfaces:
        * UDisks2.Partition
            (because we want a partitioned device)
        * UDisks2.Block
            (because we want that device to have a block device that users can
            format)
            - having IdUsage == 'filesystem'
            (because it should not be a piece of raid or lvm)
            - having Size > 0
            (because it should not be and empty removable storage reader)
        * UDisks2.Filesystem
            (because we want to ensure that a filesystem gets mounted)
            - having MountPoints != []
            - as a special exception this rule is REMOVED from eSATA and SATA
              devices as they are not automatically mounted anymore.

    This object must be traceable to an UDisks.Drive object:
        (because we need the medium to be inserted somewhere)
            - having ConnectionBus in (desired_connection_buses)
            - as a special exception this rule is weakened for eSATA because
              for such devices the ConnectionBus property is empty.
    """

    # Name of the DBus interface exposed UDisks2 for various drives
    UDISKS2_DRIVE_INTERFACE = "org.freedesktop.UDisks2.Drive"

    # Name of the DBus property provided by the "Drive" interface above
    UDISKS2_DRIVE_PROPERTY_CONNECTION_BUS = "ConnectionBus"

    def __init__(self, system_bus, loop, action, devices, minimum_speed,
                 memorycard, unmounted=False):
        # Store the desired minimum speed of the device in Mbit/s. The argument
        # is passed as the number of bits per second so let's fix that.
        self._desired_minimum_speed = minimum_speed / 10 ** 6
        # Compute the allowed UDisks2.Drive.ConnectionBus value based on the
        # legacy arguments passed from the command line.
        self._desired_connection_buses = set([
            map_udisks1_connection_bus(device) for device in devices])
        # Check if we are explicitly looking for memory cards
        self._desired_memory_card = memorycard
        # Store information whether we also want detected, but unmounted
        # devices too
        self._allow_unmounted = unmounted
        # Store the desired "delta" direction depending on
        # whether we test for insertion or removal
        if action == "insert":
            self._desired_delta_dir = DELTA_DIR_PLUS
        elif action == "remove":
            self._desired_delta_dir = DELTA_DIR_MINUS
        else:
            raise ValueError("Unsupported action: {}".format(action))
        # Store DBus bus object as we need to pass it to UDisks2 observer
        self._bus = system_bus
        # Store event loop object
        self._loop = loop
        # Setup UDisks2Observer class to track changes published by UDisks2
        self._udisks2_observer = UDisks2Observer()
        # Set the initial value of reference_objects.
        # The actual value is only set once in check()
        self._reference_objects = None
        # As above, just initializing in init for sake of consistency
        self._is_reference = None
        # Setup UDisks2Model to know what the current state is. This is needed
        # when remove events are reported as they don't carry enough state for
        # the program to work correctly. Since UDisks2Model only applies the
        # changes _after_ processing the signals from UDisks2Observer we can
        # reliably check all of the properties of the removed object / device.
        self._udisks2_model = UDisks2Model(self._udisks2_observer)
        # Whenever anything changes call our local change handler
        # This handler always computes the full delta (versus the
        # reference state) and decides if we have a match or not
        self._udisks2_model.on_change.connect(self._on_change)
        # We may need an udev context for checking the speed of USB devices
        self._udev_client = GUdev.Client()
        # A snapshot of udev devices, set in check()
        self._reference_udev_devices = None
        # Assume the test passes, this is changed when timeout expires or when
        # an incorrect device gets inserted.
        self._error = False

    def _dump_reference_udisks_objects(self):
        logging.debug("Reference UDisks2 objects:")
        for udisks2_object in self._reference_objects:
            logging.debug(" - %s", udisks2_object)

    def _dump_reference_udev_devices(self):
        logging.debug("Reference udev devices:")
        for udev_device in self._reference_udev_devices:
            interconnect_speed = get_interconnect_speed(udev_device)
            if interconnect_speed:
                logging.debug(" - %s (USB %dMBit/s)",
                              udev_device.get_device_file(),
                              interconnect_speed)
            else:
                logging.debug(" - %s", udev_device.get_device_file())

    def check(self, timeout):
        """
        Run the configured test and return the result

        The result is False if the test has failed.  The timeout, when
        non-zero, will make the test fail after the specified seconds have
        elapsed without conclusive result.
        """
        # Setup a timeout if requested
        if timeout > 0:
            GObject.timeout_add_seconds(timeout, self._on_timeout_expired)
        # Connect the observer to the bus. This will start giving us events
        # (actually when the loop starts later below)
        self._udisks2_observer.connect_to_bus(self._bus)
        # Get the reference snapshot of available devices
        self._reference_objects = copy.deepcopy(self._current_objects)
        self._dump_reference_udisks_objects()
        # Mark the current _reference_objects as ... reference, this is sadly
        # needed by _summarize_changes() as it sees the snapshot _after_ a
        # change has occurred and cannot determine if the slope of the 'edge'
        # of the change. It is purely needed for UI in verbose mode
        self._is_reference = True
        # A collection of objects that we gladly ignore because we already
        # reported on them being somehow inappropriate
        self._ignored_objects = set()
        # Get the reference snapshot of available udev devices
        self._reference_udev_devices = get_udev_block_devices(
            self._udev_client)
        self._dump_reference_udev_devices()
        # Start the loop and wait. The loop will exit either when:
        # 1) A proper device has been detected (either insertion or removal)
        # 2) A timeout (optional) has expired
        self._loop.run()
        # Return the outcome of the test
        return self._error

    def _on_timeout_expired(self):
        """
        Internal function called when the timer expires.

        Basically it's just here to tell the user the test failed or that the
        user was unable to alter the device during the allowed time.
        """
        print("You have failed to perform the required manipulation in time")
        # Fail the test when the timeout was reached
        self._error = True
        # Stop the loop now
        self._loop.quit()

    def _on_change(self):
        """
        Internal method called by UDisks2Model whenever a change had occurred
        """
        # Compute the changes that had occurred since the reference point
        delta_records = list(self._get_delta_records())
        # Display a summary of changes when we are done
        self._summarize_changes(delta_records)
        # If the changes are what we wanted stop the loop
        matching_devices = self._get_matching_devices(delta_records)
        if matching_devices:
            print("Expected device manipulation complete: {}".format(
                ', '.join(matching_devices)))
            # And call it a day
            self._loop.quit()

    def _get_matching_devices(self, delta_records):
        """
        Internal method called that checks if the delta records match the type
        of device manipulation we were expecting. Only called from _on_change()

        Returns a set of paths of block devices that matched
        """
        # Results
        results = set()
        # Group changes by DBus object path
        grouped_records = collections.defaultdict(list)
        for record in delta_records:
            grouped_records[record.value.object_path].append(record)
        # Create another snapshot od udev devices so that we don't do it over
        # and over in the loop below (besides, if we did that then results
        # could differ each time).
        current_udev_devices = get_udev_block_devices(self._udev_client)
        # Iterate over all UDisks2 objects and their delta records
        for object_path, records_for_object in grouped_records.items():
            # Skip objects we already ignored and complained about before
            if object_path in self._ignored_objects:
                continue
            needs = set(('block-fs', 'partition', 'non-empty'))
            if not self._allow_unmounted:
                needs.add('mounted')

            # As a special exception when the ConnectionBus is allowed to be
            # empty, as is the case with eSATA devices, do not require the
            # filesystem to be mounted as gvfs may choose not to mount it
            # automatically.
            found = set()
            drive_object_path = None
            object_block_device = None
            for record in records_for_object:
                # Skip changes opposite to the ones we need
                if record.delta_dir != self._desired_delta_dir:
                    continue
                # For devices with empty "ConnectionBus" property, don't
                # require the device to be mounted
                if (
                    record.value.iface_name ==
                    "org.freedesktop.UDisks2.Drive" and
                    record.value.delta_type == DELTA_TYPE_PROP and
                    record.value.prop_name == "ConnectionBus" and
                    record.value.prop_value == ""
                ):
                    needs.remove('mounted')
                # Detect block devices designated for filesystems
                if (
                    record.value.iface_name ==
                    "org.freedesktop.UDisks2.Block" and
                    record.value.delta_type == DELTA_TYPE_PROP and
                    record.value.prop_name == "IdUsage" and
                    record.value.prop_value == "filesystem"
                ):
                    found.add('block-fs')
                # Memorize the block device path
                elif (
                    record.value.iface_name ==
                    "org.freedesktop.UDisks2.Block" and
                    record.value.delta_type == DELTA_TYPE_PROP and
                    record.value.prop_name == "PreferredDevice"
                ):
                    object_block_device = record.value.prop_value
                # Ensure the device is a partition
                elif (record.value.iface_name ==
                      "org.freedesktop.UDisks2.Partition" and
                      record.value.delta_type == DELTA_TYPE_IFACE):
                    found.add('partition')
                # Ensure the device is not empty
                elif (record.value.iface_name ==
                      "org.freedesktop.UDisks2.Block" and
                      record.value.delta_type == DELTA_TYPE_PROP and
                      record.value.prop_name == "Size" and
                      record.value.prop_value > 0):
                    found.add('non-empty')
                # Ensure the filesystem is mounted
                elif (record.value.iface_name ==
                      "org.freedesktop.UDisks2.Filesystem" and
                      record.value.delta_type == DELTA_TYPE_PROP and
                      record.value.prop_name == "MountPoints" and
                      record.value.prop_value != []):
                    found.add('mounted')
                    # On some systems partition are reported as mounted
                    # filesystems, without 'partition' record
                    if set(['partition']).issubset(needs):
                        needs.remove('partition')
                # Finally memorize the drive the block device belongs to
                elif (record.value.iface_name ==
                      "org.freedesktop.UDisks2.Block" and
                      record.value.delta_type == DELTA_TYPE_PROP and
                      record.value.prop_name == "Drive"):
                    drive_object_path = record.value.prop_value
            logging.debug("Finished analyzing %s, found: %s, needs: %s"
                          " drive_object_path: %s", object_path, found, needs,
                          drive_object_path)
            if not needs.issubset(found) or drive_object_path is None:
                continue
            # We've found our candidate, let's look at the drive it belongs
            # to. We need to do this as some properties are associated with
            # the drive, not the filesystem/block device and the drive may
            # not have been inserted at all.
            try:
                drive_object = self._current_objects[drive_object_path]
            except KeyError:
                # The drive may be removed along with the device, let's check
                # if we originally saw it
                try:
                    drive_object = self._reference_objects[drive_object_path]
                except KeyError:
                    logging.error(
                        "A block device belongs to a drive we could not find")
                    logging.error("missing drive: %r", drive_object_path)
                    continue
            try:
                drive_props = drive_object["org.freedesktop.UDisks2.Drive"]
            except KeyError:
                logging.error(
                    "A block device belongs to an object that is not a Drive")
                logging.error("strange object: %r", drive_object_path)
                continue
            # Ensure the drive is on the appropriate bus
            connection_bus = drive_props["ConnectionBus"]
            if connection_bus not in self._desired_connection_buses:
                logging.warning("The object %r belongs to drive %r that"
                                " is attached to the bus %r but but we are"
                                " looking for one of %r so it cannot match",
                                object_block_device, drive_object_path,
                                connection_bus,
                                ", ".join(self._desired_connection_buses))
                # Ignore this object so that we don't spam the user twice
                self._ignored_objects.add(object_path)
                continue
            # Ensure it is a media card reader if this was explicitly requested
            drive_is_reader = is_memory_card(
                drive_props['Vendor'], drive_props['Model'],
                drive_props['Media'])
            if self._desired_memory_card and not drive_is_reader:
                logging.warning(
                    "The object %s belongs to drive %s that does not seem to"
                    " be a media reader", object_block_device,
                    drive_object_path)
                # Ignore this object so that we don't spam the user twice
                self._ignored_objects.add(object_path)
                continue
            # Ensure the desired minimum speed is enforced
            if self._desired_minimum_speed:
                # We need to discover the speed of the UDisks2 object that is
                # about to be matched. Sadly UDisks2 no longer supports this
                # property so we need to poke deeper and resort to udev.
                #
                # The UDisks2 object that we are interested in implements a
                # number of interfaces, most notably
                # org.freedesktop.UDisks2.Block, that has the Device property
                # holding the unix filesystem path (like /dev/sdb1). We already
                # hold a reference to that as 'object_block_device'
                #
                # We take this as a start and attempt to locate the udev Device
                # (don't confuse with UDisks2.Device, they are _not_ the same)
                # that is associated with that path.
                if self._desired_delta_dir == DELTA_DIR_PLUS:
                    # If we are looking for additions then look at _current_
                    # collection of udev devices
                    udev_devices = current_udev_devices
                    udisks2_object = self._current_objects[object_path]
                else:
                    # If we are looking for removals then look at referece
                    # collection of udev devices
                    udev_devices = self._reference_udev_devices
                    udisks2_object = self._reference_objects[object_path]
                try:
                    # Try to locate the corresponding udev device among the
                    # collection we've selected. Use the drive object as the
                    # key -- this looks for the drive, not partition objects!
                    udev_device = lookup_udev_device(udisks2_object,
                                                     udev_devices)
                except LookupError:
                    logging.error("Unable to map UDisks2 object %s to udev",
                                  object_block_device)
                    # Ignore this object so that we don't spam the user twice
                    self._ignored_objects.add(object_path)
                    continue
                interconnect_speed = get_interconnect_speed(udev_device)
                # Now that we know the speed of the interconnect we can try to
                # validate it against our desired speed.
                if interconnect_speed is None:
                    logging.warning("Unable to determine interconnect speed of"
                                    " device %s", object_block_device)
                    # Ignore this object so that we don't spam the user twice
                    self._ignored_objects.add(object_path)
                    continue
                elif interconnect_speed < self._desired_minimum_speed:
                    logging.warning(
                        "Device %s is connected via an interconnect that has"
                        " the speed of %dMbit/s but the required speed was"
                        " %dMbit/s", object_block_device, interconnect_speed,
                        self._desired_minimum_speed)
                    # Ignore this object so that we don't spam the user twice
                    self._ignored_objects.add(object_path)
                    continue
                else:
                    logging.info("Device %s is connected via an USB"
                                 " interconnect with the speed of %dMbit/s",
                                 object_block_device, interconnect_speed)
            # Yay, success
            results.add(object_block_device)
        return results

    @property
    def _current_objects(self):
        return self._udisks2_model.managed_objects

    def _get_delta_records(self):
        """
        Internal method used to compute the delta between reference devices and
        current devices. The result is a generator of DeltaRecord objects.
        """
        assert self._reference_objects is not None, "Only usable after check()"
        old = self._reference_objects
        new = self._current_objects
        return udisks2_objects_delta(old, new)

    def _summarize_changes(self, delta_records):
        """
        Internal method used to summarize changes (compared to reference state)
        called whenever _on_change() gets called. Only visible in verbose mode
        """
        # Filter out anything but interface changes
        flat_records = [record
                        for record in delta_records
                        if record.value.delta_type == DELTA_TYPE_IFACE]
        # Group changes by DBus object path
        grouped_records = collections.defaultdict(list)
        for record in flat_records:
            grouped_records[record.value.object_path].append(record)
        # Bail out quickly when nothing got changed
        if not flat_records:
            if not self._is_reference:
                logging.info("You have returned to the reference state")
                self._is_reference = True
            return
        else:
            self._is_reference = False
        # Iterate over grouped delta records for all objects
        logging.info("Compared to the reference state you have:")
        for object_path in sorted(grouped_records.keys()):
            records_for_object = sorted(
                grouped_records[object_path],
                key=lambda record: record.value.iface_name)
            # Skip any job objects as they just add noise
            if any((record.value.iface_name == "org.freedesktop.UDisks2.Job"
                    for record in records_for_object)):
                continue
            logging.info("For object %s", object_path)
            for record in records_for_object:
                # Ignore property changes for now
                if record.value.delta_type != DELTA_TYPE_IFACE:
                    continue
                # Get the name of the interface that was affected
                iface_name = record.value.iface_name
                # Get the properties for that interface (for removals get the
                # reference values, for additions get the current values)
                if record.delta_dir == DELTA_DIR_PLUS:
                    props = self._current_objects[object_path][iface_name]
                    action = "inserted"
                else:
                    props = self._reference_objects[object_path][iface_name]
                    action = "removed"
                # Display some human-readable information associated with each
                # interface change
                if iface_name == "org.freedesktop.UDisks2.Drive":
                    logging.info("\t * %s a drive", action)
                    logging.info("\t   vendor and name: %r %r",
                                 props['Vendor'], props['Model'])
                    logging.info("\t   bus: %s", props['ConnectionBus'])
                    logging.info("\t   size: %s", format_bytes(props['Size']))
                    logging.info("\t   is media card: %s", is_memory_card(
                        props['Vendor'], props['Model'], props['Media']))
                    logging.info("\t   current media: %s",
                                 props['Media'] or "???" if
                                 props['MediaAvailable'] else "N/A")
                elif iface_name == "org.freedesktop.UDisks2.Block":
                    logging.info("\t * %s block device", action)
                    logging.info("\t   from drive: %s", props['Drive'])
                    logging.info("\t   having device: %s", props['Device'])
                    logging.info("\t   having usage, type and version:"
                                 " %s %s %s", props['IdUsage'],
                                 props['IdType'], props['IdVersion'])
                    logging.info("\t   having label: %s", props['IdLabel'])
                elif iface_name == "org.freedesktop.UDisks2.PartitionTable":
                    logging.info("\t * %s partition table", action)
                    logging.info("\t   having type: %r", props['Type'])
                elif iface_name == "org.freedesktop.UDisks2.Partition":
                    logging.info("\t * %s partition", action)
                    logging.info("\t   from partition table: %s",
                                 props['Table'])
                    logging.info("\t   having size: %s",
                                 format_bytes(props['Size']))
                    logging.info("\t   having name: %r", props['Name'])
                elif iface_name == "org.freedesktop.UDisks2.Filesystem":
                    logging.info("\t * %s file system", action)
                    logging.info("\t   having mount points: %r",
                                 props['MountPoints'])


def main():
    description = "Wait for the specified device to be inserted or removed."
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument('action', choices=['insert', 'remove'])
    parser.add_argument(
        'device', choices=['usb', 'sdio', 'firewire', 'scsi',
                           'ata_serial_esata'], nargs="+")
    memorycard_help = ("Memory cards devices on bus other than sdio require "
                       "this parameter to identify them as such")
    parser.add_argument('--memorycard', action="store_true",
                        help=memorycard_help)
    parser.add_argument('--timeout', type=int, default=20)
    min_speed_help = ("Will only accept a device if its connection speed "
                      "attribute is higher than this value "
                      "(in bits/s)")
    parser.add_argument('--minimum_speed', '-m', help=min_speed_help,
                        type=int, default=0)
    parser.add_argument('--verbose', action='store_const', const=logging.INFO,
                        dest='logging_level', help="Enable verbose output")
    parser.add_argument('--debug', action='store_const', const=logging.DEBUG,
                        dest='logging_level', help="Enable debugging")
    parser.add_argument('--unmounted', action='store_true',
                        help="Don't require drive being automounted")
    parser.add_argument('--zapper-usb-address', type=str,
                        help="Zapper's USB switch address to use")
    parser.set_defaults(logging_level=logging.WARNING)
    args = parser.parse_args()

    # Configure logging as requested
    # XXX: This may be incorrect as logging.basicConfig() fails after any other
    # call to logging.log(). The proper solution is to setup a verbose logging
    # configuration and I didn't want to do it now.
    logging.basicConfig(
        level=args.logging_level,
        format='[%(asctime)s] %(levelname)s:%(name)s:%(message)s')

    # Connect to the system bus, we also get the event
    # loop as we need it to start listening for signals.
    system_bus, loop = connect_to_system_bus()

    # Check if system bus has the UDisks2 object
    if is_udisks2_supported(system_bus):
        # Construct the listener with all of the arguments provided on the
        # command line and the explicit system_bus, loop objects.
        logging.debug("Using UDisks2 interface")
        listener = UDisks2StorageDeviceListener(
            system_bus, loop,
            args.action, args.device, args.minimum_speed, args.memorycard,
            args.unmounted)
    else:
        # Construct the listener with all of the arguments provided on the
        # command line and the explicit system_bus, loop objects.
        logging.debug("Using UDisks1 interface")
        listener = UDisks1StorageDeviceListener(
            system_bus, loop,
            args.action, args.device, args.minimum_speed, args.memorycard)
    # Run the actual listener and wait till it either times out of discovers
    # the appropriate media changes
    if args.zapper_usb_address:
        zapper_host = os.environ.get('ZAPPER_HOST')
        if not zapper_host:
            raise SystemExit(
                "ZAPPER_HOST environment variable not found!")
        usb_address = args.zapper_usb_address
        delay = 5  # in seconds

        def do_the_insert():
            logging.info("Calling zapper to connect the USB device")
            zapper_run(zapper_host, "zombiemux_set_state", usb_address, 'DUT')
        insert_timer = threading.Timer(delay, do_the_insert)

        def do_the_remove():
            logging.info("Calling zapper to disconnect the USB device")
            zapper_run(zapper_host, "zombiemux_set_state", usb_address, 'OFF')
        remove_timer = threading.Timer(delay, do_the_remove)
        if args.action == "insert":
            logging.info("Starting timer for delayed insertion")
            insert_timer.start()
        elif args.action == "remove":
            logging.info("Starting timer for delayed removal")
            remove_timer.start()
        try:
            res = listener.check(args.timeout)
            return res
        except KeyboardInterrupt:
            return 1

    else:
        print("\n\n{} NOW\n\n".format(args.action.upper()), flush=True)
        try:
            return listener.check(args.timeout)
        except KeyboardInterrupt:
            return 1


if __name__ == "__main__":
    sys.exit(main())
