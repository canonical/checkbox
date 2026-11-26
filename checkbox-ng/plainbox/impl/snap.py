"""Helpers for detecting snap confinement."""

import os


def in_classic_snap():
    """Return whether the current snap uses classic confinement."""
    snap = os.getenv("SNAP")
    if snap:
        with open(os.path.join(snap, "meta/snap.yaml")) as snap_yaml:
            for line in snap_yaml:
                if line == "confinement: classic\n":
                    return True
    return False


def in_strict_snap():
    """Return whether the current process runs in a strict snap."""
    return bool(os.getenv("SNAP")) and not in_classic_snap()
