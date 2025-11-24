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
| 6lowpan   | eeprom      | hibernate   | memory            | self        | tmp            |
+-----------+-------------+-------------+-------------------+-------------+----------------+
| acpi      | esata       | i2c         | miscellanea       | serial      | ubuntucore     |
+-----------+-------------+-------------+-------------------+-------------+----------------+
| audio     | ethernet    | image       | mobilebroadband   | smoke       | usb            |
+-----------+-------------+-------------+-------------------+-------------+----------------+
| benchmarks| expresscard | info        | monitor           | snapd       | virtualization |
+-----------+-------------+-------------+-------------------+-------------+----------------+
| bluetooth | fingerprint | input       | networking        | socketcan   | watchdog       |
+-----------+-------------+-------------+-------------------+-------------+----------------+
| camera_   | firewire    | install     | nvdimm            | submission  | wireless       |
+-----------+-------------+-------------+-------------------+-------------+----------------+
| canary    | firmware    | kernel-snap | oob-management    | suspend     | wwan           |
+-----------+-------------+-------------+-------------------+-------------+----------------+
| codecs    | fscrypt     | keys        | optical           | tpm         |                |
+-----------+-------------+-------------+-------------------+-------------+----------------+
| cpu       | gadget      | led         | power-management  | thunderbolt |                |
+-----------+-------------+-------------+-------------------+-------------+----------------+
| disk      | gpio        | location    | rtc               | touchpad    |                |
+-----------+-------------+-------------+-------------------+-------------+----------------+
| dock      | graphics    | mediacard   | security          | touchscreen |                |
+-----------+-------------+-------------+-------------------+-------------+----------------+

.. _camera: units/camera/README.rst
