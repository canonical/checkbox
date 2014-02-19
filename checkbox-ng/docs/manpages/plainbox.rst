=============================================
plainbox -- test developer's swiss army knife
=============================================

.. toctree::
   :maxdepth: 2

Synopsis
========

usage: plainbox [-h] [--version] [-v] [-D] [-C]
                [-T LOGGER] [-P] [-I]
                subcommand ...

Description
===========

:term:`PlainBox` is a toolkit consisting of python3 library, development tools,
documentation and examples. It is targeted at developers working on testing or
certification applications and authors creating tests for such applications.

Options
=======

Optional Arguments
------------------

  -h, --help            show this help message and exit
  --version             show program's version number and exit

Logging and Debugging
---------------------

  -v, --verbose         be more verbose (same as --log-level=INFO)
  -D, --debug           enable DEBUG messages on the root logger
  -C, --debug-console   display DEBUG messages in the console
  -T LOGGER, --trace LOGGER
                        enable DEBUG messages on the specified logger (can be
                        used multiple times)
  -P, --pdb             jump into pdb (python debugger) when a command crashes
  -I, --debug-interrupt
                        crash on SIGINT/KeyboardInterrupt, useful with --pdb


PlainBox Sub-Commands
=====================

PlainBox uses a number of sub-commands for performing specific operations.
Since it targets several different audiences commands are arranged into three
parts: test authors, test users and core developers

Test Users
----------

    plainbox run
        Run a test job. This is the swiss army knife of a swiss army knife. Has
        lots of options that affect job selection, execution and handling results.

    plainbox check-config
        check and display plainbox configuration. While this command doesn't allow
        to edit any settings it is very useful for figuring out what variables are
        available and which configuration files are consulted.

Test Authors
------------

    plainbox startprovider
        Create a new provider (directory). This command allows test authors to
        create a new collection (provider) of test definitions for PlainBox.

    plainbox dev script
        Run the command from a job in a way it would run as a part of normal
        run, ignoring all dependencies / requirements and providing additional
        diagnostic messages.

    plainbox dev analyze
        Analyze how selected jobs would be executed. Takes almost the same
        arguments as ``plainbox run`` does. Additional optional arguments
        control the type of analysis performed.

    plainbox dev parse
        Parse stdin with the specified parser. PlainBox comes with a system for
        plugging parser definitions so that shell programs (and developers) get
        access to structured data exported from otherwise hard-to-parse output.

    plainbox dev list
        List and describe various objects. Run without arguments to see all the
        high-level objects PlainBox knows about. Optional argument can restrict
        the list to objects of one kind.

Core Developers
---------------

    plainbox self-test
        Run unit and integration tests. Unit tests work also after installation
        so this command can verify a local installation at any time.

    plainbox dev special
        Access to special/internal commands.

    plainbox dev crash
        Crash the application. Useful for testing the crash handler and crash
        log files.

    plainbox dev logtest
        Log messages at various levels. Useful for testing the logging system.

Files and Directories
=====================

The following files and directories affect PlainBox:

Created or written to
---------------------

``$XDG_CACHE_HOME/plainbox/logs``
    PlainBox keeps all internal log files in this directory. In particular the
    ``crash.log`` is generated there on abnormal termination. If extended
    logging / tracing is enabled via ``--debug`` or ``--trace`` then
    ``debug.log`` will be created in this directory. The files are generated on
    demand and are rotated if they grow too large. It is safe to remove them at
    any time.

``$XDG_CACHE_HOME/plainbox/sessions``
    PlainBox keeps internal state of all running and dormant (suspended or
    complete) sessions here. Each session is kept in a separate directory with
    a randomly generated name. This directory may also contain a symlink
    ``last-session`` that points at one of those sessions. The symlink may be
    broken as a part of normal operation.

    Sessions may accumulate, in some cases, and they are not garbage collected
    at this time. In general it is safe to remove sessions when PlainBox is not
    running.

Looked up or read from
----------------------

``/usr/local/share/plainbox-providers-1/*.provider``
    System wide, locally administered directory with provider definitions. See
    PROVIDERS for more information. Jobs defined here have access to
    ``plainbox-trusted-launcher(1)`` and may run as root without prompting
    (depending on configuration).

``/usr/share/plainbox-providers-1/*.provider``
    Like ``/usr/local/share/plainbox-providers-1`` but maintained by the local
    package management system. This is where packaged providers add their
    definitions.

``$XDG_DATA_HOME/plainbox-providers-1/*.provider``
    Per-user directory with provider definitions. This directory may be used to
    install additional test definitions that are only available to a particular
    user. Jobs defined there will not have access to
    ``plainbox-trusted-launcher(1)`` and will use ``pkexec(1)`` or ``sudo(1)``
    to run as root, if needed.

    Typically this directory is used by test provider developers transparently
    by invoking ``manage.py develop`` (manage.py is the per-provider management
    script generated by ``plainbox startprovider``)

``/etc/xdg/plainbox.conf``

    System-wide configuration file (lowest priority). See below for details.

``$XDG_CONFIG_HOME/plainbox.conf``

    Per-user configuration (highest priority).

Configuration Files
===================

PlainBox (and its derivatives) uses a configuration system composed of
variables arranged in sections. All configuration files follow the well-known
INI-style syntax. While PlainBox itself is not really using any variables,
knowledge of where those can be defined is useful for working with derivative
applications, such as Checkbox.

The environment section
-----------------------

The ``[environment]`` section deserves special attention. If a job advertises
usage of environment variable ``FOO`` (by using the `environ: FOO` declaration)
and ``FOO`` is not available in the environment of the user starting plainbox,
then the value is obtained from the ``[environment]`` section. This mechanism
is useful for distributing both site-wide and per-user configuration for jobs.

Environment Variables
=====================

The following environment variables affect PlainBox:

``PROVIDERPATH``
    Determines the lookup of test providers. Note that unless otherwise
    essential, it is recommended to install test providers into one of the
    aforementioned directories instead of using PROVIDERPATH.

    The default value is composed out of ':'-joined list of:

    * ``/usr/local/share/plainbox-providers-1``
    * ``/usr/share/plainbox-providers-1``
    * ``$XDG_DATA_HOME/plainbox-providers-1``

``PLAINBOX_USE_TRUSTED_LAUNCHER``
    Alters the PlainBox execution controller voting score so that jobs coming
    from the ``2013.com.canonical:checkbox-src`` provider are forced to go
    through the ``plainbox-trusted-launcher(1)``. This is a development-only
    feature. It is patched away by responsible packagers to prevent security
    risk present from using plainbox-trusted-launcher with the insecure job
    definitions installed in not system-wide locations.

``PLAINBOX_LOCALE_DIR``
    Alters the lookup directory for translation catalogs. When unset uses
    system-wide locations. Developers working with a local copy should set it
    to ``build/mo`` (after running ``./setup.py build_i18n``)

``PLAINBOX_I18N_MODE``
    Alters behavior of the translation subsystem. This is only useful to
    developers that wish to see fake translations of all the strings marked as
    translatable. Available values include ``no-op``, ``gettext`` (default),
    ``rot-13``, ``lorem-ipsum-XX`` where ``XX`` is the language code of the
    faked translations. Supported faked translations are: ``ar`` (Arabic),
    ``ch`` (Chinese), ``he`` (Hebrew), ``jp`` (Japanese), ``kr`` (Korean),
    ``pl`` (Polish) and ``ru`` (Russian)
