Running jobs as root
====================

:term:`PlainBox` is started without any privilege.  But several tests need to
start commands requiring privileges.

Such tests will call a trusted launcher, a standalone script which does not
depend on the :term:`PlainBox` core modules.
`polkit <http://www.freedesktop.org/wiki/Software/polkit>`_ will control access
to system resources.  The trusted launcher has to be started using
`pkexec <http://www.freedesktop.org/software/polkit/docs/0.105/pkexec.1.html>`_
so that the related policy file works as expected.

To avoid a security hole that allows anyone to run anything as root, the
launcher can only run jobs installed in a system-wide directory. This way we
are not weaken the trust system as root access is required to install both
components (the trusted runner and jobs). The :term:`PlainBox` process will
send an identifier which is matched by a well-known list in the trusted
launcher. This identifier is the job hash:

.. code-block:: bash

    $ pkexec plainbox-trusted-launcher-1 --hash JOB-HASH

See :attr:`plainbox.impl.secure.job.BaseJob.checksum` for details about job
hashes.

Using Polkit
^^^^^^^^^^^^

Available authentication methods
--------------------------------

.. note::

    Only applicable to the package version of PlainBox

PlainBox comes with two authentication methods but both aim to retain the
granted privileges for the life of the :term:`PlainBox` process.

* The first method will ask the password only once and show the following
  agent on desktop systems (a text-based agent is available for servers):

    .. code-block:: text

        +-----------------------------------------------------------------------------+
        | [X]                            Authenticate                                 |
        +-----------------------------------------------------------------------------+
        |                                                                             |
        | [Icon] Please enter your password. Some tests require root access to run    |
        |        properly. Your password will never be stored and will never be       |
        |        submitted with test results.                                         |
        |                                                                             |
        |        An application is attempting to perform an action that requires      |
        |        privileges.                                                          |
        |        Authentication as the super user is required to perform this action. |
        |                                                                             |
        |        Password: [________________________________________________________] |
        |                                                                             |
        | [V] Details:                                                                |
        |  Action: org.freedesktop.policykit.pkexec.run-plainbox-job                  |
        |  Vendor: PlainBox                                                           |
        |                                                                             |
        |                                                     [Cancel] [Authenticate] |
        +-----------------------------------------------------------------------------+

    The following policy file has to be installed in
    :file:`/usr/share/polkit-1/actions/` on Ubuntu systems. Asking the
    password just one time and keeps the authentication for forthcoming calls
    is provided by the **allow_active** element and the **auth_admin_keep**
    value.

    Check the `polkit actions <http://www.freedesktop.org/software/polkit/docs/0.105/polkit.8.html#polkit-declaring-actions>`_
    documentation for details about the other parameters.

    .. code-block:: xml

        <?xml version="1.0" encoding="UTF-8"?>
        <!DOCTYPE policyconfig PUBLIC
         "-//freedesktop//DTD PolicyKit Policy Configuration 1.0//EN"
         "http://www.freedesktop.org/standards/PolicyKit/1/policyconfig.dtd">
        <policyconfig>

          <vendor>PlainBox</vendor>
          <vendor_url>https://launchpad.net/checkbox</vendor_url>
          <icon_name>checkbox</icon_name>

          <action id="org.freedesktop.policykit.pkexec.run-plainbox-job">
            <description>Run Job command</description>
            <message>Authentication is required to run a job command.</message>
            <defaults>
              <allow_any>no</allow_any>
              <allow_inactive>no</allow_inactive>
              <allow_active>auth_admin_keep</allow_active>
            </defaults>
            <annotate key="org.freedesktop.policykit.exec.path">/usr/bin/plainbox-trusted-launcher-1</annotate>
            <annotate key="org.freedesktop.policykit.exec.allow_gui">TRUE</annotate>
          </action>

        </policyconfig>

* The second method is only intended to be used in headless mode (like `SRU`).
  The only difference with the above method is that **allow_active** will be
  set to **yes**.

.. note::

    The two policy files are available in the PlainBox :file:`contrib/`
    directory.

Environment settings with pkexec
--------------------------------

`pkexec <http://www.freedesktop.org/software/polkit/docs/0.105/pkexec.1.html>`_
allows an authorized user to execute a command as another user.  But the
environment that ``command`` will run it, will be set to a minimal known and
safe environment in order to avoid injecting code through ``LD_LIBRARY_PATH``
or similar mechanisms.

However, some jobs commands require specific enviroment variables such as the
name of an access point for a wireless test. Those kind of variables must be
available to the trusted launcher. To do so, the enviromment mapping is sent
to the launcher like key/value pairs are sent to the env(1) command:

.. code-block:: bash

    $ pkexec trusted-launcher JOB-HASH [NAME=VALUE [NAME=VALUE ...]]

Each NAME will be set to VALUE in the environment given that they are known
and defined in the :ref:`JobDefinition.environ <environ>` parameter.

plainbox-trusted-launcher-1
^^^^^^^^^^^^^^^^^^^^^^^^^^^

The trusted launcher is the minimal code needed to be able to run a
:term:`CheckBox` job command.

Internally the checkbox trusted launcher looks for jobs in the system locations
defined in :attr:`plainbox.impl.secure.providers.v1.all_providers` which
defaults to :file:`/usr/share/plainbox-trusted-launcher-1/*.provider`.

Usage
-----

.. code-block:: text

    plainbox-trusted-launcher-1 [-h] (--hash HASH | --warmup)
                              [--via LOCAL-JOB-HASH]
                              [NAME=VALUE [NAME=VALUE ...]]

    positional arguments:
      NAME=VALUE            Set each NAME to VALUE in the string environment

    optional arguments:
      -h, --help            show this help message and exit
      --hash HASH           job hash to match
      --warmup              Return immediately, only useful when used with
                            pkexec(1)
      --via LOCAL-JOB-HASH  Local job hash to use to match the generated job

.. note::

    Check all job hashes with ``plainbox special -J``

As stated in the polkit chapter, only a trusted subset of the environment
mapping will be set using `subprocess.call` to run the command.  Only the
variables defined in the job environ property are allowed to avoid compromising
the root environment. Needed modifications like adding ``CHECKBOX_SHARE`` and
new paths to scripts are managed by the plainbox-trusted-launcher-1.

Authentication on PlainBox startup
----------------------------------

To avoid prompting the password at the first test requiring privileges,
:term:`PlainBox` will call the ``plainbox-trusted-launcher-1`` with the
``--warmup`` option.  It's like a NOOP and it will return immediately, but
thanks to the installed policy file the authentication will be kept.

.. note::

    When running the development version from a branch, the usual polkit
    authentication agent will pop up to ask the password each and every time.
    This is the only difference.

Special case of jobs using the CheckBox local plugin
----------------------------------------------------

For jobs generated from :ref:`local <local>` jobs (e.g.
disk/read_performance.*) the trusted launcher is started with ``--via`` meaning
that we have to first eval a local job to find a hash match. Once a match is
found, the job command is executed.

.. code-block:: bash

    $ pkexec plainbox-trusted-launcher-1 --hash JOB-HASH --via LOCAL-JOB-HASH

.. note::

    it will obviously fail if any local job can ever generate another local job.
