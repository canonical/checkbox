Checkbox Configs
^^^^^^^^^^^^^^^^

Configuration values resolution order
=====================================

The directories that are searched for config files are:
``/etc/xdg/``
``~/.config/``

Invoking ``checkbox-cli`` (without launcher)
--------------------------------------------
Assumed config file name is ``checkbox.conf``

Invoking launcher
-----------------
The file name to look for is specified using ``config_filename`` variable from
launcher, from the ``[config]`` section. If it's not present, ``checkbox.conf``
is used.

Note that if same configuration variable is defined in more than one place, the
value resolution is as follows:

1. config file from ``~/.config``
2. launcher being invoked (only the new syntax launchers)
3. config file from ``/etc/xdg``

Configs with Checkbox Remote
============================

When the Checkbox Slave starts, it looks for config files in the same places
that local Checkbox session would look (on the Slave side).
If the Master uses a Launcher, then the values from that Launcher take
precedence over the values from configs on the Slave side.

Example:

::

    # checkbox.conf on the Slave

    [environment]
    FOO = 12
    BAR = 6

::

    # Launcher used by the master

    # (...)
    [environment]
    FOO = 42

A Checkbox job that runs ``echo $FOO $BAR`` would print ``42 6``

Note that ``BAR`` is still available even though Master used Launcher that did
not define it.
