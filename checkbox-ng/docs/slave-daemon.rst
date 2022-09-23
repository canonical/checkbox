.. _daemonic_slave:

Checkbox Slave Daemon Service
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Checkbox snaps supporting Checkbox Remote functionality usually come with a
Systemd service that can ensure Checkbox Slave is loaded and active.

.. note::

    In the examples below checkbox-snappy snap is used. For project specific
    snaps replace ``checkbox-snappy`` with the name of Checkbox snap for your
    project.

Enabling the daemon
===================

To enable the Daemon first you have to enable it in the snap:

.. code-block:: bash

    $ snap set checkbox-snappy slave=enabled

And then ensure the Systemd service is running

.. code-block:: bash

    $ sudo systemctl restart snap.checkbox-snappy.remote-slave.service

Disabling the daemon
====================

In a rare case where you want to have multiple Checkbox snaps installed on the
system, it's necessary to disable all, but one.

To disable the daemon run

.. code-block:: bash

    $ snap set checkbox-snappy slave=disabled
    $ sudo systemctl stop snap.checkbox-snappy.remote-slave.service


Stopping the daemon
===================

If you wish to stop currently running Slave instance, run

.. code-block:: bash

    $ sudo systemctl stop snap.checkbox-snappy.remote-slave.service

Or press ctrl+c on the Master controlling that particular slave, and select
``stop the checkbox slave @your_host``.

Note that if the Daemon is enabled, the Slave will go back up after a reboot.


Troubleshooting
===============

Whenever you have a problem with misbehaving daemon, it's advisable to start
troubleshooting by restarting the host running the Slave.

Daemon looks enabled but I cannot connect to it from the master
---------------------------------------------------------------

Check if the daemon is enabled:

.. code-block:: bash

    $ snap get checkbox-snappy slave

Check if the service is enabled:

.. code-block:: bash

    $ sudo systemctl status snap.checkbox-snappy.remote-slave.service

The output should state it's ``active (running)``.

If it's not running, make sure the service and the Daemon are enabled.

Master connects but I'm seeing wrong test plans
-----------------------------------------------

There is a chance that you have two services running that compete to listen
on the default port.

Try listing statuses of all Checkbox Slave services and make sure only one is
running.

.. code-block:: bash

    $ sudo systemctl status '*checkbox*slave*'
