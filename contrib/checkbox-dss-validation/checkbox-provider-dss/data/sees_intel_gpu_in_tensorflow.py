import tensorflow as tf
import intel_extension_for_tensorflow as itex


print(tf.__version__)
print(itex.__version__)


devices = tf.config.experimental.list_physical_devices()
if not any("XPU" in device for device in devices):
    raise AssertionError("XPU device not found")
