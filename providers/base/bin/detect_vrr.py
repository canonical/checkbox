#!/usr/bin/env python3
#
# This file is part of Checkbox.

# Copyright 2026 Canonical Ltd.
#
# Authors:
#   Zhongning Li <zhongning.li@canonical.com>
#
# Checkbox is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License version 3,
# as published by the Free Software Foundation.
#
# Checkbox is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Checkbox.  If not, see <http://www.gnu.org/licenses/>.


import ctypes
import ctypes.util
import os
from pathlib import Path

# this should find "libdrm.so.2"
# works on xenial too, though we won't test vrr on that
libdrm_path = ctypes.util.find_library("drm")
if not libdrm_path:
    raise ImportError("libdrm not found")
drm = ctypes.CDLL(libdrm_path)


# https://github.com/CPFL/drm/blob/6f90b77ea903756c87ae614c093e3d816ebb26fc/xf86drmMode.h#L72
DRM_MODE_PROP_NAME_LEN = 32


class drmModePropertyRes(ctypes.Structure):
    _fields_ = [
        ("prop_id", ctypes.c_uint32),
        ("flags", ctypes.c_uint32),
        ("name", ctypes.c_char * DRM_MODE_PROP_NAME_LEN),
        ("count_values", ctypes.c_uint32),
        ("values", ctypes.POINTER(ctypes.c_uint64)),
        ("count_enums", ctypes.c_uint32),
        ("enums", ctypes.c_void_p),
        ("count_blobs", ctypes.c_uint32),
        ("blob_ids", ctypes.POINTER(ctypes.c_uint32)),
    ]


class drmModeConnector(ctypes.Structure):
    _fields_ = [
        ("connector_id", ctypes.c_uint32),
        ("encoder_id", ctypes.c_uint32),
        ("connector_type", ctypes.c_uint32),
        ("connector_type_id", ctypes.c_uint32),
        ("connection", ctypes.c_uint32),
        ("mmWidth", ctypes.c_uint32),
        ("mmHeight", ctypes.c_uint32),
        ("subpixel", ctypes.c_uint32),
        ("count_modes", ctypes.c_int),
        ("modes", ctypes.c_void_p),
        ("count_props", ctypes.c_int),
        ("props", ctypes.POINTER(ctypes.c_uint32)),
        ("prop_values", ctypes.POINTER(ctypes.c_uint64)),
        ("count_encoders", ctypes.c_int),
        ("encoders", ctypes.POINTER(ctypes.c_uint32)),
    ]


class drmModeRes(ctypes.Structure):
    _fields_ = [
        ("count_fbs", ctypes.c_int),
        ("fbs", ctypes.c_void_p),
        ("count_crtcs", ctypes.c_int),
        ("crtcs", ctypes.c_void_p),
        ("count_connectors", ctypes.c_int),
        ("connectors", ctypes.POINTER(ctypes.c_uint32)),
        ("count_encoders", ctypes.c_int),
        ("encoders", ctypes.c_void_p),
        ("min_width", ctypes.c_uint32),
        ("max_width", ctypes.c_uint32),
        ("min_height", ctypes.c_uint32),
        ("max_height", ctypes.c_uint32),
    ]


drm.drmModeGetResources.restype = ctypes.POINTER(drmModeRes)
drm.drmModeGetConnector.restype = ctypes.POINTER(drmModeConnector)
drm.drmModeGetProperty.restype = ctypes.POINTER(drmModePropertyRes)


def get_vrr_capable_monitors(dri_card: Path) -> bool:
    """Checks if a /dev/dri/cardN is vrr capable
    A monitor must be connected and active for the result to be accurate

    :param dri_card: _description_
    :raises RuntimeError: Failed to open /dev/driN
    :raises RuntimeError: drmModeGetResources returned nullptr
    """
    vrr_capable = False
    with dri_card.open() as f:
        fd = f.fileno()
        if fd < 0:
            raise RuntimeError("Could not open DRM device")

        res_ptr = drm.drmModeGetResources(fd)
        if not res_ptr:
            raise RuntimeError("Failed to get DRM resources")

        res = res_ptr.contents
        for i in range(res.count_connectors):
            conn_id = res.connectors[i]
            conn_ptr = drm.drmModeGetConnector(fd, conn_id)
            if not conn_ptr:
                continue

            conn = conn_ptr.contents
            if conn.connection != 1:  # ignore disconnected connectors
                continue

            for j in range(conn.count_props):
                prop_ptr = drm.drmModeGetProperty(fd, conn.props[j])
                if not prop_ptr:
                    continue

                prop_name = prop_ptr.contents.name.decode()
                if prop_name == "vrr_capable":
                    val = conn.prop_values[j]
                    if val == 1:
                        print(
                            "Connection ID",
                            conn_id,
                            "is VRR capable",
                        )
                        # keep going, print the status for all connections
                        vrr_capable = True
                drm.drmModeFreeProperty(prop_ptr)

            drm.drmModeFreeConnector(conn_ptr)

        drm.drmModeFreeResources(res_ptr)

    return vrr_capable


if __name__ == "__main__":
    at_least_1_capable = False
    for path in Path("/dev/dri").iterdir():
        if os.path.basename(str(path)).startswith("card"):
            print("Testing", path)
            at_least_1_capable = get_vrr_capable_monitors(path)
            print("=" * 10)

    if not at_least_1_capable:
        raise SystemExit(
            "[ ERR ] None of the monitors connected to this DUT supports VRR"
        )
