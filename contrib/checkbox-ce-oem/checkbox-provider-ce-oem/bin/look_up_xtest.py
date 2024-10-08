#!/usr/bin/env python3

from checkbox_support.snap_utils.snapd import Snapd
import os


class ExtendSanpd(Snapd):
    _apps = "/v2/apps"

    def __init__(self, task_timeout=30, poll_interval=1, verbose=False):
        super().__init__(task_timeout, poll_interval, verbose)

    def list_apps(self, snaps):
        return self._get(self._apps, params={"names": snaps})


def look_up_xtest():
    """Lookup xtest and tee-supplicant apps."""
    a = ExtendSanpd()
    snap = os.environ.get("XTEST")
    apps = a.list_apps(snap)
    results = {"xtest": None, "tee": None}
    if apps["result"]:
        for app in apps["result"]:
            if app["name"] == "xtest":
                results["xtest"] = "{}.xtest".format(app["snap"])
            if app["name"] == "tee-supplicant":
                results["tee"] = "{}.tee-supplicant".format(app["snap"])
    if results["xtest"] is None or results["tee"] is None:
        raise SystemError("Can not find xtest snap in the system.")
    if results["xtest"].split(".")[0] != results["tee"].split(".")[0]:
        raise SystemError("Find more then one xtest snap in the system.")
    return results
