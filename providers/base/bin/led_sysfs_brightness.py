#!/usr/bin/env python3
#
# Written by:
#   Kunyang Fan <kunyang_fan@aaeon.com.tw>

import os
import sys


def led_brightness_write(led, brightness):
    print(f"{led} brightness -> {brightness}", flush=True)
    # test led devices exist
    if not os.path.exists(f"/sys/class/leds/{led}/brightness"):
        raise SystemExit(f"External LED {led} not exist")

    with open(f"/sys/class/leds/{led}/brightness", "w") as f:
        f.write(f"{brightness}\n")


def led_arrays(model_name):
    led_data = os.path.expandvars(
        f"$PLAINBOX_PROVIDER_DATA/led-brightness.{model_name}.in"
    )
    if not os.path.exists(led_data):
        raise SystemExit(f"ERROR: no led information found at: {led_data}")
    with open(led_data) as f:
        for line in f:
            if line.startswith("#"):
                continue
            yield line.strip()


def main():
    if len(sys.argv) < 3:
        raise SystemExit("Usage: led_syfs_brightness.py MODEL_NAME on/off")
    model_name = sys.argv[1]
    if sys.argv[2] == "on":
        brightness = 255
    else:
        brightness = 0
    for led in led_arrays(model_name):
        led_brightness_write(led, brightness)


if __name__ == "__main__":
    main()
