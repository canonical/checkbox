Configuration values resolution order
=====================================

The directories that are searched for config files are:
``/etc/xdg/``
``~/.config/``

The filename that's looked up depends on how checkbox is run.

Invoking ``checkbox-cli`` (without launcher)
--------------------------------------------
Assumed config file name is ``checkbox.conf``

Invoking ``plainbox``
---------------------
Assumed config file name is ``plainbox.conf``

Invoking launcher
-----------------
The file name to look for is specified using ``config_filename`` variable from
launcher, from the ``[config]`` section. If it's not present, ``checkbox.conf``
' is used.

Apps using SessionAssistant or the plainbox internals directly
--------------------------------------------------------------
``plainbox.conf`` is used, unless
``SessionAsistant.use_alternate_configuration()`` is called.

Note that if same configuration variable is defined in more then one place, the
value resolution is as follows:
1. config file from ``~/.config``
2. launcher being invoked (only the new syntax launchers)
3. config file from ``/etc/xdg``
