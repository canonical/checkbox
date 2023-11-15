Checkbox base provider
=======================

The Checkbox base provider contains a series of tests used in the tool and
other providers. The base tests cover a wide range and are used to test the
core functionalities of the devices.

The `bin/` and `src/`  contain several `.py`, `.sh` and `.cpp` files that are
the base for tests used by Checkbox. The specific Checkbox units are located
under the units folder.

Base Provider Units
###################

+------------+-------------+-------------+------------------+-------------+----------------+
| 6lowpan    | eeprom      | i2c         | miscellanea      | serial      | ubuntucore     |
+------------+-------------+-------------+------------------+-------------+----------------+
| acpi       | esata       | image       | mobilebroadband  | smoke       | usb            |
+------------+-------------+-------------+------------------+-------------+----------------+
| audio      | ethernet    | info        | monitor          | snapd       | virtualization |
+------------+-------------+-------------+------------------+-------------+----------------+
| benchmarks | expresscard | input       | networking       | socketcan   | watchdog       |
+------------+-------------+-------------+------------------+-------------+----------------+
| bluetooth  | fingerprint | install     | nvdimm           | stress      | wireless       |
+------------+-------------+-------------+------------------+-------------+----------------+
| camera_    | firewire    | kernel-snap | oob-management   | submission  | wwan           |
+------------+-------------+-------------+------------------+-------------+----------------+
| canary     | firmware    | keys        | optical          | suspend     | zapper         |
+------------+-------------+-------------+------------------+-------------+----------------+
| codecs     | gadget      | led         | power-management | thunderbolt |                |
+------------+-------------+-------------+------------------+-------------+----------------+
| cpu        | gpio        | location    | rtc              | touchpad    |                |
+------------+-------------+-------------+------------------+-------------+----------------+
| disk       | graphics    | mediacard   | security         | touchscreen |                |
+------------+-------------+-------------+------------------+-------------+----------------+
| dock       | hibernate   | memory      | self             | tpm         |                |
+------------+-------------+-------------+------------------+-------------+----------------+

.. _camera: units/camera/README.rst
