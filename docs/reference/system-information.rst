System information
==================

Checkbox collects telemetry about the DUT transparently during a test run.
This debug information is stored in the ``system_information`` field of the
``submission.json`` report and can help investigate failures after the run has
finished.

Each collector stores the version of the tool that produced the data, whether
collection succeeded, and either the parsed payload or the command failure
details.

bios
----

The ``bios`` collector records firmware metadata from DMI sysfs. The payload
contains the BIOS date, release, vendor, version, and whether the system booted
in UEFI or legacy BIOS mode.

debian_packages
---------------

The ``debian_packages`` collector records the Debian package inventory reported
by ``dpkg``. Each entry contains the package name, installed version, and
architecture, making the tested software baseline explicit.

distribution
------------

The ``distribution`` collector records operating-system identity from
``os-release``. It captures fields such as distributor name, human-readable
description, release number, and codename.

image_info
----------

The ``image_info`` collector records Canonical OEM image metadata when it is
available. It extracts project, series, kernel flavour or build identifier, and
the corresponding OEM share URL from the image DCD string.

inxi
----

The ``inxi`` collector records a broad hardware and operating-system inventory
from the bundled ``inxi`` tool. It includes platform details such as CPU,
graphics, storage, networking, sensors, partitioning, and driver information.

journalctl
----------

The ``journalctl`` collector records recent systemd journal entries as JSON
objects. It keeps logs from the last three days and caps the amount collected to
avoid excessive memory use on constrained devices.

kernel_cmdline
--------------

The ``kernel_cmdline`` collector records the exact boot command line passed to
the running kernel. This includes parameters such as the boot image, root
device, feature flags, debug options, and hardware workarounds.

kernel_modules
--------------

The ``kernel_modules`` collector records the modules currently loaded in the
kernel. For each module it includes the name, size, instance count,
dependencies, load state, and kernel memory offset.

machine_manifest
----------------

The ``machine_manifest`` collector records the Checkbox manifest.

memory
------

The ``memory`` collector records memory totals parsed from ``/proc/meminfo``.
The payload includes total RAM and total swap, expressed in bytes.

snaps
-----

The ``snaps`` collector records the installed snap packages reported by snapd.
It captures the snap environment present during the run, including package
metadata such as names, revisions, channels, confinement, and versions.

udev_devices
------------

The ``udev_devices`` collector records the udev device database. It includes
low-level devices visible to the operating system, their sysfs paths,
subsystems, properties, and hardware identifiers parsed for buses such as PCI,
USB, ACPI, input, HID, SCSI, and platform devices.

uname
-----

The ``uname`` collector records kernel and host identity from Python's platform
interfaces. It includes the operating-system name, hostname, kernel release,
kernel build version, and machine architecture.
