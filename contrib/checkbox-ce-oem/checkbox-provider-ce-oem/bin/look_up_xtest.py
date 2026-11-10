#!/usr/bin/env python3

from checkbox_support.snap_utils.snapd import Snapd


class ExtendSanpd(Snapd):
    _apps = "/v2/apps"

    def __init__(self, task_timeout=30, poll_interval=1, verbose=False):
        super().__init__(task_timeout, poll_interval, verbose)

    def list_apps(self, snaps=None):
        # Snapd._request() appends `params` verbatim as the query
        # string (it is not a dict passed to e.g. requests), so it
        # must be pre-formatted as "names=<snap>" here. Passing the
        # bare snap name (the previous behaviour) built an invalid
        # query string that snapd silently ignored, so /v2/apps
        # returned every app on the system instead of just this
        # snap's — look_up_app() would then happily match an "xtest"
        # app belonging to a completely different snap (e.g. the
        # board's gadget snap) instead of failing loudly.
        params = "names={}".format(snaps) if snaps else None
        return self._get(self._apps, params=params)


def look_up_app(target_app, snap_name=None):
    """Lookup target app and the snap."""
    apps = ExtendSanpd().list_apps(snap_name)
    try:
        for app in apps["result"]:
            if app["name"] == target_app:
                return ".".join([app["snap"], app["name"]])
    except Exception:
        raise SystemError("Not found {} in the system!".format(target_app))
