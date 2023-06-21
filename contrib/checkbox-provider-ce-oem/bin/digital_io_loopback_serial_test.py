#!/bin/python3
import serial
import time
import binascii
from argparse import ArgumentParser


def calculate_crc(*data):
    crc_sum = 0x00
    for byte in data:
        crc_sum ^= byte
        for _ in range(0, 8):
            tmp_int = 7 if (crc_sum & 0x80) else 0
            crc_sum = (crc_sum << 1) ^ tmp_int

            if crc_sum > 255:
                crc_sum -= 256
    return crc_sum


class DigitalIOSerialController():

    TEST_STATES = (0, 1)
    # DIGITAL_IN_PINS = [6, 7, 8, 9]
    # DIGITAL_OUT_PINS = [2, 3, 4, 5]
    PREFIX_BYTE = 68 # equal to 0x44

    def __init__(self, port):
        self.conn = serial.Serial("/dev/{}".format(port), timeout=2)

    def generate_message(self, *data):
        """Generate command with CRC checksum

        Args:
            *data (list): paritial bytes to communicate to serial console

        Returns:
            messages (bytearray): a command to communicate to serial console
        """
        crc_sum = calculate_crc(*data)
        data = list(data)
        data.append(crc_sum)

        return bytearray(data)

    def read_digital_in(self, pin_num):
        """Read the value from digital input port
        Will issue a command to serial console with following format
        {function_byte} {pin_byte} {crc_sum}

        Args:
            pin_num (str): the port ot DI

        Returns:
            value (str): the value of DI
        """
        print("\n# Read value from register byte {}..".format(pin_num))
        msg = self.generate_message(self.PREFIX_BYTE, pin_num)
        self.conn.write(msg)
        resp = self.conn.read(16)
        value = binascii.b2a_hex(resp, " ").decode("utf8").split(" ")[2]

        return value

    def write_digital_out(self, pin_num, value):
        """Write the value to digital output port
        Will issue a command to serial console with following format
        {function_byte} {pin_byte} {value} {crc_sum}

        Args:
            pin_num (str): the port ot DO
            value (str): the value will write to DO

        Returns:
            N/A
        """
        print("\n# Write {} to register byte {}..".format(value, pin_num))
        msg = self.generate_message(
                  self.PREFIX_BYTE, pin_num, value)
        self.conn.write(msg)
        resp = self.conn.read(16)
        print(resp)

    def run_test(self, out_port, in_port):
        """Launch Digital I/O test

        Args:
            out_port (str): the port of DO
            in_port (str): the port of DI

        Raises:
            SystemExit: Exit the function with the test result
        """
        print(
            "# Digital I/O loopback test. out:{}, in:{}".format(
                out_port, in_port)
        )
        raise SystemExit(not self.loopback_test(out_port, in_port))

    def loopback_test(self, out_port, in_port):
        """Launch Digital I/O loopback test

        Args:
            out_port (str): the pin byte of DO
            in_port (str): the pin byte of DI

        Returns:
            result (bool): test results
        """
        result = True

        for state in self.TEST_STATES:
            value = self.read_digital_in(in_port)
            print("Initial DI value {} is {}".format(in_port, value))

            self.write_digital_out(out_port, state)
            time.sleep(1)
            real_state = self.read_digital_in(in_port)

            if int(real_state) != state:
                str_match = "mismatch"
                result = False
            else:
                str_match = "match"
            print("# Digital state {}. expected: {} real: {}\n".format(
                str_match, state, real_state)
            )
        return result

def main():
    parser = ArgumentParser()
    parser.add_argument(
        "-o", "--do_byte",
        type=int,
        required=True,
        help="Provide the register byte of digital output port."
    )
    parser.add_argument(
        "-i", "--di_byte",
        type=int,
        required=True,
        help="Provide the register byte of digital input port."
    )
    parser.add_argument(
        "-s", "--serial_port",
        required=True,
        help="Provide the serial console port to communicate with."
    )
    args = parser.parse_args()

    obj = DigitalIOSerialController(args.serial_port)
    obj.run_test(args.do_byte, args.di_byte)

if __name__ == "__main__":
    main()
