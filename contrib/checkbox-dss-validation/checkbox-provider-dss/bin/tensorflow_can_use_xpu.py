#!/usr/bin/env python3

import intel_extension_for_tensorflow as itex
import tensorflow as tf
import jupyter


devices = tf.config.experimental.list_physical_devices()
xpu_found = False
for device_str in devices:
   if "XPU" in device_str:
       xpu_found = True
       break

assert xpu_found, "XPU not found"
