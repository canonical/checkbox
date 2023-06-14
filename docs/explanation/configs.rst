Checkbox Configs
^^^^^^^^^^^^^^^^

Configuration values resolution order
=====================================

The directories that are searched for config files are:

* ``/etc/xdg/``
* ``~/.config/``
* ``$SNAP_DATA`` if run as a snap

Invoking ``checkbox-cli`` (without launcher)
--------------------------------------------

By default, Checkbox will look for a config file named ``checkbox.conf`` in the
directories mentioned above.

Invoking launcher
-----------------

If using a :ref:`launcher<launcher>`, the file name to look for is specified
using the ``config_filename`` variable from the ``[config]`` section (see
:ref:`launcher_config` for more information). If it's not present,
``checkbox.conf`` is used.

Note that if same configuration variable is defined in more than one place, the
value resolution is as follows:

1. launcher being invoked
2. config file from ``~/.config``
3. config file from ``/etc/xdg``
4. config file from ``$SNAP_DATA``

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
