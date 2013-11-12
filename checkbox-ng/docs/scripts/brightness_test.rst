brightness_test
===============

This script tests the brightness of the systems backlight can be changed by using the kernel interfaces in /sys/class/backlight. There may be more than one interface to choose from, so the correct interface to use is selected by using the heuristic prescribed in https://www.kernel.org/doc/Documentation/ABI/stable/sysfs-class-backlight. The brightness is manipulated by updating the brightness file of the interface and the actual_brightness file is checked to see if the value was modified to the brightness selected.
