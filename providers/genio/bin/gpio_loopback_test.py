#!/usr/bin/env python3
# This file is part of Checkbox.
#
# Copyright 2024 Canonical Ltd.
# Authors:
#   Patrick Chang <patrick.chang@canonical.com>
#   Fernando Bravo <fernando.bravo.hernandez@canonical.com>
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

import time
import os
from argparse import ArgumentParser, RawTextHelpFormatter


class GPIOSysFsController:

    TEST_STATES = (0, 1)
    ROOT_PATH = "/sys/class/gpio"

    def __init__(self):
        pass

    def get_gpio_base_number(self):
        """Get the base number of GPIO chip"""
        print("Get GPIO Chips info")
        with open("/sys/kernel/debug/gpio", "r") as fp:
            value = fp.read().strip()
            print(value)
            gpiochips = [i for i in value.split("\n") if "gpiochip" in i]
            gpiochip_base_number_dict = {}
            for gc in gpiochips:
                gc_splits = gc.split(" ")
                gpiochip = gc_splits[0].replace(":", "")
                base_number = gc_splits[2].split("-")[0]
                gpiochip_base_number_dict.update({gpiochip: base_number})

            print("\n\nGPIO chip base number mapping:")
            print(gpiochip_base_number_dict)
            return gpiochip_base_number_dict

    def run_test(
        self,
        output_gpio_chip_number,
        input_gpio_chip_number,
        physical_output_port,
        physical_input_port,
        gpio_output_pin,
        gpio_input_pin,
    ):
        """Launch GPIO test

        Args:
            output_gpio_chip_number (str): the number of output gpio chip
                e.g. 0
            input_gpio_chip_number (str): the number of input gpio chip
                e.g. 3
            physical_output_port (str): the name or physical port number for
                output, it's used to provide a human readable content only
                e.g. J3, pin26
            physical_input_port (str): the name or physical port number for
                input, it's used to provide a human readable content only
                e.g. J7, pin27
            gpio_output_pin (str): the gpio pin number of output. This value
                means the real pin number of target GPIO. You can get this
                information from Schematic or User Guide of the DUT
            gpio_input_pin (str): the gpio pin number of intput. This value
                means the real pin number of target GPIO. You can get this
                information from Schematic or User Guide of the DUT

        Raises:
            SystemExit: exit with the test result
        """
        base_number_mapping = self.get_gpio_base_number()
        output_base_number = int(
            base_number_mapping["gpiochip{}".format(output_gpio_chip_number)]
        )
        input_base_number = int(
            base_number_mapping["gpiochip{}".format(input_gpio_chip_number)]
        )
        output_pin_number = output_base_number + int(gpio_output_pin)
        input_pin_number = input_base_number + int(gpio_input_pin)
        print("\nOutput Base Number: {}".format(output_base_number))
        print("Input Base Number: {}".format(input_base_number))
        print(
            "Physical output port: {}, GPIO number: {}".format(
                physical_output_port, gpio_output_pin
            )
        )
        print(
            "Physical input port: {}, GPIO number {}".format(
                physical_input_port, gpio_input_pin
            )
        )
        print(
            "Output Pin Number: {} + Base Number = {}".format(
                gpio_output_pin, output_pin_number
            )
        )
        print(
            "Input Pin Number: {} + Base Number = {}".format(
                gpio_input_pin, input_pin_number
            )
        )
        print("\n# Start GPIO loopback test")
        if not self.loopback_test(output_pin_number, input_pin_number):
            raise SystemExit("Failed: GPIO loopback test failed")

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
            "{}/gpio{}/direction".format(self.ROOT_PATH, port), "w"
        ) as fp:
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
                raise SystemExit("Failed to export GPIO {}\n".format(port))

            # Set direction
            self.set_direction(port, direction)
        except Exception as err:
            raise IOError(
                "{} \nError: Failed to configure GPIO {} to {}".format(
                    err, port, direction
                )
            )

    def loopback_test(self, out_port, in_port):
        """Launch GPIO loopback test

        Args:
            out_port (str): the gpio port of output
            in_port (str): the gpio port of input

        Returns:
            result (bool): the test result
        """
        result = True
        self.configure_gpio(out_port, "out")
        self.configure_gpio(in_port, "in")

        for state in self.TEST_STATES:
            print("Try to send and receive {}".format(state))
            value = self.read_gpio(in_port)
            print(
                "The initial input GPIO {}'s value is {}".format(
                    in_port, value
                )
            )

            self.set_gpio(out_port, state)
            time.sleep(1)
            real_state = self.read_gpio(in_port)

            if int(real_state) != state:
                str_match = "mismatch"
                result = False
            else:
                str_match = "match"
            print(
                "# Digital state {}. expected: {} real: {}\n".format(
                    str_match, state, real_state
                )
            )
        return result


def main():
    parser = ArgumentParser(formatter_class=RawTextHelpFormatter)
    parser.add_argument(
        "-oc",
        "--output_gpio_chip_number",
        help="Provide the target gpio chip number for output.",
        default=0,
    )
    parser.add_argument(
        "-ic",
        "--input_gpio_chip_number",
        help="Provide the target gpio chip number for input.",
        default=0,
    )
    parser.add_argument(
        "-po",
        "--physical_output_port",
        help=(
            "Provide the physical output port number/name."
            " It's used to provide a human readable content only"
        ),
    )
    parser.add_argument(
        "-pi",
        "--physical_input_port",
        help=(
            "Provide the physical input port number/name."
            " It's used to provide a human readable content only"
        ),
    )
    parser.add_argument(
        "-go",
        "--gpio_output_pin",
        help=(
            "Provide the output gpio pin number. You can get this information"
            " from Schematic or User Guide of the DUT"
        ),
    )
    parser.add_argument(
        "-gi",
        "--gpio_input_pin",
        help=(
            "Provide the output gpio pin number. You can get this information"
            " from Schematic or User Guide of the DUT"
        ),
    )
    args = parser.parse_args()

    obj = GPIOSysFsController()
    obj.run_test(
        args.output_gpio_chip_number,
        args.input_gpio_chip_number,
        args.physical_output_port,
        args.physical_input_port,
        args.gpio_output_pin,
        args.gpio_input_pin,
    )


if __name__ == "__main__":
    main()
