Checkbox Testbed Daemon Service
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Checkbox snaps supporting Checkbox Remote functionality usually come with a
systemd service that can ensure :term:`Checkbox Testbed` is loaded and active.

.. note::

    In the examples below checkbox snap is used. For project-specific snaps,
    replace ``checkbox`` with the name of the Checkbox snap for your project.

Enabling the daemon
===================

To enable the Daemon first you have to enable it in the snap:

.. code-block:: bash

    $ snap set checkbox slave=enabled

And then ensure the systemd service is running:

.. code-block:: bash

    $ sudo systemctl restart snap.checkbox.testbed.service

Disabling the daemon
====================

In a rare case where you want to have multiple Checkbox snaps installed on the
system, it's necessary to disable all, but one.

To disable the daemon, run

.. code-block:: bash

    $ snap set checkbox slave=disabled
    $ sudo systemctl stop snap.checkbox.testbed.service


Stopping the daemon
===================

If you wish to stop the currently running Testbed instance, run

.. code-block:: bash

    $ sudo systemctl stop snap.checkbox.testbed.service

Or press ``Ctrl+C`` on the Checkbox instance controlling that particular DUT,
and select ``Exit and stop the Checkbox service on the testbed at your_host``.

Note that if the Daemon is enabled, the Testbed service will go back up after a
reboot.


Troubleshooting
===============

Whenever you have a problem with misbehaving daemon, it's advisable to start
troubleshooting by restarting the :term:`DUT`.

Daemon looks enabled but I cannot connect to it from the Controller
-------------------------------------------------------------------

Check if the daemon is enabled:

.. code-block:: bash

    $ snap get checkbox slave

Check if the service is enabled:

.. code-block:: bash

    $ sudo systemctl status snap.checkbox.testbed.service

The output should state it's ``active (running)``.

If it's not running, make sure the service and the Daemon are enabled.

The Controller connects to the DUT but I'm seeing wrong test plans
------------------------------------------------------------------

There is a chance that you have two services running that compete to listen
on the default port.

Try listing statuses of all Checkbox Testbed services and make sure only one is
running:

.. code-block:: bash

    $ sudo systemctl status "*checkbox*service*"
