#!/usr/bin/env python3

from checkbox_support.snap_utils.snapd import Snapd
import os


class ExtendSanpd(Snapd):
    _apps = "/v2/apps"

    def __init__(self, task_timeout=30, poll_interval=1, verbose=False):
        super().__init__(task_timeout, poll_interval, verbose)

    def list_apps(self, snaps):
        return self._get(self._apps, params={"names": snaps})


def look_up_app(target_app):
    """Lookup target app and the snap."""
    if target_app == "xtest":
        snap = os.environ.get("XTEST")
    elif target_app == "tee-supplicant":
        snap = os.environ.get("TEE_SUPPLICANT")
    apps = ExtendSanpd().list_apps(snap)
    try:
        for app in apps["result"]:
            if app["name"] == target_app:
                return ".".join([app["snap"], app["name"]])
    except Exception:
        raise SystemError("Not found {} in the system!".format(target_app))
