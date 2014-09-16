=================
plainbox.conf (5)
=================

Synopsis
========

``/etc/xdg/plainbox.conf``

``$XDG_CONFIG_HOME/plainbox.conf``

Description
===========

Plainbox (and its derivatives) uses a configuration system composed of
variables arranged in sections. All configuration files follow the well-known
INI-style syntax. While Plainbox itself is not really using any variables,
knowledge of where those can be defined is useful for working with derivative
applications, such as Checkbox.

The [environment] section
-------------------------

The ``[environment]`` section deserves special attention. If a job advertises
usage of environment variable ``FOO`` (by using the `environ: FOO` declaration)
and ``FOO`` is not available in the environment of the user starting plainbox,
then the value is obtained from the ``[environment]`` section. This mechanism
is useful for distributing both site-wide and per-user configuration for jobs.

Files
=====

``/etc/xdg/plainbox.conf``

    System-wide configuration file (lowest priority).

``$XDG_CONFIG_HOME/plainbox.conf``

    Per-user configuration (highest priority).

Examples
========

/etc/xdg/plainbox.conf::

    [environment]
    OPEN_BG_SSID=my-ap-ssid

See Also
========

``plainbox-check-config`` (1)
