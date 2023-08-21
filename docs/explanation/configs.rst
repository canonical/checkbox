.. _checkbox_configs:

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

Check the configuration
=======================

The values resolution order and the fact that configurations can be stored in
so many different places may bring confusion when running Checkbox.

Fortunately, the ``check-config`` command will list:

- all the configuration files being used
- for each section, the configured parameters being used
- the origin of each of these customized parameters
- an overall status report

For example:

.. code-block:: none

    $ checkbox-cli check-config

    Configuration files:
     - /var/snap/checkbox/2799/checkbox.conf
       [config]
         config_filename=checkbox.conf      (Default)
       (...)
       [test plan]
         filter=*                           (Default)
         forced=False                       (Default)
         unit=                              (Default)
       [test selection]
         exclude=                           (Default)
         forced=False                       (Default)
       (...)
       [environment]
         STRESS_BOOT_ITERATIONS=100         From config file: /var/snap/checkbox/2799/checkbox.conf
       (...)
       [manifest]
    No problems with config(s) found!

Configs with Checkbox Remote
============================

When the :term:`Checkbox Agent` starts, it looks for config files in the same
places that local Checkbox session would look (on the :term:`Agent` side). If
the :term:`Checkbox Controller` uses a Launcher, then the values from that
Launcher take precedence over the values from configs on the :term:`Agent` side.

Example:

::

    # checkbox.conf on the Agent

    [environment]
    FOO = 12
    BAR = 6

::

    # Launcher used by the Controller

    # (...)
    [environment]
    FOO = 42

A Checkbox job that runs ``echo $FOO $BAR`` would print ``42 6``

Note that ``BAR`` is still available even though the Controller used a Launcher
that did not define it.
