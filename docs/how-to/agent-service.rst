Checkbox Agent Service
^^^^^^^^^^^^^^^^^^^^^^^^

Checkbox snaps supporting Checkbox Remote functionality usually come with a
systemd service that can ensure :term:`Checkbox Agent` is loaded and active.

.. note::

    In the examples below, the checkbox snap is used. For project-specific
    snaps, replace ``checkbox`` with the name of the Checkbox snap for your
    project.

Enabling the service
====================

By default, Checkbox snaps should automatically start the systemd service. To
make sure it is running, run

.. code-block:: bash

    $ sudo systemctl restart snap.checkbox.agent.service

Stopping the service
====================

In a rare case where you want to have multiple Checkbox snaps installed on the
system, it's necessary to disable all but one services.

To do this, run

.. code-block:: bash

    $ sudo systemctl stop snap.checkbox.agent.service


You can also press ``Ctrl+C`` on the Checkbox instance controlling that
particular agent, and select ``Exit and stop the Checkbox service on the agent
at your_host``.

Note that the Agent service will come back up after a reboot.

Troubleshooting
===============

Whenever you have a problem with misbehaving service, it's advisable to start
troubleshooting by restarting the :term:`DUT`.

I cannot connect to the Agent from the Controller
-------------------------------------------------

Check if the service is enabled:

.. code-block:: bash

    $ sudo systemctl status snap.checkbox.agent.service

The output should state it's ``active (running)``.

If it's not running, make sure the service is enabled.

The Controller connects to the Agent but I'm seeing the wrong test plans
------------------------------------------------------------------------

There is a chance that you have two services running that compete to listen
on the default port.

Try listing statuses of all Checkbox Agent services and make sure only one is
running:

.. code-block:: bash

    $ sudo systemctl status "*checkbox*service*"
