#!/usr/bin/env python3
#
# Written by:
#   Kunyang Fan <kunyang_fan@aaeon.com.tw>

import os
import sys


def led_brightness_write(led, brightness):
    print("{} brightness -> {}".format(led, brightness), flush=True)
    # test led devices exist
    if not os.path.exists('/sys/class/leds/{}/brightness'.format(led)):
        raise SystemExit('External LED {} not exist'.format(led))

    with open('/sys/class/leds/{}/brightness'.format(led), 'wt') as f:
        f.write('{}\n'.format(brightness))


def led_arrays(model_name):
    led_data = os.path.expandvars(
        '$PLAINBOX_PROVIDER_DATA/led-brightness.{}.in'.format(model_name))
    if not os.path.exists(led_data):
        raise SystemExit(
            "ERROR: no led information found at: {}".format(led_data))
    with open(led_data, 'r') as f:
        for line in f:
            if line.startswith('#'):
                continue
            yield line.strip()


def main():
    if len(sys.argv) < 3:
        raise SystemExit('Usage: led_syfs_brightness.py MODEL_NAME on/off')
    model_name = sys.argv[1]
    if sys.argv[2] == 'on':
        brightness = 255
    else:
        brightness = 0
    for led in led_arrays(model_name):
        led_brightness_write(led, brightness)


if __name__ == '__main__':
    main()
