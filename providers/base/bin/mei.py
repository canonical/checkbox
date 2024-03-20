#!/usr/bin/env python3

import array
import uuid
import fcntl
import struct
import os
from argparse import ArgumentParser


DEFAULT_MEI_NODE = "mei0"


class MEI_INTERFACE():

    IOCTL_MEI_CONNECT_CLIENT = 0xc0104801

    def __init__(self):
        self._mei_obj = None

    def _get_mei(self):
        path = "/dev"
        devices = os.listdir(path)
        if DEFAULT_MEI_NODE in devices:
            return os.path.join(path, DEFAULT_MEI_NODE)
        for device in devices:
            if device.find("mei") != -1:
                return os.path.join(path, device)

    def open(self):
        mei_path = self._get_mei()
        if mei_path is None:
            raise SystemExit("MEI interface not found")
        print("connecting to {}".format(mei_path))
        self._mei_obj = os.open(mei_path, os.O_RDWR)

    def connect(self, str_uuid):
        obj_uuid = uuid.UUID(str_uuid)
        array_data = array.array("b", obj_uuid.bytes_le)
        fcntl.ioctl(self._mei_obj,
                    self.IOCTL_MEI_CONNECT_CLIENT,
                    array_data, 1)
        max_length, version = struct.unpack("<IB", array_data.tobytes()[:5])
        return max_length, version

    def write(self, msg_id):
        data_write = struct.pack("I", msg_id)
        result = os.write(self._mei_obj, data_write)
        return result

    def read(self, size):
        data = os.read(self._mei_obj, size)
        return data

    def close(self):
        os.close(self._mei_obj)


def get_mei_firmware_version():
    # This is a fixed uuid to connect to MEI
    # https://github.com/intel/lms/blob/388f115b2aeb3ea11499971c65f828daefd32c47/MEIClient/Include/HECI_if.h#L32
    mei_fw_uuid = "8e6a6715-9abc-4043-88ef-9e39c6f63e0f"
    # This is a request code for firmware version
    mei_fw_ver_req = 0x000002FF
    # The length of firmware version is alway 28
    mei_fw_ver_rep_length = 28
    print("Collecting MEI firmware data through MEI interface..\n")
    try:
        mei_interface = MEI_INTERFACE()
        mei_interface.open()
        mei_interface.connect(mei_fw_uuid)
        mei_interface.write(mei_fw_ver_req)
        raw_fw_ver = mei_interface.read(mei_fw_ver_rep_length)

        str_ver = struct.unpack("4BH2B2HH2B2HH2B2H", raw_fw_ver)
        str_ver = "%d.%d.%d.%d" % (str_ver[5],
                                   str_ver[4],
                                   str_ver[8],
                                   str_ver[7])
        print("MEI firmware version: {}".format(str_ver))
    except Exception as err:
        err_msg = ("Unable to retrieve MEI firmware version"
                   " due to {}".format(err))
        raise SystemExit(err_msg)
    finally:
        if mei_interface._mei_obj is not None:
            mei_interface.close()


if __name__ == "__main__":
    parser = ArgumentParser(prog="MEI Testing Tool",
                            description="This is a tool to help you perform"
                                        " the MEI testing")
    parser.add_argument("--get-version",
                        action="store_true",
                        help="Get the MEI version via MEI interface")
    args = parser.parse_args()
    if args.get_version:
        get_mei_firmware_version()
