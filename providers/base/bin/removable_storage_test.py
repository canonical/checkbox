#!/usr/bin/env python3

import argparse
import collections
import dbus
import hashlib
import logging
import os
import platform
import re
import shlex
import subprocess
import sys
import tempfile
import time

import gi
gi.require_version('GUdev', '1.0')
from gi.repository import GUdev                                 # noqa: E402

from checkbox_support.dbus import connect_to_system_bus         # noqa: E402
from checkbox_support.dbus.udisks2 import (                     # noqa: E402
    UDISKS2_BLOCK_INTERFACE,
    UDISKS2_DRIVE_INTERFACE,
    UDISKS2_FILESYSTEM_INTERFACE,
    UDISKS2_LOOP_INTERFACE,
    UDisks2Model,
    UDisks2Observer,
    is_udisks2_supported,
    lookup_udev_device,
    map_udisks1_connection_bus)
from checkbox_support.heuristics.udisks2 import is_memory_card  # noqa: E402
from checkbox_support.helpers.human_readable_bytes import (     # noqa: E402
    HumanReadableBytes)
from checkbox_support.parsers.udevadm import (                  # noqa: E402
    CARD_READER_RE,
    GENERIC_RE,
    FLASH_RE,
    find_pkname_is_root_mountpoint)                             # noqa: E402
from checkbox_support.udev import get_interconnect_speed        # noqa: E402
from checkbox_support.udev import get_udev_block_devices        # noqa: E402
from checkbox_support.udev import get_udev_xhci_devices         # noqa: E402


class ActionTimer():
    '''Class to implement a simple timer'''

    def __enter__(self):
        self.start = time.time()
        return self

    def __exit__(self, *args):
        self.stop = time.time()
        self.interval = self.stop - self.start


class RandomData():
    '''Class to create data files'''

    def __init__(self, size):
        self.tfile = tempfile.NamedTemporaryFile(delete=False)
        self.path = ''
        self.name = ''
        self.path, self.name = os.path.split(self.tfile.name)
        self._write_test_data_file(size)

    def _generate_test_data(self):
        seed = "104872948765827105728492766217823438120"
        phrase = '''
        Lorem ipsum dolor sit amet, consectetuer adipiscing elit, sed diam
        nonummy nibh euismod tincidunt ut laoreet dolore magna aliquam erat
        volutpat. Ut wisi enim ad minim veniam, quis nostrud exerci tation
        ullamcorper suscipit lobortis nisl ut aliquip ex ea commodo consequat.
        Duis autem vel eum iriure dolor in hendrerit in vulputate velit esse
        molestie consequat, vel illum dolore eu feugiat nulla facilisis at vero
        eros et accumsan et iusto odio dignissim qui blandit praesent luptatum
        zzril delenit augue duis dolore te feugait nulla facilisi.
        '''
        words = phrase.replace('\n', '').split()
        word_deque = collections.deque(words)
        seed_deque = collections.deque(seed)
        while True:
            yield ' '.join(list(word_deque))
            word_deque.rotate(int(seed_deque[0]))
            seed_deque.rotate(1)

    def _write_test_data_file(self, size):
        data = self._generate_test_data()
        while os.path.getsize(self.tfile.name) < size:
            self.tfile.write(next(data).encode('UTF-8'))
        return self


def md5_hash_file(path):
    md5 = hashlib.md5()
    try:
        with open(path, 'rb') as stream:
            while True:
                data = stream.read(8192)
                if not data:
                    break
                md5.update(data)
    except IOError as exc:
        logging.error("unable to checksum %s: %s", path, exc)
        return None
    else:
        return md5.hexdigest()


def on_ubuntucore():
    """
    Check if running from on ubuntu core
    """
    snap = os.getenv("SNAP")
    if snap:
        with open(os.path.join(snap, 'meta/snap.yaml')) as f:
            for line in f.readlines():
                if line == "confinement: classic\n":
                    return False
        return True
    return False


class DiskTest():
    ''' Class to contain various methods for testing removable disks '''

    def __init__(self, device, memorycard, lsblkcommand):
        self.rem_disks = {}     # mounted before the script running
        self.rem_disks_nm = {}  # not mounted before the script running
        self.rem_disks_memory_cards = {}
        self.rem_disks_memory_cards_nm = {}
        self.rem_disks_speed = {}
        # LP: #1313581, TODO: extend to be rem_disks_driver
        self.rem_disks_xhci = {}
        self.data = ''
        self.lsblk = ''
        self.device = device
        self.memorycard = memorycard
        self._run_lsblk(lsblkcommand)
        self._probe_disks()

    def read_file(self, source):
        with open(source, 'rb') as infile:
            try:
                self.data = infile.read()
            except IOError as exc:
                logging.error("Unable to read data from %s: %s", source, exc)
                return False
            else:
                return True

    def write_file(self, data, dest):
        try:
            outfile = open(dest, 'wb', 0)
        except OSError as exc:
            logging.error("Unable to open %s for writing.", dest)
            logging.error("  %s", exc)
            return False
        with outfile:
            try:
                outfile.write(self.data)
            except IOError as exc:
                logging.error("Unable to write data to %s: %s", dest, exc)
                return False
            else:
                outfile.flush()
                os.fsync(outfile.fileno())
                return True

    def clean_up(self, target):
        try:
            os.unlink(target)
        except OSError as exc:
            logging.error("Unable to remove tempfile %s", target)
            logging.error("  %s", exc)

    def _find_parent(self, device):
        if self.lsblk:
            pattern = re.compile('KNAME="(?P<KNAME>.*)" '
                                 'TYPE="(?P<TYPE>.*)" '
                                 'MOUNTPOINT="(?P<MOUNTPOINT>.*)"')
            for line in self.lsblk.splitlines():
                m = pattern.match(line)
                if m and device.startswith(m.group('KNAME')):
                    return m.group('KNAME')
        return False

    def _run_lsblk(self, lsblkcommand):
        try:
            self.lsblk = subprocess.check_output(shlex.split(lsblkcommand),
                                                 universal_newlines=True)
        except subprocess.CalledProcessError as exc:
            raise SystemExit(exc)

    def _probe_disks(self):
        """
        Internal method used to probe for available disks

        Indirectly sets:
            self.rem_disks{,_nm,_memory_cards,_memory_cards_nm,_speed}
        """
        if on_ubuntucore():
            self._probe_disks_udisks2_cli()
        else:
            bus, loop = connect_to_system_bus()
            if is_udisks2_supported(bus):
                self._probe_disks_udisks2(bus)
            else:
                self._probe_disks_udisks1(bus)

    def _probe_disks_udisks2_cli(self):
        # First we will build up a db of udisks info by scraping the output
        # of the dump command
        # TODO: remove the snap prefix when the alias becomes available
        proc = subprocess.Popen(['udisks2.udisksctl', 'dump'],
                                stdout=subprocess.PIPE)
        udisks_devices = {}
        current_bd = None
        current_interface = None
        while True:
            line = proc.stdout.readline().decode(sys.stdout.encoding)
            if line == '':
                break
            if line == '\n':
                current_bd = None
                current_interface = None
            if line.startswith('/org/freedesktop/UDisks2/'):
                path = line.strip()
                current_bd = os.path.basename(path).rstrip(':')
                udisks_devices[current_bd] = {}
                continue
            if current_bd is None:
                continue
            if line.startswith('  org.freedesktop'):
                current_interface = line.strip().rstrip(':')
                udisks_devices[current_bd][current_interface] = {}
                continue
            if current_interface is None:
                continue
            entry = ''.join(c for c in line if c not in '\n\t\' ')
            wanted_keys = ('Device:', 'Drive:', 'MountPoints:', 'Vendor:',
                           'ConnectionBus:', 'Model:', 'Media:',)
            for key in wanted_keys:
                if entry.startswith(key):
                    udisks_devices[current_bd][current_interface][key] = (
                        entry[len(key):])

        # Now use the populated udisks structure to fill out the API used by
        # other _probe disks functions
        for device, interfaces in udisks_devices.items():
            # iterate over udisks objects that have both filesystem and
            # block device interfaces
            if (UDISKS2_FILESYSTEM_INTERFACE in interfaces and
                    UDISKS2_BLOCK_INTERFACE in interfaces):
                # To be an IO candidate there must be a drive object
                drive = interfaces[UDISKS2_BLOCK_INTERFACE].get('Drive:')
                if drive is None or drive == '/':
                    continue
                drive_object = udisks_devices[os.path.basename(drive)]

                # Get the connection bus property from the drive interface of
                # the drive object. This is required to filter out the devices
                # we don't want to look at now.
                connection_bus = (
                    drive_object[UDISKS2_DRIVE_INTERFACE]['ConnectionBus:'])
                desired_connection_buses = set([
                    map_udisks1_connection_bus(device)
                    for device in self.device])
                # Skip devices that are attached to undesired connection buses
                if connection_bus not in desired_connection_buses:
                    continue

                dev_file = (
                    interfaces[UDISKS2_BLOCK_INTERFACE].get('Device:'))

                parent = self._find_parent(dev_file.replace('/dev/', ''))
                if (parent and
                        find_pkname_is_root_mountpoint(parent, self.lsblk)):
                    continue

                # XXX: we actually only scrape the first one currently
                mount_point = (
                    interfaces[UDISKS2_FILESYSTEM_INTERFACE].get(
                        'MountPoints:'))
                if mount_point == '':
                    mount_point = None

                # We need to skip-non memory cards if we look for memory cards
                # and vice-versa so let's inspect the drive and use heuristics
                # to detect memory cards (a memory card reader actually) now.
                if self.memorycard != is_memory_card(
                        drive_object[UDISKS2_DRIVE_INTERFACE]['Vendor:'],
                        drive_object[UDISKS2_DRIVE_INTERFACE]['Model:'],
                        drive_object[UDISKS2_DRIVE_INTERFACE]['Media:']):
                    continue

                if mount_point is None:
                    self.rem_disks_memory_cards_nm[dev_file] = None
                    self.rem_disks_nm[dev_file] = None
                else:
                    self.rem_disks_memory_cards[dev_file] = mount_point
                    self.rem_disks[dev_file] = mount_point

                # Get the speed of the interconnect that is associated with the
                # block device we're looking at. This is purely informational
                # but it is a part of the required API
                udev_devices = get_udev_block_devices(GUdev.Client())
                for udev_device in udev_devices:
                    if udev_device.get_device_file() == dev_file:
                        interconnect_speed = get_interconnect_speed(
                            udev_device)
                        if interconnect_speed:
                            self.rem_disks_speed[dev_file] = (
                                interconnect_speed * 10 ** 6)
                        else:
                            self.rem_disks_speed[dev_file] = None

    def _probe_disks_udisks2(self, bus):
        """
        Internal method used to probe / discover available disks using udisks2
        dbus interface using the provided dbus bus (presumably the system bus)
        """
        # We'll need udisks2 and udev to get the data we need
        udisks2_observer = UDisks2Observer()
        udisks2_model = UDisks2Model(udisks2_observer)
        udisks2_observer.connect_to_bus(bus)
        udev_client = GUdev.Client()
        # Get a collection of all udev devices corresponding to block devices
        udev_devices = get_udev_block_devices(udev_client)
        # Get a collection of all udisks2 objects
        udisks2_objects = udisks2_model.managed_objects
        # Let's get a helper to simplify the loop below

        def iter_filesystems_on_block_devices():
            """
            Generate a collection of UDisks2 object paths that
            have both the filesystem and block device interfaces
            """
            for udisks2_object_path, interfaces in udisks2_objects.items():
                if (UDISKS2_FILESYSTEM_INTERFACE in interfaces and
                        UDISKS2_BLOCK_INTERFACE in interfaces and
                        UDISKS2_LOOP_INTERFACE not in interfaces):
                    yield udisks2_object_path
        # We need to know about all IO candidates,
        # let's iterate over all the block devices reported by udisks2
        for udisks2_object_path in iter_filesystems_on_block_devices():
            # Get interfaces implemented by this object
            udisks2_object = udisks2_objects[udisks2_object_path]
            # Find the path of the udisks2 object that represents the drive
            # this object is a part of
            drive_object_path = (
                udisks2_object[UDISKS2_BLOCK_INTERFACE]['Drive'])
            # Lookup the drive object, if any. This can fail when
            try:
                drive_object = udisks2_objects[drive_object_path]
            except KeyError:
                logging.error(
                    "Unable to locate drive associated with %s",
                    udisks2_object_path)
                continue
            else:
                drive_props = drive_object[UDISKS2_DRIVE_INTERFACE]
            # Get the connection bus property from the drive interface of the
            # drive object. This is required to filter out the devices we don't
            # want to look at now.
            connection_bus = drive_props["ConnectionBus"]
            desired_connection_buses = set([
                map_udisks1_connection_bus(device)
                for device in self.device])
            # Skip devices that are attached to undesired connection buses
            if connection_bus not in desired_connection_buses:
                continue
            # Lookup the udev object that corresponds to this object
            try:
                udev_device = lookup_udev_device(udisks2_object, udev_devices)
            except LookupError:
                logging.error(
                    "Unable to locate udev object that corresponds to: %s",
                    udisks2_object_path)
                continue
            # Get the block device pathname,
            # to avoid the confusion, this is something like /dev/sdbX
            dev_file = udev_device.get_device_file()
            parent = self._find_parent(dev_file.replace('/dev/', ''))
            if parent and find_pkname_is_root_mountpoint(parent, self.lsblk):
                continue
            # Get the list of mount points of this block device
            mount_points = (
                udisks2_object[UDISKS2_FILESYSTEM_INTERFACE]['MountPoints'])
            # Get the speed of the interconnect that is associated with the
            # block device we're looking at. This is purely informational but
            # it is a part of the required API
            interconnect_speed = get_interconnect_speed(udev_device)
            if interconnect_speed:
                self.rem_disks_speed[dev_file] = (
                    interconnect_speed * 10 ** 6)
            else:
                self.rem_disks_speed[dev_file] = None
            # Ensure it is a media card reader if this was explicitly requested
            drive_is_reader = is_memory_card(
                drive_props['Vendor'], drive_props['Model'],
                drive_props['Media'])
            if self.memorycard and not drive_is_reader:
                continue
            # The if/else test below simply distributes the mount_point to the
            # appropriate variable, to keep the API requirements. It is
            # confusing as _memory_cards is variable is somewhat dummy.
            if mount_points:
                # XXX: Arbitrarily pick the first of the mount points
                mount_point = mount_points[0]
                self.rem_disks_memory_cards[dev_file] = mount_point
                self.rem_disks[dev_file] = mount_point
            else:
                self.rem_disks_memory_cards_nm[dev_file] = None
                self.rem_disks_nm[dev_file] = None

    def _probe_disks_udisks1(self, bus):
        """
        Internal method used to probe / discover available disks using udisks1
        dbus interface using the provided dbus bus (presumably the system bus)
        """
        ud_manager_obj = bus.get_object("org.freedesktop.UDisks",
                                        "/org/freedesktop/UDisks")
        ud_manager = dbus.Interface(ud_manager_obj, 'org.freedesktop.UDisks')
        for dev in ud_manager.EnumerateDevices():
            device_obj = bus.get_object("org.freedesktop.UDisks", dev)
            device_props = dbus.Interface(device_obj, dbus.PROPERTIES_IFACE)
            udisks = 'org.freedesktop.UDisks.Device'
            if not device_props.Get(udisks, "DeviceIsDrive"):
                dev_bus = device_props.Get(udisks, "DriveConnectionInterface")
                if dev_bus in self.device:
                    parent_model = parent_vendor = ''
                    if device_props.Get(udisks, "DeviceIsPartition"):
                        parent_obj = bus.get_object(
                            "org.freedesktop.UDisks",
                            device_props.Get(udisks, "PartitionSlave"))
                        parent_props = dbus.Interface(
                            parent_obj, dbus.PROPERTIES_IFACE)
                        parent_model = parent_props.Get(udisks, "DriveModel")
                        parent_vendor = parent_props.Get(udisks, "DriveVendor")
                        parent_media = parent_props.Get(udisks, "DriveMedia")
                    if self.memorycard:
                        if (dev_bus != 'sdio' and not
                                FLASH_RE.search(parent_media) and not
                                CARD_READER_RE.search(parent_model) and not
                                GENERIC_RE.search(parent_vendor)):
                            continue
                    else:
                        if (FLASH_RE.search(parent_media) or
                                CARD_READER_RE.search(parent_model) or
                                GENERIC_RE.search(parent_vendor)):
                            continue
                    dev_file = str(device_props.Get(udisks, "DeviceFile"))
                    dev_speed = str(device_props.Get(udisks,
                                                     "DriveConnectionSpeed"))
                    self.rem_disks_speed[dev_file] = dev_speed
                    if len(device_props.Get(udisks, "DeviceMountPaths")) > 0:
                        devPath = str(device_props.Get(udisks,
                                                       "DeviceMountPaths")[0])
                        self.rem_disks[dev_file] = devPath
                        self.rem_disks_memory_cards[dev_file] = devPath
                    else:
                        self.rem_disks_nm[dev_file] = None
                        self.rem_disks_memory_cards_nm[dev_file] = None

    def get_disks_xhci(self):
        """
        Compare
        1. the pci slot name of the devices using xhci
        2. the pci slot name of the disks,
           which is usb3 disks in this case so far,
        to make sure the usb3 disk does be on the controller using xhci
        """
        # LP: #1378724
        udev_client = GUdev.Client()
        # Get a collection of all udev devices corresponding to block devices
        udev_devices = get_udev_block_devices(udev_client)
        # Get a collection of all udev devices corresponding to xhci devices
        udev_devices_xhci = get_udev_xhci_devices(udev_client)
        if platform.machine() in ("aarch64", "armv7l"):
            enumerator = GUdev.Enumerator(client=udev_client)
            udev_devices_xhci = [
                device for device in enumerator.execute()
                if (device.get_driver() == 'xhci-hcd' or
                    device.get_driver() == 'xhci_hcd')]
        for udev_device_xhci in udev_devices_xhci:
            pci_slot_name = udev_device_xhci.get_property('PCI_SLOT_NAME')
            xhci_devpath = udev_device_xhci.get_property('DEVPATH')
            for udev_device in udev_devices:
                devpath = udev_device.get_property('DEVPATH')
                if (self._compare_pci_slot_from_devpath(devpath,
                                                        pci_slot_name)):
                    self.rem_disks_xhci[
                        udev_device.get_property('DEVNAME')] = 'xhci'
                if platform.machine() in ("aarch64", "armv7l"):
                    if xhci_devpath in devpath:
                        self.rem_disks_xhci[
                            udev_device.get_property('DEVNAME')] = 'xhci'
        return self.rem_disks_xhci

    def mount(self):
        passed_mount = {}

        for key in self.rem_disks_nm:
            temp_dir = tempfile.mkdtemp()
            if self._mount(key, temp_dir) != 0:
                logging.error("can't mount %s", key)
            else:
                passed_mount[key] = temp_dir

        if len(self.rem_disks_nm) == len(passed_mount):
            self.rem_disks_nm = passed_mount
            return 0
        else:
            count = len(self.rem_disks_nm) - len(passed_mount)
            self.rem_disks_nm = passed_mount
            return count

    def _mount(self, dev_file, mount_point):
        return subprocess.call(['mount', dev_file, mount_point])

    def umount(self):
        errors = 0
        for disk in self.rem_disks_nm:
            if not self.rem_disks_nm[disk]:
                continue
            if self._umount(disk) != 0:
                errors += 1
                logging.error("can't umount %s on %s",
                              disk, self.rem_disks_nm[disk])
        return errors

    def _umount(self, mount_point):
        # '-l': lazy umount, dealing problem of unable to umount the device.
        return subprocess.call(['umount', '-l', mount_point])

    def clean_tmp_dir(self):
        for disk in self.rem_disks_nm:
            if not self.rem_disks_nm[disk]:
                continue
            if not os.path.ismount(self.rem_disks_nm[disk]):
                os.rmdir(self.rem_disks_nm[disk])

    def _compare_pci_slot_from_devpath(self, devpath, pci_slot_name):
        # LP: #1334991
        # a smarter parser to get and validate a pci slot name from DEVPATH
        # then compare this pci slot name to the other
        dl = devpath.split('/')
        s = set([x for x in dl if dl.count(x) > 1])
        if (
            (pci_slot_name in dl) and
            (dl.index(pci_slot_name) < dl.index('block')) and
            (not (pci_slot_name in s))
        ):
            # 1. there is such pci_slot_name
            # 2. sysfs topology looks like
            #    DEVPATH = ....../pci_slot_name/....../block/......
            # 3. pci_slot_name should be unique in DEVPATH
            return True
        else:
            return False


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('device',
                        choices=['usb', 'firewire', 'sdio',
                                 'scsi', 'ata_serial_esata'],
                        nargs='+',
                        help=("The type of removable media "
                              "(usb, firewire, sdio, scsi or ata_serial_esata)"
                              "to test."))
    parser.add_argument('-l', '--list',
                        action='store_true',
                        default=False,
                        help="List the removable devices and mounting status")
    parser.add_argument('-m', '--min-speed',
                        action='store',
                        default=0,
                        type=int,
                        help="Minimum speed a device must support to be "
                             "considered eligible for being tested (bits/s)")
    parser.add_argument('-p', '--pass-speed',
                        action='store',
                        default=0,
                        type=int,
                        help="Minimum average throughput from all eligible"
                             "devices for the test to pass (MB/s)")
    parser.add_argument('-i', '--iterations',
                        action='store',
                        default='1',
                        type=int,
                        help=("The number of test cycles to run. One cycle is"
                              "comprised of generating --count data files of "
                              "--size bytes and writing them to each device."))
    parser.add_argument('-c', '--count',
                        action='store',
                        default='1',
                        type=int,
                        help='The number of random data files to generate')
    parser.add_argument('-s', '--size',
                        action='store',
                        type=HumanReadableBytes,
                        default='1MiB',
                        help=("The size of the test data file to use. "
                              "You may use SI or IEC suffixes like: 'K', 'M',"
                              "'G', 'T', 'Ki', 'Mi', 'Gi', 'Ti', etc. Default"
                              " is %(default)s"))
    parser.add_argument('--auto-reduce-size',
                        action='store_true',
                        default=False,
                        help=("Automatically reduce size to fit in the target"
                              "filesystem. Reducing until fits in 1MiB"))
    parser.add_argument('-n', '--skip-not-mount',
                        action='store_true',
                        default=False,
                        help=("skip the removable devices "
                              "which haven't been mounted before the test."))
    parser.add_argument('--memorycard', action="store_true",
                        help=("Memory cards devices on bus other than sdio "
                              "require this parameter to identify "
                              "them as such"))
    parser.add_argument('--driver',
                        choices=['xhci_hcd'],
                        help=("Detect the driver of the host controller."
                              "Only xhci_hcd for usb3 is supported so far."))
    parser.add_argument("--lsblkcommand", action='store', type=str,
                        default="lsblk -i -n -P -e 7 -o KNAME,TYPE,MOUNTPOINT",
                        help=("Command to execute to get lsblk information. "
                              "Only change it if you know what you're doing."))

    args = parser.parse_args()

    test = DiskTest(args.device, args.memorycard, args.lsblkcommand)

    # LP:1876966
    if os.getuid() != 0:
        print("ERROR: This script must be run as root!")
        return 1

    errors = 0
    # If we do have removable drives attached and mounted
    if len(test.rem_disks) > 0 or len(test.rem_disks_nm) > 0:
        if args.list:  # Simply output a list of drives detected
            print('-' * 20)
            print("Removable devices currently mounted:")
            if args.memorycard:
                if len(test.rem_disks_memory_cards) > 0:
                    for disk, mnt_point in test.rem_disks_memory_cards.items():
                        print("%s : %s" % (disk, mnt_point))
                else:
                    print("None")

                print("Removable devices currently not mounted:")
                if len(test.rem_disks_memory_cards_nm) > 0:
                    for disk in test.rem_disks_memory_cards_nm:
                        print(disk)
                else:
                    print("None")
            else:
                if len(test.rem_disks) > 0:
                    for disk, mnt_point in test.rem_disks.items():
                        print("%s : %s" % (disk, mnt_point))
                else:
                    print("None")

                print("Removable devices currently not mounted:")
                if len(test.rem_disks_nm) > 0:
                    for disk in test.rem_disks_nm:
                        print(disk)
                else:
                    print("None")

            print('-' * 20)

            return 0

        else:  # Create a file, copy to disk and compare hashes
            if args.skip_not_mount:
                disks_all = test.rem_disks
            else:
                # mount those haven't be mounted yet.
                errors_mount = test.mount()

                if errors_mount > 0:
                    print("There're total %d device(s) failed at mounting."
                          % errors_mount)
                    errors += errors_mount

                disks_all = dict(list(test.rem_disks.items()) +
                                 list(test.rem_disks_nm.items()))

            if len(disks_all) > 0:
                print("Found the following mounted %s partitions:"
                      % ', '.join(args.device))

                for disk, mount_point in disks_all.items():
                    supported_speed = test.rem_disks_speed[disk]
                    print("    %s : %s : %s bits/s" %
                          (disk, mount_point, supported_speed),
                          end="")
                    if (args.min_speed and
                            int(args.min_speed) > int(supported_speed)):
                        print(" (Will not test it, speed is below %s bits/s)" %
                              args.min_speed, end="")

                    print("")

                print('-' * 20)

                disks_eligible = {disk: disks_all[disk] for disk in disks_all
                                  if not args.min_speed or
                                  int(test.rem_disks_speed[disk]) >=
                                  int(args.min_speed)}
                if len(disks_eligible) == 0:
                    logging.error(
                        "No %s disks with speed higher than %s bits/s",
                        args.device, args.min_speed)
                    return 1
                write_sizes = []
                test_files = {}
                disks_freespace = {}
                for disk, path in disks_eligible.items():
                    stat = os.statvfs(path)
                    disks_freespace[disk] = stat.f_bfree * stat.f_bsize
                smallest_freespace = min(disks_freespace.values())
                smallest_partition = [d for d, v in disks_freespace.items() if
                                      v == smallest_freespace][0]
                desired_size = args.size
                if desired_size > smallest_freespace:
                    if args.auto_reduce_size:
                        min_space = HumanReadableBytes("1MiB")
                        if smallest_freespace < min_space:
                            sys.exit("Not enough space. {} is required on {}"
                                     .format(min_space, smallest_partition))
                        new_size = HumanReadableBytes(
                            int(0.8 * smallest_freespace))
                        logging.warning("Automatically reducing test data size"
                                        ". {} requested. Reducing to {}."
                                        .format(desired_size, new_size))
                        desired_size = new_size
                    else:
                        sys.exit("Not enough space. {} is required on {}"
                                 .format(desired_size, smallest_partition))
                # Generate our data file(s)
                for count in range(args.count):
                    test_files[count] = RandomData(desired_size)
                    write_sizes.append(os.path.getsize(
                        test_files[count].tfile.name))
                    total_write_size = sum(write_sizes)

                try:
                    # Clear dmesg so we can check for I/O errors later
                    subprocess.check_output(['dmesg', '-C'])
                    for disk, mount_point in disks_eligible.items():
                        print("%s (Total Data Size / iteration: %0.4f MB):" %
                              (disk, (total_write_size / 1024 / 1024)))
                        iteration_write_size = (
                            total_write_size * args.iterations) / 1024 / 1024
                        iteration_write_times = []
                        for iteration in range(args.iterations):
                            target_file_list = []
                            write_times = []
                            for file_index in range(args.count):
                                parent_file = test_files[file_index].tfile.name
                                parent_hash = md5_hash_file(parent_file)
                                target_filename = (
                                    test_files[file_index].name +
                                    '.%s' % iteration)
                                target_path = mount_point
                                target_file = os.path.join(target_path,
                                                           target_filename)
                                target_file_list.append(target_file)
                                test.read_file(parent_file)
                                with ActionTimer() as timer:
                                    if not test.write_file(test.data,
                                                           target_file):
                                        logging.error(
                                            "Failed to copy %s to %s",
                                            parent_file, target_file)
                                        errors += 1
                                        continue
                                write_times.append(timer.interval)
                                child_hash = md5_hash_file(target_file)
                                if parent_hash != child_hash:
                                    logging.warning(
                                        "[Iteration %s] Parent and Child"
                                        " copy hashes mismatch on %s!",
                                        iteration, target_file)
                                    logging.warning(
                                        "\tParent hash: %s", parent_hash)
                                    logging.warning(
                                        "\tChild hash: %s", child_hash)
                                    errors += 1
                            for file in target_file_list:
                                test.clean_up(file)
                            total_write_time = sum(write_times)
                            # avg_write_time = total_write_time / args.count
                            try:
                                avg_write_speed = ((
                                    total_write_size / total_write_time) /
                                    1024 / 1024)
                            except ZeroDivisionError:
                                avg_write_speed = 0.00
                            finally:
                                iteration_write_times.append(total_write_time)
                                print("\t[Iteration %s] Average Speed: %0.4f"
                                      % (iteration, avg_write_speed))
                        for iteration in range(args.iterations):
                            iteration_write_time = sum(iteration_write_times)
                        print("\tSummary:")
                        print("\t\tTotal Data Attempted: %0.4f MB"
                              % iteration_write_size)
                        print("\t\tTotal Time to write: %0.4f secs"
                              % iteration_write_time)
                        print("\t\tAverage Write Time: %0.4f secs" %
                              (iteration_write_time / args.iterations))
                        try:
                            avg_write_speed = (iteration_write_size /
                                               iteration_write_time)
                        except ZeroDivisionError:
                            avg_write_speed = 0.00
                        finally:
                            print("\t\tAverage Write Speed: %0.4f MB/s" %
                                  avg_write_speed)
                finally:
                    for key in range(args.count):
                        test.clean_up(test_files[key].tfile.name)
                    if (len(test.rem_disks_nm) > 0):
                        if test.umount() != 0:
                            errors += 1
                        test.clean_tmp_dir()
                    dmesg = subprocess.run(['dmesg'], stdout=subprocess.PIPE)
                    if 'I/O error' in dmesg.stdout.decode():
                        logging.error("I/O errors found in dmesg")
                        errors += 1

                if errors > 0:
                    logging.warning(
                        "Completed %s test iterations, but there were"
                        " errors", args.count)
                    return 1
                else:
                    # LP: 1313581
                    # Try to figure out whether the disk
                    # is SuperSpeed USB and using xhci_hcd driver.
                    if (args.driver == 'xhci_hcd'):
                        # The speed reported by udisks is sometimes
                        # less than 5G bits/s, for example,
                        # it may be 705032705 bits/s
                        # So using
                        # 500000000
                        # = 500 M bits/s
                        # > 480 M bits/s ( USB 2.0 spec.)
                        # to make sure that it is higher USB version than 2.0
                        #
                        # int() for int(test.rem_disks_speed[disk])
                        # is necessary
                        # because the speed value of
                        # the dictionary rem_disks_speed is
                        # 1. str or int from _probe_disks_udisks2
                        # 2. int from _probe_disks_udisks1.
                        # This is really a mess. : (
                        print("\t\t--------------------------------")
                        if (500000000 < int(test.rem_disks_speed[disk])):
                            print("\t\tDevice Detected: SuperSpeed USB")
                            # Unlike rem_disks_speed,
                            # which must has the connect speed
                            # for each disk devices,
                            # disk devices may not use xhci as
                            # controller drivers.
                            # This will raise KeyError for no
                            # associated disk device was found.
                            if test.get_disks_xhci().get(disk, '') != 'xhci':
                                raise SystemExit(
                                    "\t\tDisk does not use xhci_hcd.")
                            print("\t\tDriver Detected: xhci_hcd")
                        else:
                            # Give it a hint for the detection failure.
                            # LP: #1362902
                            print(("\t\tNo SuperSpeed USB using xhci_hcd "
                                   "was detected correctly."))
                            print(("\t\tHint: please use dmesg to check "
                                   "the system status again."))
                            return 1
                    # Pass is not assured
                    if (not args.pass_speed or
                            avg_write_speed >= args.pass_speed):
                        return 0
                    else:
                        print("FAIL: Average speed was lower than desired "
                              "pass speed of %s MB/s" % args.pass_speed)
                        return 1
            else:
                logging.error("No device being mounted successfully "
                              "for testing, aborting")
                return 1

    else:  # If we don't have removable drives attached and mounted
        logging.error("No removable drives were detected, aborting")
        return 1


if __name__ == '__main__':
    sys.exit(main())
