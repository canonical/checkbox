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

Invoking launcher that uses 'the new syntax'
--------------------------------------------
The file name to look for is specified using ``config_filename`` variable from
launcher, from the ``[config]`` section. If it's not present, ``checkbox.conf``
' is used.

Invoking 'legacy' launcher
--------------------------
Both, ``plainbox.conf`` and the value ``config_filename`` from launcher are used.

Apps using SessionAssistant or the plainbox internals directly
-----------------------------------------------------------
``plainbox.conf`` is used, unless
``SessionAsistant.use_alternate_configuration()`` is called.

Note that if same configuration variable is defined in more then one place, the
value resolution is as follows:
 1. launcher being invoked (only the new syntax launchers)
 2. config file from ``~/.config``
 3. config file from ``/etc/xdg``

For legacy launchers, because two config filenames can be used (the one defined
in ``config_filename``, and ``plainbox.conf``), the one from
``config_filename`` takes precedence over plainbox.conf. I.e. the order of
preference is (most important first):
 1. ``~/.config/checkbox.conf``
 2. ``~/.config/plainbox.conf``
 3. ``/etc/xdg/checkbox.conf``
 4. ``/etc/xdg/plainbox.conf``
