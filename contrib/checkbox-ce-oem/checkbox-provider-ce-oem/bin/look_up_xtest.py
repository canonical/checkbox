#!/usr/bin/env python3

from checkbox_support.snap_utils.snapd import Snapd
import os


class ExtendSanpd(Snapd):
    _apps = "/v2/apps"

    def __init__(self, task_timeout=30, poll_interval=1, verbose=False):
        super().__init__(task_timeout, poll_interval, verbose)

    def list_apps(self, snaps):
        return self._get(self._apps, params={"names": snaps})


def look_up_apps(apps, snap_name=None):
    """Lookup xtest and tee-supplicant apps."""
    results = {"xtest": None, "tee": None}
    if apps:
        for app in apps:
            if app["name"] == "xtest":
                results["xtest"] = "{}.xtest".format(app["snap"])
            if app["name"] == "tee-supplicant":
                results["tee"] = "{}.tee-supplicant".format(app["snap"])
    if snap_name:
        results["xtest"] = "{}.xtest".format(snap_name)
        results["tee"] = "{}.tee-supplicant".format(snap_name)
    return results


def main():
    a = ExtendSanpd()
    snap = os.environ.get("XTEST")

    apps = a.list_apps()
    app_results = look_up_apps(apps, snap)
    return app_results


if __name__ == "__main__":
    print(main())
