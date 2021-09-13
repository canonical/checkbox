#!/bin/sh
if ! (udevadm info --export-db | grep -q iio_device); then
   echo "Screen orientation check PASSED:"
   echo "no iio_device found in this device, therefore rotation should not happen."
   exit 0
fi

if dbus-send --system --print-reply --dest=net.hadess.SensorProxy \
  /net/hadess/SensorProxy \
  org.freedesktop.DBus.Properties.Get string:net.hadess.SensorProxy string:HasAccelerometer |
  grep -q "boolean true"; then
  echo "Screen orientation check FAILED:"
  echo "this device has an accelerometer that needs to be disabled."
  echo "==="
  # list IIO devices for reference
  echo "udevadm info /sys/bus/iio/devices/iio*"
  udevadm info /sys/bus/iio/devices/iio*
  exit 1
fi

echo "Screen orientation check PASSED:"
echo "Accelerometer is not enabled."
