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

+-----------+-------------+-------------+-------------------+-------------+----------------+
| 6lowpan   | eeprom      | hibernate   | memory            | security    | touchscreen    |
+-----------+-------------+-------------+-------------------+-------------+----------------+
| acpi      | esata       | i2c         | miscellanea       | self        | tmp            |
+-----------+-------------+-------------+-------------------+-------------+----------------+
| audio     | ethernet    | image       | mobilebroadband   | serial      | ubuntucore     |
+-----------+-------------+-------------+-------------------+-------------+----------------+
| benchmarks| expresscard | info        | monitor           | smoke       | usb            |
+-----------+-------------+-------------+-------------------+-------------+----------------+
| bluetooth | fingerprint | input       | networking        | snapd       | virtualization |
+-----------+-------------+-------------+-------------------+-------------+----------------+
| camera_   | firewire    | install     | npu               | socketcan   | watchdog       |
+-----------+-------------+-------------+-------------------+-------------+----------------+
| canary    | firmware    | kernel-snap | nvdimm            | submission  | wireless       |
+-----------+-------------+-------------+-------------------+-------------+----------------+
| codecs    | fscrypt     | keys        | oob-management    | suspend     | wwan           |
+-----------+-------------+-------------+-------------------+-------------+----------------+
| cpu       | gadget      | led         | optical           | tpm         |                |
+-----------+-------------+-------------+-------------------+-------------+----------------+
| disk      | gpio        | location    | power-management  | thunderbolt |                |
+-----------+-------------+-------------+-------------------+-------------+----------------+
| dock      | graphics    | mediacard   | rtc               | touchpad    |                |
+-----------+-------------+-------------+-------------------+-------------+----------------+

.. _camera: units/camera/README.rst
