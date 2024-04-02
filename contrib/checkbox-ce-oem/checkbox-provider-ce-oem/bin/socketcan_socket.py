import socket
import struct
import sys
import json
import subprocess
import logging
import contextlib
from enum import Enum


def init_logger():
    """
    Set the logger to log DEBUG and INFO to stdout, and
    WARNING, ERROR, CRITICAL to stderr.
    """
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    logger_format = "%(asctime)s %(levelname)-8s %(message)s"
    date_format = "%Y-%m-%d %H:%M:%S"

    # Log DEBUG and INFO to stdout, others to stderr
    stdout_handler = logging.StreamHandler(sys.stdout)
    stdout_handler.setFormatter(logging.Formatter(logger_format, date_format))

    stderr_handler = logging.StreamHandler(sys.stderr)
    stderr_handler.setFormatter(logging.Formatter(logger_format, date_format))

    stdout_handler.setLevel(logging.DEBUG)
    stderr_handler.setLevel(logging.WARNING)

    # Add a filter to the stdout handler to limit log records to
    # INFO level and below
    stdout_handler.addFilter(lambda record: record.levelno <= logging.INFO)

    root_logger.addHandler(stderr_handler)
    root_logger.addHandler(stdout_handler)

    return root_logger


class CANSocket():

    # struct module format strings for CAN packets
    # Normal format:
    #   <   little-endian
    #   I   unsigned int (4)    : CAN-ID + EFF/RTR/ERR Flags
    #   B   unsigned char (1)   : Data length
    #   3x  padding (3 * 1)     : -
    #   8s  char array (8 * 1)  : Data
    FORMAT = "<IB3x8s"
    # Flexible Data (FD) rate format:
    #   <    little-endian
    #   I    unsigned int (4)    : CAN-ID + EFF/RTR/ERR Flags
    #   B    unsigned char (1)   : Data length
    #   B    unsigned char (1)   : FD Flags
    #   2x   padding (2 * 1)     : -
    #   64s  char array (64 * 1) : Data
    FD_FORMAT = "<IBB2x64s"

    CAN_MTU = struct.Struct(FORMAT).size
    CANFD_MTU = struct.Struct(FD_FORMAT).size

    # Socket options from <linux/can/raw.h>
    CAN_RAW_FILTER = 1         # set 0 .. n can_filter(s)
    CAN_RAW_ERR_FILTER = 2     # set filter for error frames
    CAN_RAW_LOOPBACK = 3       # local loopback (default:on)
    CAN_RAW_RECV_OWN_MSGS = 4  # receive my own msgs (default:off)
    CAN_RAW_FD_FRAMES = 5      # allow CAN FD frames (default:off)
    CAN_RAW_JOIN_FILTERS = 6   # all filters must match to trigger

    def __init__(self, interface=None, fdmode=False, verbose=False):
        self.sock = socket.socket(socket.PF_CAN,  # protocol family
                                  socket.SOCK_RAW,
                                  socket.CAN_RAW)
        self._fdmode = fdmode
        self._verbose = verbose
        if interface is not None:
            self._bind(interface)

    def __enter__(self):
        return self

    def __exit__(self):
        self.close()

    def close(self):
        self.sock.close()

    def _bind(self, interface):
        self.sock.bind((interface,))
        if self._fdmode:  # default is off
            self.sock.setsockopt(
                socket.SOL_CAN_RAW, self.CAN_RAW_FD_FRAMES, 1)

    def struct_packet(
            self, can_id, data, id_flag=0, fd_flag=0, fd_frame=False):
        """
        Generate CAN frame binary data

        Args:
            can_id (int):   CAN ID
            data (byte):    CAN data packet
            id_flag (int):  CAN ID flag
            fd_flag (int):  additional FD flag
            fd_frame (bol): FD frame data

        Return:
            can_packet(bytes): a bytes object of CAN packet
        """
        can_id = can_id | id_flag
        if fd_frame:
            can_packet = struct.pack(
                self.FD_FORMAT,
                can_id,
                len(data),
                fd_flag,
                data
            )
        else:
            can_packet = struct.pack(
                self.FORMAT,
                can_id,
                len(data),
                data
            )

        return can_packet

    def destruct_packet(self, can_packet):
        nbytes = len(can_packet)
        logging.debug("Destruct CAN packet..")
        if nbytes == self.CANFD_MTU:
            logging.debug("Got CAN FD frame..")
            can_id, length, fd_flags, data = struct.unpack(
                    self.FD_FORMAT, can_packet)
        elif nbytes == self.CAN_MTU:
            logging.debug("Got Classical CAN frame..")
            can_id, length, data = struct.unpack(
                    self.FORMAT, can_packet)
        else:
            logging.error("Got an unexpected data with length %s", nbytes)
            return (None, None)

        can_id &= socket.CAN_EFF_MASK
        if can_id and data[:length] and self._verbose:
            logging.debug('CAN packet data')
            logging.debug('  ID  : %s', '{:x}'.format(can_id))
            logging.debug('  Data: %s', data[:length].hex())

        return (can_id, data[:length])

    def send(self, can_packet, timeout=None):
        """
        Send CAN frame data through CANSocket

        Args:
            can_packet: CAN data packet
            timeout:    timeout for sending packet

        Raises:
            SystemExit: if any error occurs during sending CAN frame
        """
        try:
            if timeout:
                self.sock.settimeout(timeout)
            self.sock.send(can_packet)
            self.sock.settimeout(None)
        except OSError as e:
            logging.error(e)
            if e.errno == 90:
                raise SystemExit(
                    'ERROR: interface does not support FD Mode')
            else:
                raise SystemExit('ERROR: OSError on attempt to send')

    def recv(self, timeout=None):
        """
        Receive data from CANSocket

        Args:
            timeout:    timeout for sending packet

        Raises:
            SystemExit: if any error occurs during receiving CAN frame
        """
        data_struct = self.CANFD_MTU if self._fdmode else self.CAN_MTU
        try:
            if timeout:
                self.sock.settimeout(timeout)
            can_pkt = self.sock.recv(data_struct)
            self.sock.settimeout(None)
            return can_pkt
        except TimeoutError:
            logging.error("Failed to receive within %ss", timeout)
            return None
        except OSError as e:
            logging.error(e)
            if e.errno == 90:
                raise SystemExit(
                    'ERROR: interface does not support FD Mode')
            else:
                raise SystemExit('ERROR: OSError on attempt to receive')


class CANLinkState(Enum):
    """CAN Link State

    Reference link:
    https://github.com/torvalds/linux/blob/master/include/uapi/linux/can/netlink.h#L69
    """
    ERROR_ACTIVE = "ERROR-ACTIVE"
    ERROR_WARNING = "ERROR-WARNING"
    ERROR_PASSIVE = "ERROR-PASSIVE"
    BUS_OFF = "BUS-OFF"
    STOPPED = "STOPPED"
    SLEEPING = "SLEEPING"
    MAX = "MAX"


class CANLinkInfo():
    """
    CAN Link Information
    """
    def __init__(self, dev):
        self._can_dev = dev
        self._can_raw_data = None
        self._raw_data = None
        self.get_link_info()

    def get_link_info(self):

        ret = subprocess.run(
            "ip -d -j link show {}".format(self._can_dev),
            shell=True,
            capture_output=True
        )
        try:
            json_data = json.loads(ret.stdout.decode("utf-8").strip("\n"))
            self._raw_data = json_data[0]
            if json_data[0]["linkinfo"]["info_kind"] == "can":
                self._can_raw_data = json_data[0]["linkinfo"]["info_data"]
        except Exception as e:
            logging.error("Unexpected error: %s", e)

    @property
    def bittiming(self):
        if self._can_raw_data:
            return self._can_raw_data.get("bittiming", {})

    @property
    def data_bittiming(self):
        if self._can_raw_data:
            return self._can_raw_data.get("data_bittiming", {})

    @property
    def restart_ms(self):
        if self._can_raw_data:
            return self._can_raw_data["restart_ms"]

    @property
    def state(self):
        if self._can_raw_data:
            return self._can_raw_data["state"]

    @property
    def operate_state(self):
        return self._raw_data["operstate"]

    @property
    def mtu(self):
        return self._raw_data["mtu"]

    def configure(self, bittiming, data_bittiming={}, restart_ms=0, fd=False):
        """
        Configure the CAN attribute

        Args:
            bittiming (dict): bitrate attributes
            data_bittiming (dict, optional):
                data bitrate attributes. Defaults to {}.
            restart_ms (int, optional):
                restart timeout. Defaults to 0.
            fd (bool, optional):
                CAN FD mode. Defaults to False.
        """
        supported_attributes = ["bitrate", "sample_point"]
        self.get_link_info()

        cmd_str = ""
        for key, value in bittiming.items():
            if key in supported_attributes:
                cmd_str = "{} {} {}".format(cmd_str,
                                            key.replace("_", "-"),
                                            value)

        for key, value in data_bittiming.items():
            if key in supported_attributes:
                cmd_str = "{} d{} {}".format(cmd_str,
                                             key.replace("_", "-"),
                                             value)
        mtu = 16
        if fd:
            mtu = 72
            cmd_str = "{} fd on".format(cmd_str)

        if restart_ms:
            cmd_str = "{} restart-ms {}".format(cmd_str, restart_ms)

        if cmd_str:
            cmd_str = "ip link set {} mtu {} type can {}".format(
                self._can_dev, mtu, cmd_str
            )
            logging.debug(
                "configure CAN %s device - '%s'", self._can_dev, cmd_str
            )
            subprocess.run(cmd_str, shell=True)
        else:
            logging.debug("CAN attribute has no difference")

    def enable_link(self):
        """
        Enable CAN Link
        """
        logging.debug("enable CAN %s device", self._can_dev)
        subprocess.run("ip link set {} up".format(self._can_dev), shell=True)

    def disable_link(self):
        """
        Disable CAN Link
        """
        logging.debug("disable CAN %s device", self._can_dev)
        subprocess.run(
            "ip link set {} down".format(self._can_dev), shell=True)


@contextlib.contextmanager
def prepare_can_link(can_dev, fd_mode=False):
    try:
        can_link = CANLinkInfo(can_dev)
        original_bitrate = can_link.bittiming
        original_dbitrate = can_link.data_bittiming
        original_restart_ms = can_link.restart_ms
        original_op_state = can_link.operate_state
        original_mtu = can_link.mtu

        if can_link.operate_state == "UP":
            can_link.disable_link()

        if fd_mode:
            can_link.configure(
                bittiming={"bitrate": 1000000},
                data_bittiming={"bitrate": 2000000},
                restart_ms=30000,
                fd=fd_mode
            )
        else:
            can_link.configure(
                bittiming={"bitrate": 1000000},
                data_bittiming={},
                restart_ms=30000
            )

        can_link.enable_link()
        yield can_link

    finally:
        print("Restore {} configuration".format(can_dev))
        can_link.disable_link()
        if original_mtu == 72:
            can_link.configure(
                bittiming=original_bitrate,
                data_bittiming=original_dbitrate,
                restart_ms=original_restart_ms,
                fd=fd_mode
            )
        else:
            can_link.configure(
                bittiming=original_bitrate,
                restart_ms=original_restart_ms
            )

        if original_op_state == "UP":
            can_link.enable_link()
