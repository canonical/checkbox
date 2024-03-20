#!/usr/bin/env python3

from checkbox_support.snap_utils.snapd import Snapd
from checkbox_support.snap_utils.system import get_gadget_snap


def look_up_xtest():
    if Snapd().list("x-test"):
        return "x-test.xtest"
    elif look_up_gadget() is not False:
        return look_up_gadget()
    else:
        raise SystemExit(1)


def look_up_gadget():
    gadget = get_gadget_snap()
    snap = Snapd().list(gadget)
    if "apps" in snap.keys():
        for app in snap["apps"]:
            if app["name"] == "xtest":
                return ".".join([app["snap"], app["name"]])
    return False


def main():
    print(look_up_xtest())


if __name__ == "__main__":
    main()
