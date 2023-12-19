.. _checkbox_configs:

Checkbox Configs
^^^^^^^^^^^^^^^^

Configuration file path
=======================

By default, Checkbox searches for configuration files in the following directories:

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


Configuration values resolution order
=====================================

If the same configuration variable is defined in more than one place, the order
of value resolution is as follows (from the highest to lowest priority):

1. launcher being invoked
2. config file from ``~/.config``
3. config file from ``/etc/xdg``
4. config file from ``$SNAP_DATA``

If a configuration is specified in a launcher, values specified in other files
for the same configuration are overridden.

For example, if the following config file is created at a custom location
``/tmp/my_config_name.conf``:

.. code-block:: none
   :caption: /tmp/my_config_name.conf

   [test plan] 
   unit = com.canonical.certification::smoke 
   forced = yes

   [test selection] 
   forced = yes

And another config file at the one of the default lookup locations
``~/.config/checkbox.conf`` contains a duplicated value:

.. code-block:: none
   :caption: ~/.config/checkbox.conf

   [test plan] 
   unit = wrong_name

Then invoke Checkbox with the following launcher:

.. code-block:: none
   :caption: myLauncher
   :emphasize-lines: 2

   [config] 
   config_filename = /tmp/my_config_name.conf

Checkbox will load the correct test plan specified in the launcher. The ``unit``
value in the default location is ignored.


Configuration inheritance
=========================

To maintain a clean setup for different use cases, it is useful to define a
global configuration for Checkbox and a few smaller configurations that are
specific to each situation. You can use the ``config_filename`` option to bring
values from other configuration files into a config or a launcher.

For example, the following config file contains some global configurations at
``~/.config/checkbox_global.conf``:

.. code-block:: none
  :caption: ~/.config/checkbox_global.conf

  [ui]
  output = hide-automated

  [launcher]
  session_title = My machine name
  stock_reports = [text]

  [exporter:text]
  unit = com.canonical.plainbox::text

  [transport:out_to_file]
  type = file
  path = /tmp/.last_checkbox_out.txt

  [report:screen]
  exporter = text
  transport = out_to_file

  [manifest]
  com.canonical.certification::my_manifest_key = True

If you invoke Checkbox with a launcher file that refers to this global config,
both configuration sources are taken into account:

.. code-block:: none
   :caption: myLauncher
   :emphasize-lines: 2
 
   [config]
   config_filename = ~/.config/checkbox_global.conf

   [test plan]
   unit = com.canonical.certification::smoke
   force = True


If the same configuration option is defined in different sources, the value
defined in the importing file overrides the one from the imported config.

For example, the following launcher configures the test report and submission,
where the ``stock_reports`` value overrides the imported value:

.. code-block:: none
   :caption: mySecondLauncher
   :emphasize-lines: 2, 9

   [config]
   config_filename = ~/.config/checkbox_global.conf

   [test plan]
   unit = com.canonical.certification::smoke
   forced = True

   [launcher]
   stock_reports = [text, certification, submission_files]
   local_submission = True

The configuration value inheritance (when a config or a launcher imports
another config/launcher) allows every value to be inherited and
overridden. It is helpful to use the :ref:`'check-config' command <check_config_cmd>` to track 
the origin of config values before running tests.

.. warning::

   Circular import is not allowed. We advise you to use this feature in
   moderation since whilst it can simplify the maintanoneng of multiple
   configurations by avoiding copy-pasting values around, it can also make
   debugging a configuration complicated. 

.. _check_config_cmd:

Configuration checker
=====================

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
     - /home/user/.config/checkbox.conf
       [config]
         config_filename=checkbox.conf      (Default)
       (...)
       [test plan]
         filter=*wireless*                  From config file: /home/user/.config/checkbox.conf
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

A configuration file may have errors. Consider the following ``checkbox.conf``
placed in ``/home/user/.config/``:

.. code-block:: none

    [test plan]
    filter = *wireless*

    [test selection]
    wrong_var = example

When running the ``check-config`` command, the following will be reported:

.. code-block:: none

    Problems:
    -  Unexpected section [test plan]. Origin: /home/user/.config/checkbox.conf
    -  Unexpected variable 'wrong_var' in section [test selection] Origin: /home/user/.config/checkbox.conf

Indeed, there is a typo in the name of the ``[test plan]`` section, and
a unknown variable is set in the ``[test selection]`` section. For more
information on the available sections and variables, please check the
:ref:`launcher` reference.


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
