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
    snap = os.environ.get("XTEST")
    apps = ExtendSanpd().list_apps(snap)
    results = {"xtest": None, "tee-supplicant": None}
    xtest_apps = list(
        {
            (app["snap"], app["name"])
            for app in apps["result"]
            if app["name"] in ["tee-supplicant", "xtest"]
        }
    )
    if xtest_apps:
        if (
            len(xtest_apps) > 2
            or xtest_apps[0][0] != xtest_apps[1][0]
            or xtest_apps[0][1] == xtest_apps[1][1]
        ):
            raise SystemError("Found multiple xtest snap in the system!")
    else:
        raise SystemError("Not found xtest snap in the system!")
    for key in results.keys():
        results[key] = ".".join([xtest_apps[0][0], key])
    return results
