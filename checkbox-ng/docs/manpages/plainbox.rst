============
plainbox (1)
============

.. argparse::
    :ref: plainbox.impl.box.get_parser_for_sphinx
    :prog: plainbox
    :manpage:
    :nodefault:
    :nosubcommands:

    Plainbox is a toolkit consisting of python3 library, development
    tools, documentation and examples. It is targeted at developers working
    on testing or certification applications and authors creating tests for
    such applications.

Plainbox Sub-Commands
=====================

Plainbox uses a number of sub-commands for performing specific operations.
Since it targets several different audiences commands are arranged into three
parts: test authors, test users and core developers

Test Users
----------

    plainbox run
        Run a test job. This is the swiss army knife of a swiss army knife. Has
        lots of options that affect job selection, execution and handling
        results.

    plainbox check-config
        check and display plainbox configuration. While this command doesn't
        allow to edit any settings it is very useful for figuring out what
        variables are available and which configuration files are consulted.

Test Authors
------------

    plainbox startprovider
        Create a new provider (directory). This command allows test authors to
        create a new collection (provider) of test definitions for Plainbox.

    plainbox dev script
        Run the command from a job in a way it would run as a part of normal
        run, ignoring all dependencies / requirements and providing additional
        diagnostic messages.

    plainbox dev analyze
        Analyze how selected jobs would be executed. Takes almost the same
        arguments as ``plainbox run`` does. Additional optional arguments
        control the type of analysis performed.

    plainbox dev parse
        Parse stdin with the specified parser. Plainbox comes with a system for
        plugging parser definitions so that shell programs (and developers) get
        access to structured data exported from otherwise hard-to-parse output.

    plainbox dev list
        List and describe various objects. Run without arguments to see all the
        high-level objects Plainbox knows about. Optional argument can restrict
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

Files
=====

The following files and directories affect Plainbox:

Created or written to
---------------------

``$XDG_CACHE_HOME/plainbox/logs``
    Plainbox keeps all internal log files in this directory. In particular the
    ``crash.log`` is generated there on abnormal termination. If extended
    logging / tracing is enabled via ``--debug`` or ``--trace`` then
    ``debug.log`` will be created in this directory. The files are generated on
    demand and are rotated if they grow too large. It is safe to remove them at
    any time.

``$XDG_CACHE_HOME/plainbox/sessions``
    Plainbox keeps internal state of all running and dormant (suspended or
    complete) sessions here. Each session is kept in a separate directory with
    a randomly generated name. This directory may also contain a symlink
    ``last-session`` that points at one of those sessions. The symlink may be
    broken as a part of normal operation.

    Sessions may accumulate, in some cases, and they are not garbage collected
    at this time. In general it is safe to remove sessions when Plainbox is not
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

In addition, refer to the list of files mentioned by ``plainbox.conf`` (5)

Environment Variables
=====================

The following environment variables affect Plainbox:

``PROVIDERPATH``
    Determines the lookup of test providers. Note that unless otherwise
    essential, it is recommended to install test providers into one of the
    aforementioned directories instead of using PROVIDERPATH.

    The default value is composed out of ':'-joined list of:

    * ``/usr/local/share/plainbox-providers-1``
    * ``/usr/share/plainbox-providers-1``
    * ``$XDG_DATA_HOME/plainbox-providers-1``

``PLAINBOX_LOCALE_DIR``
    Alters the lookup directory for translation catalogs. When unset uses
    system-wide locations. Developers working with a local copy should set it
    to ``build/mo`` (after running ``./setup.py build_i18n``)

``PLAINBOX_I18N_MODE``
    Alters behavior of the translation subsystem. This is only useful to
    developers that wish to see fake translations of all the strings marked as
    translatable. Available values include ``no-op``, ``gettext`` (default),
    ``lorem-ipsum-XX`` where ``XX`` is the language code of the faked
    translations. Supported faked translations are: ``ar`` (Arabic), ``ch``
    (Chinese), ``he`` (Hebrew), ``jp`` (Japanese), ``kr`` (Korean), ``pl``
    (Polish) and ``ru`` (Russian)

``PLAINBOX_DEBUG``
    Setting this to a non-empty string enables early logging support.  This is
    somewhat equivalent to running ``plainbox --debug`` except that it also
    affects code that runs before command line parsing is finished. One
    particular value that can be used here is "console". It enables console
    traces (similar to ``plainbox --debug-console`` command-line argument).

``PLAINBOX_LOG_LEVEL``
    This variable is only inspected if ``PLAINBOX_DEBUG`` is not empty. It is
    equivalent to the ``plainbox --log-level=`` command-line argument. By
    default (assuming ``PLAINBOX_DEBUG`` is set) is ``DEBUG`` which turns on
    everything.

``PLAINBOX_TRACE``.
    This variable is only inspected if ``PLAINBOX_DEBUG`` is not empty. It is
    equivalent to the ``plainbox --trace=`` command-line argument. Unlike the
    command line argument, it handles a comma-separated list of loggers to
    trace. By default it is empty.

See Also
========

:doc:`plainbox-run`, :doc:`plainbox-session`, :doc:`plainbox-check-config`
:doc:`plainbox-self-test`, :doc:`plainbox-startprovider`, :doc:`plainbox-dev`
:doc:`plainbox.conf`
