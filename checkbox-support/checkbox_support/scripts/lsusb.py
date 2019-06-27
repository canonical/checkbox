#!/usr/bin/env python3
# lsusb.py
# Displays your USB devices in reasonable form.
# (c) Kurt Garloff <garloff@suse.de>, 2/2009, GPL v2 or v3.
#
# Copyright 2016 Canonical Ltd.
# Sylvain Pineau <sylvain.pineau@canonical.com>
#
# Usage: See usage()

from functools import total_ordering
import getopt
import os
import re
import sys

# Global options
showint = False
showhubint = False
noemptyhub = False
nohub = False
warnsort = False
shortmode = False

prefix = "/sys/bus/usb/devices/"
usbids = "/usr/share/usb.ids"

esc = chr(27)
norm = esc + "[0;0m"
bold = esc + "[0;1m"
red = esc + "[0;31m"
green = esc + "[0;32m"
amber = esc + "[0;33m"

cols = ("", "", "", "", "")

usbvendors = []
usbproducts = []
usbclasses = []

devlst = (
        'host',              # usb-storage
        'video4linux/video', # uvcvideo et al.
        'sound/card',        # snd-usb-audio
        'net/',              # cdc_ether, ...
        'input/input',       # usbhid
        'usb:hiddev',        # usb hid
        'bluetooth/hci',     # btusb
        'ttyUSB',            # btusb
        'tty/',              # cdc_acm
        'usb:lp',            # usblp
        'usb/',              # hiddev, usblp
    )


def readattr(path, name):
    "Read attribute from sysfs and return as string"
    f = open(prefix + path + "/" + name)
    return f.readline().rstrip("\n")


def readlink(path, name):
    "Read symlink and return basename"
    return os.path.basename(os.readlink(prefix + path + "/" + name))


@total_ordering
class UsbClass:
    "Container for USB Class/Subclass/Protocol"

    def __init__(self, cl, sc, pr, str=""):
        self.pclass = cl
        self.subclass = sc
        self.proto = pr
        self.desc = str

    def __repr__(self):
        return self.desc

    def __lt__(self, oth):
        if self.pclass != oth.pclass:
            return self.pclass - oth.pclass
        if self.subclass != oth.subclass:
            return self.subclass - oth.subclass
        return self.proto - oth.proto

    def __eq__(self, oth):
        if self.pclass != oth.pclass:
            return False
        if self.subclass != oth.subclass:
            return False
        return self.proto == oth.proto


@total_ordering
class UsbVendor:
    "Container for USB Vendors"

    def __init__(self, vid, vname=""):
        self.vid = vid
        self.vname = vname

    def __repr__(self):
        return self.vname

    def __lt__(self, oth):
        return self.vid - oth.vid

    def __eq__(self, oth):
        return self.vid == oth.vid


@total_ordering
class UsbProduct:
    "Container for USB VID:PID devices"

    def __init__(self, vid, pid, pname=""):
        self.vid = vid
        self.pid = pid
        self.pname = pname

    def __repr__(self):
        return self.pname

    def __lt__(self, oth):
        if self.vid != oth.vid:
            return self.vid - oth.vid
        return self.pid - oth.pid

    def __eq__(self, oth):
        if self.vid != oth.vid:
            return False
        return self.pid == oth.pid


def ishexdigit(str):
    "return True if all digits are valid hex digits"
    for dg in str:
        if not dg.isdigit() and dg not in 'abcdef':
            return False
    return True


def parse_usb_ids():
    "Parse /usr/share/usb.ids and fill usbvendors, usbproducts, usbclasses"
    id = 0
    sid = 0
    mode = 0
    strg = ""
    cstrg = ""
    with open(usbids, encoding="utf-8", errors='ignore') as f:
        for ln in f:
            if ln[0] == '#':
                continue
            ln = ln.rstrip('\n')
            if len(ln) == 0:
                continue
            if ishexdigit(ln[0:4]):
                mode = 0
                id = int(ln[:4], 16)
                usbvendors.append(UsbVendor(id, ln[6:]))
                continue
            if ln[0] == '\t' and ishexdigit(ln[1:3]):
                sid = int(ln[1:5], 16)
                # USB devices
                if mode == 0:
                    usbproducts.append(UsbProduct(id, sid, ln[7:]))
                    continue
                elif mode == 1:
                    nm = ln[5:]
                    if nm != "Unused":
                        strg = cstrg + ":" + nm
                    else:
                        strg = cstrg + ":"
                    usbclasses.append(UsbClass(id, sid, -1, strg))
                    continue
            if ln[0] == 'C':
                mode = 1
                id = int(ln[2:4], 16)
                cstrg = ln[6:]
                usbclasses.append(UsbClass(id, -1, -1, cstrg))
                continue
            if (
                mode == 1 and ln[0] == '\t' and ln[1] == '\t' and
                ishexdigit(ln[2:4])
            ):
                prid = int(ln[2:4], 16)
                usbclasses.append(UsbClass(id, sid, prid, strg + ":" + ln[6:]))
                continue
            mode = 2


def find_usb_prod(vid, pid):
    "Return device name from USB Vendor:Product list"
    strg = ""
    dev = UsbVendor(vid, "")
    try:
        strg = [v for v in usbvendors if v == dev][0].__repr__()
    except IndexError:
        return ""
    dev = UsbProduct(vid, pid, "")
    try:
        strg += " " + [p for p in usbproducts if p == dev][0].__repr__()
    except IndexError:
        return strg
    return strg


def find_usb_class(cid, sid, pid):
    "Return USB protocol from usbclasses list"
    if cid == 0xff and sid == 0xff and pid == 0xff:
        return "Vendor Specific"
    dev = UsbClass(cid, sid, pid, "")
    try:
        return [c for c in usbclasses if c == dev][0].__repr__()
    except IndexError:
        pass
    dev = UsbClass(cid, sid, -1, "")
    try:
        return [c for c in usbclasses if c == dev][0].__repr__()
    except IndexError:
        pass
    dev = UsbClass(cid, -1, -1, "")
    try:
        return [c for c in usbclasses if c == dev][0].__repr__()
    except IndexError:
        return ""


def find_storage(hostno):
    "Return SCSI block dev names for host"
    res = ""
    for ent in os.listdir("/sys/class/scsi_device/"):
        (host, bus, tgt, lun) = ent.split(":")
        if host == hostno:
            try:
                path = "/sys/class/scsi_device/%s/device/block" % ent
                for ent2 in os.listdir(path):
                    res += ent2 + " "
            except:
                pass
    return res


def find_dev(driver, usbname):
    "Return pseudo devname that's driven by driver"
    res = ""
    for nm in devlst:
        dir = prefix + usbname
        prep = ""
        idx = nm.find('/')
        if idx != -1:
            prep = nm[:idx+1]
            dir += "/" + nm[:idx]
            nm = nm[idx+1:]
        ln = len(nm)
        try:
            for ent in os.listdir(dir):
                if ent[:ln] == nm:
                    res += prep+ent+" "
                    if nm == "host":
                        res += "(" + find_storage(ent[ln:])[:-1] + ")"
        except:
            pass
    return res


class UsbInterface:
    "Container for USB interface info"

    def __init__(self, parent=None, level=1):
        self.parent = parent
        self.level = level
        self.fname = ""
        self.iclass = 0
        self.isclass = 0
        self.iproto = 0
        self.noep = 0
        self.driver = ""
        self.devname = ""
        self.protoname = ""

    def read(self, fname):
        fullpath = ""
        if self.parent:
            fullpath += self.parent.fname + "/"
        fullpath += fname
        self.fname = fname
        self.iclass = int(readattr(fullpath, "bInterfaceClass"), 16)
        self.isclass = int(readattr(fullpath, "bInterfaceSubClass"), 16)
        self.iproto = int(readattr(fullpath, "bInterfaceProtocol"), 16)
        self.noep = int(readattr(fullpath, "bNumEndpoints"))
        try:
            self.driver = readlink(fname, "driver")
            self.devname = find_dev(self.driver, fname)
        except:
            pass
        self.protoname = find_usb_class(self.iclass, self.isclass, self.iproto)

    def __str__(self):
        return "%-16s(IF) %02x:%02x:%02x %iEPs (%s) %s%s %s%s%s\n" % \
            (" " * self.level+self.fname, self.iclass,
             self.isclass, self.iproto, self.noep,
             self.protoname,
             cols[3], self.driver,
             cols[4], self.devname, cols[0])


class UsbDevice:
    "Container for USB device info"

    def __init__(self, parent=None, level=0):
        self.parent = parent
        self.level = level
        self.display_name = ""
        self.fname = ""
        self.busnum = 0
        self.devnum = 0
        self.iclass = 0
        self.isclass = 0
        self.iproto = 0
        self.vid = 0
        self.pid = 0
        self.name = ""
        self.usbver = ""
        self.speed = ""
        self.maxpower = ""
        self.noports = 0
        self.nointerfaces = 0
        self.driver = ""
        self.devname = ""
        self.interfaces = []
        self.children = []

    def read(self, fname):
        self.fname = fname
        self.iclass = int(readattr(fname, "bDeviceClass"), 16)
        self.isclass = int(readattr(fname, "bDeviceSubClass"), 16)
        self.iproto = int(readattr(fname, "bDeviceProtocol"), 16)
        self.vid = int(readattr(fname, "idVendor"), 16)
        self.pid = int(readattr(fname, "idProduct"), 16)
        self.busnum = int(readattr(fname, "busnum"))
        self.devnum = int(readattr(fname, "devnum"))
        self.usbver = readattr(fname, "version")
        try:
            self.name = readattr(fname, "manufacturer") + " " \
                  + readattr(fname, "product")
            if self.name[:5] == "Linux":
                rx = re.compile(r"Linux [^ ]* .hci[-_]hcd")
                mch = rx.match(self.name)
                if mch:
                    self.name = "Linux Foundation %.2f root hub" % float(
                                                                   self.usbver)
        except:
            pass
        if not self.name:
            self.name = find_usb_prod(self.vid, self.pid)
        # Some USB Card readers have a better name than Generic ...
        if self.name[:7] == "Generic":
            oldnm = self.name
            self.name = find_usb_prod(self.vid, self.pid)
            if not self.name:
                self.name = oldnm
        self.speed = readattr(fname, "speed")
        self.maxpower = readattr(fname, "bMaxPower")
        self.noports = int(readattr(fname, "maxchild"))
        try:
            self.nointerfaces = int(readattr(fname, "bNumInterfaces"))
        except:
            self.nointerfaces = 0
        try:
            self.driver = readlink(fname, "driver")
            self.devname = find_dev(self.driver, fname)
        except:
            pass

    def readchildren(self):
        if self.fname[0:3] == "usb":
            fname = self.fname[3:]
        else:
            fname = self.fname
        for dirent in os.listdir(prefix + self.fname):
            if not dirent[0:1].isdigit():
                continue
            if os.access(prefix + dirent + "/bInterfaceClass", os.R_OK):
                iface = UsbInterface(self, self.level+1)
                iface.read(dirent)
                self.interfaces.append(iface)
            else:
                usbdev = UsbDevice(self, self.level+1)
                usbdev.read(dirent)
                usbdev.readchildren()
                self.children.append(usbdev)

    def __str__(self):
        if self.iclass == 9:
            col = cols[2]
            if noemptyhub and len(self.children) == 0:
                return ""
            if nohub:
                str = ""
        else:
            col = cols[1]
        if not nohub or self.iclass != 9:
            if shortmode:
                str = "ID %04x:%04x %s" % (self.vid, self.pid, self.name)
            else:
                str = "Bus %03d Device %03d: ID %04x:%04x %s" % \
                    (self.busnum, self.devnum, self.vid, self.pid, self.name)
            str += "\n"
            if showint:
                for iface in self.interfaces:
                    str += iface.__str__()
        for child in self.children:
            str += child.__str__()
        return str


def deepcopy(lst):
    "Returns a deep copy from the list lst"
    copy = []
    for item in lst:
        copy.append(item)
    return copy


def display_diff(lst1, lst2, fmtstr, args):
    "Compare lists (same length!) and display differences"
    for idx in range(0, len(lst1)):
        if lst1[idx] != lst2[idx]:
            print("Warning: " + fmtstr % args(lst2[idx]))


def fix_usbvend():
    "Sort USB vendor list and (optionally) display diffs"
    if warnsort:
        oldusbvend = deepcopy(usbvendors)
    usbvendors.sort()
    if warnsort:
        display_diff(usbvendors, oldusbvend, "Unsorted Vendor ID %04x",
                     lambda x: (x.vid,))


def fix_usbprod():
    "Sort USB products list"
    if warnsort:
        oldusbprod = deepcopy(usbproducts)
    usbproducts.sort()
    if warnsort:
        display_diff(usbproducts, oldusbprod,
                     "Unsorted Vendor:Product ID %04x:%04x",
                     lambda x: (x.vid, x.pid))


def fix_usbclass():
    "Sort USB class list"
    if warnsort:
        oldusbcls = deepcopy(usbclasses)
    usbclasses.sort()
    if warnsort:
        display_diff(usbclasses, oldusbcls,
                     "Unsorted USB class %02x:%02x:%02x",
                     lambda x: (x.pclass, x.subclass, x.proto))


def usage():
    "Displays usage information"
    print("Usage: lsusb.py [options]")
    print("Options:")
    print(" -h display this help")
    print(" -i display interface information")
    print(" -I display interface information, even for hubs")
    print(" -u suppress empty hubs")
    print(" -U suppress all hubs")
    print(" -c use colors")
    print(" -s short mode")
    print(" -w display warning if usb.ids is not sorted correctly")
    print(" -f FILE override filename for /usr/share/usb.ids")
    return 2


def read_usb():
    "Read toplevel USB entries and print"
    for dirent in os.listdir(prefix):
        if not dirent[0:3] == "usb":
            continue
        usbdev = UsbDevice(None, 0)
        usbdev.read(dirent)
        usbdev.readchildren()
        print(usbdev.__str__(), end="")


def main():
    "main entry point"
    global showint, showhubint, noemptyhub, nohub, warnsort, cols, usbids, \
           shortmode
    try:
        (optlist, args) = getopt.gnu_getopt(sys.argv[1:], "hiIuUwcsf:", ("help",))
    except getopt.GetoptError as exc:
        print("Error:", exc)
        sys.exit(usage())
    for opt in optlist:
        if opt[0] == "-h" or opt[0] == "--help":
            usage()
            sys.exit(0)
        if opt[0] == "-i":
            showint = True
            continue
        if opt[0] == "-I":
            showint = True
            showhubint = True
            continue
        if opt[0] == "-u":
            noemptyhub = True
            continue
        if opt[0] == "-U":
            noemptyhub = True
            nohub = True
            continue
        if opt[0] == "-c":
            cols = (norm, bold, red, green, amber)
            continue
        if opt[0] == "-w":
            warnsort = True
            continue
        if opt[0] == "-f":
            usbids = opt[1]
            continue
        if opt[0] == "-s":
            shortmode = True
            continue
    if len(args) > 0:
        print("Error: excess args %s ..." % args[0])
        sys.exit(usage())
    try:
        parse_usb_ids()
        fix_usbvend()
        fix_usbprod()
        fix_usbclass()
    except:
        print(" WARNING: Failure to read usb.ids", file=sys.stderr)
        print(sys.exc_info(), file=sys.stderr)
    read_usb()

# Entry point
if __name__ == "__main__":
    main()
