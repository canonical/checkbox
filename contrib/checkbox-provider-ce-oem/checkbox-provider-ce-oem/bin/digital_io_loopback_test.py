#!/bin/python3
import time
import os
from argparse import ArgumentParser, RawTextHelpFormatter


class DigitalIOSysFsController():

    TEST_STATES = (0, 1)
    ROOT_PATH = "/sys/class/gpio"

    def __init__(self):
        pass

    def run_test(self, out_port, in_port):
        """Launch GPIO test

        Args:
            out_port (str): the gpio port of DO
            in_port (str): the gpio port of DI

        Raises:
            SystemExit: exit with the test result
        """
        print("# GPIO loopback test. out:{}, in:{}".format(out_port, in_port))
        raise SystemExit(not self.loopback_test(out_port, in_port))

    def check_gpio_node(self, port):
        """Check the GPIO port is exists

        Args:
            port (str): the gpio port
        """
        return os.path.exists("{}/gpio{}".format(self.ROOT_PATH, port))

    def set_gpio(self, port, value):
        """Write the value to GPIO port

        Args:
            port (str): the gpio port
            value (str): 0 or 1
        """
        print("# Set GPIO {} value to {}".format(port, value))
        with open("{}/gpio{}/value".format(self.ROOT_PATH, port), "wt") as fp:
            fp.write("{}\n".format(value))

    def read_gpio(self, port):
        """Read the value from GPIO port

        Args:
            port (str): the gpio port

        Returns:
            value (str): the value of gpio port
        """
        with open("{}/gpio{}/value".format(self.ROOT_PATH, port), "r") as fp:
            value = fp.read().strip()
        print("# Read GPIO {}, value is {}".format(port, value))
        return value

    def set_direction(self, port, value):
        """Set direction for GPIO port

        Args:
            port (str): the gpio port
            direction (str): the direction of gpio port
        """
        print("# Set GPIO {} direction to {}".format(port, value))
        with open(
            "{}/gpio{}/direction".format(self.ROOT_PATH, port), "w") as fp:
            fp.write("{}\n".format(value))

    def configure_gpio(self, port, direction):
        """Initial and configure GPIO port

        Args:
            port (str): the gpio port
            direction (str): the direction of gpio port

        Raises:
            IOError: raise error if any issue
        """
        try:
            # Export GPIO
            if not self.check_gpio_node(port):
                with open("{}/export".format(self.ROOT_PATH), "w") as fexport:
                    fexport.write("{}\n".format(port))

            if not self.check_gpio_node(port):
                print("Failed to export GPIO {}\n".format(port))

            # Set direction
            self.set_direction(port, direction)
        except Exception as err:
            IOError("Failed to configure GPIO %s to %s", port, direction)

    def loopback_test(self, out_port, in_port):
        """Launch GPIO loopback test

        Args:
            out_port (str): the gpio port of DO
            in_port (str): the gpio port of DI

        Returns:
            result (bool): the test result
        """
        result = True
        self.configure_gpio(out_port, "out")
        self.configure_gpio(in_port, "in")

        for state in self.TEST_STATES:
            value = self.read_gpio(in_port)
            print("Initial GPIO {} value is {}".format(in_port, value))

            self.set_gpio(out_port, state)
            time.sleep(1)
            real_state = self.read_gpio(in_port)

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
    parser = ArgumentParser(formatter_class=RawTextHelpFormatter)
    parser.add_argument(
        "-o", "--do_pin",
        help="Provide the gpio pin of digital output port."
    )
    parser.add_argument(
        "-i", "--di_pin",
        help="Provide the gpio pin of digital input port."
    )
    args = parser.parse_args()

    obj = DigitalIOSysFsController()
    obj.run_test(args.do_pin, args.di_pin)

if __name__ == "__main__":
    main()
