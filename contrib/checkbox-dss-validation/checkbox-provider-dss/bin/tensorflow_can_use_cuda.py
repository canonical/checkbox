#!/usr/bin/env python3

import tensorflow as tf

devices = tf.config.experimental.list_physical_devices()
for device_str in devices:
    if "CUDA" in device_str:
        break
else:
    raise AssertionError("CUDA device not found")
