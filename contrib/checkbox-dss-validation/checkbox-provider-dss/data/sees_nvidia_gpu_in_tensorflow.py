import tensorflow as tf


print(tf.__version__)


devices = tf.config.experimental.list_physical_devices("GPU")
if not any("GPU" in device for device in devices):
    raise AssertionError("CUDA device not found")
