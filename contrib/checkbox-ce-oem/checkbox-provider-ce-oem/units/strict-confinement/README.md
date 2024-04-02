# Introduction to snap strict confinement test jobs
The test jobs under this category are intended to test the Ubuntu Core
functions in snap strict confinement mode. This means snap needs the right
to access system resources by connecting interfaces.
Running script *env_setup.py* to install and connect the interface before
testing.

## id: dbus-{cold|warm}-boot-loop-reboot
Those jobs call dbus command to let system go into cold or warm reboot status.
And it rely on the snapd interface *shutdown*.
