#!/usr/bin/env python3
# Copyright 2025 Canonical Ltd.
# All rights reserved.
#
# Written by:
#     Hanhsuan Lee <hanhsuan.lee@canonical.com>
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
"""
checkbox_support.helpers.file_watcher import FileWatcher
=============================================

Utility class for watching file create/modify/delete event with inotify
"""

import os
import ctypes
import struct


class FileWatcher:
    """
    This class helps to use inotify system event to monitor file status
    """

    libc = ctypes.CDLL("libc.so.6")

    # inotify constants
    IN_MODIFY = 0x00000002
    IN_CREATE = 0x00000100
    IN_DELETE = 0x00000200

    # inotify_event struct format (fixed part is 16 bytes)
    # Watch descriptor: int
    # Mask of events: uint32_t
    # Unique cookie associating related events (for rename): uint32_t
    # Size of name field: uint32_t
    # Optional null-terminated name: char
    EVENT_STRUCT_FORMAT = "iIII"

    def __init__(self):
        self.fd = self.libc.inotify_init()
        if self.fd < 0:
            raise SystemExit("Failed to initialize inotify")

    def watch_directory(self, path: str, event: str) -> int:
        """
        Set the watching path and event

        :param path:
            The full path of directory

        :param event:
            c: file create event
            m: file modify event
            d: file delete event
            Could combine them in any order, such as "mc", "dmc"
        :returns:
            Watch descriptor
        """
        mask = 0x00000000
        if "m" in event:
            mask = mask | self.IN_MODIFY
        if "d" in event:
            mask = mask | self.IN_DELETE
        if "c" in event:
            mask = mask | self.IN_CREATE
        if mask == 0x00000000:
            mask = self.IN_MODIFY
        return self.libc.inotify_add_watch(self.fd, path.encode("utf-8"), mask)

    def stop_watch(self, wd: int):
        """
        Remove the watching path and event

        :param wd:
            Watch descriptor
        """
        return self.libc.inotify_rm_watch(self.fd, wd)

    def _mask2event(self, mask: int) -> str:
        """
        Convert mask to human readable message

        :param mask:
            inotify event mask
        :returns:
            modify, create, delete or unknown
        """
        event_map = {
            self.IN_MODIFY: "modify",
            self.IN_CREATE: "create",
            self.IN_DELETE: "delete",
        }
        return event_map.get(mask, "unknown")

    def read_events(self, size: int) -> list:
        """
        Start reading event

        :param size:
            event reading size
        :returns:
            parsed event information list
        """
        raw_data = os.read(self.fd, 1024 if size < 0 else size)
        event = []
        while len(raw_data) > 0:
            wd, mask, cookie, length = struct.unpack(
                self.EVENT_STRUCT_FORMAT, raw_data[:16]
            )
            raw_data = raw_data[16:]
            name = (
                raw_data[:length].rstrip(b"\0").decode("utf-8")
                if length > 0
                else ""
            )
            event.append(
                {
                    "wd": wd,
                    "event": self._mask2event(mask),
                    "cookie": cookie,
                    "name": name,
                }
            )
            raw_data = raw_data[length:]
        return event
