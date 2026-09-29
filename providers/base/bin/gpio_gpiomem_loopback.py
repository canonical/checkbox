#!/usr/bin/env python3
# Copyright 2019 Canonical Ltd.
# All rights reserved.
#
# Written by:
#   Jonathan Cave <jonathan.cave@canonical.com>

import RPi.GPIO as GPIO

import os
import sys
import time


def loopback_test(out_lane, in_lane):
    print(f"{out_lane} -> {in_lane}", flush=True)
    out_lane = int(out_lane)
    in_lane = int(in_lane)
    GPIO.setup(out_lane, GPIO.OUT, initial=GPIO.LOW)
    GPIO.setup(in_lane, GPIO.IN)
    for i in range(6):
        GPIO.output(out_lane, i % 2)
        time.sleep(0.5)
        if GPIO.input(in_lane) != (i % 2):
            raise SystemExit(
                f"Failed loopback test out: {out_lane} in: {in_lane}"
            )
        time.sleep(0.5)


def gpio_pairs(model_name):
    gpio_data = os.path.expandvars(
        f"$PLAINBOX_PROVIDER_DATA/gpio-loopback.{model_name}.in"
    )
    if not os.path.exists(gpio_data):
        raise SystemExit(f"ERROR: no gpio information found at: {gpio_data}")
    with open(gpio_data) as f:
        for line in f:
            if line.startswith("#"):
                continue
            yield line.strip().split(",")


def main():
    if len(sys.argv) < 2:
        raise SystemExit("Usage: gpio_loopback.py MODEL_NAME")
    model_name = sys.argv[1]

    print(f"Using RPi.GPIO module {GPIO.VERSION}")
    GPIO.setmode(GPIO.BCM)
    GPIO.setwarnings(False)

    for pair in gpio_pairs(model_name):
        loopback_test(*pair)

    GPIO.cleanup()


if __name__ == "__main__":
    main()
