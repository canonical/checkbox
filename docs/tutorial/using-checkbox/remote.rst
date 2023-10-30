.. _base_tutorial_remote:

==============
Remote testing
==============

So far, you have used Checkbox in local mode. It is, however, possible to use
Checkbox to test a device from another device. It is the preferred method
of using Checkbox, especially if you plan on running tests that suspend,
reboot or turn off the device you're testing. In Checkbox language, the
device being tested is called an :term:`agent<Checkbox Agent>` and the device
controlling the execution of the tests is called the :term:`controller<Checkbox
Controller>`. This is the remote mode. In this section, you will use the
remote mode to execute a test plan.

Agent and controller
====================

Run the following command:

.. code-block:: none

    systemctl status snap.checkbox.agent.service

You should see something like this:

.. code-block:: none

    ● snap.checkbox.agent.service - Service for snap application checkbox.service
         Loaded: loaded (/etc/systemd/system/snap.checkbox.service.service; enabled; vendor preset: enabled)
         Active: active (running) since Fri 2023-07-21 13:38:48 CST; 1h 29min ago
       Main PID: 1411 (python3)
          Tasks: 1 (limit: 19014)
         Memory: 69.7M
            CPU: 2.537s
         CGroup: /system.slice/snap.checkbox.service.service
                 └─1411 python3 /snap/checkbox22/current/bin/checkbox-cli service

    Jul 21 13:38:48 coltrane systemd[1]: Started Service for snap application checkbox.service.
    (...)

When you install Checkbox on a device, a Systemd service is started to turn
this device into a Checkbox agent.

For the sake of this tutorial, let's stop this service for the moment:

.. code-block:: none

    sudo systemctl stop snap.checkbox.agent.service

Now, open two terminal windows using ``Ctrl+Alt+T``. In the first one,
start the Checkbox agent:

.. code-block:: none

    sudo checkbox.checkbox-cli run-agent

In the second one, run Checkbox as a controller to connect to the agent:

.. code-block:: none

    checkbox.checkbox-cli control 127.0.0.1

.. note::

    127.0.0.1 is the IP address pointing to your own computer!

On the agent terminal, you should see something like  ``Using `$USER` user``
where ``$USER`` is your local user name.

On the controller terminal, you should get the list of test plans available. Go
ahead and select the "Checkbox Base Tutorial" test plan, keep all the tests
selected and start the test session by pressing ``T``. All the test cases
are being executed, then Checkbox generates the usual text summary as well
as the submission files. Notice how the output is slightly different:

.. code-block:: none

    1.17MB [00:00, 25.3MB/s, file=/home/pieq/.local/share/checkbox-ng/submission_2023-07-21T07.30.46.784342.html]
    file:///home/pieq/.local/share/checkbox-ng/submission_2023-07-21T07.30.46.784342.html
    32.0kB [00:00, 26.6MB/s, file=/home/pieq/.local/share/checkbox-ng/submission_2023-07-21T07.30.46.784342.junit.xml]
    file:///home/pieq/.local/share/checkbox-ng/submission_2023-07-21T07.30.46.784342.junit.xml
    256kB [00:00, 24.1MB/s, file=/home/pieq/.local/share/checkbox-ng/submission_2023-07-21T07.30.46.784342.tar.xz]
    file:///home/pieq/.local/share/checkbox-ng/submission_2023-07-21T07.30.46.784342.tar.xz

This is because the submission files are generated on the agent, then
transferred over the network to the controller, so Checkbox displays the
size of each file as well as some estimated duration for the transfer. Since
in our case both the agent and the controller are on the same device, the
transfer is immediate.

Similar to the local mode, Checkbox also asks by default if you want to
upload the results to the Certification website. Just type ``n`` and press
``Enter`` to end the session.

On the agent terminal, you can see a message like:

.. code-block:: none

    Finalizing session that hasn't been submitted anywhere: remote-2023-07-21T07.26.58

This means the test session ``remote-2023-07-21T07.26.58`` has been completed
and it was not uploaded to the Certification website.

Stop the agent running in the terminal by pressing ``Ctrl+C`` in it, then
restart the Checkbox agent service with:

.. code-block:: none

    sudo systemctl start snap.checkbox.agent.service

If you have another device running Ubuntu, you can try to install Checkbox on
it, then connect to it using your own computer with the ``checkbox.checkbox-cli
control x.x.x.x`` command, replacing ``x.x.x.x`` by the IP address of the
other device.

Launchers in remote mode
========================

In remote mode, you can use launchers the same way you did in
local mode. If you still have the launcher file you created in the
:ref:`base_tutorial_launcher` section, run the following command:

.. code-block:: none

    checkbox.checkbox-cli control 127.0.0.1 mylauncher

This will start a remote test session with the configuration defined in
your launcher.

The interrupt screen
====================

When run in remote mode, Checkbox comes with some additional features. One
of them is the interrupt screen. Run Checkbox remote:

.. code-block:: none

    checkbox.checkbox-cli control 127.0.0.1

Select the "Checkbox Base Tutorial" test plan, leave all the jobs selected,
and press ``T`` to start the testing session.

Now, while the tests are being executed by the agent, press ``Ctrl+C``
on the controller. You should see a screen like this:

.. code-block:: none

     Interruption!
    ┌─────────────────────────────────────────────────────────────────────────────┐
    │                                                                             │
    │          What do you want to interrupt?                                     │
    │                                                                             │
    │     (X) Nothing, continue testing (ESC)                                     │
    │     ( ) Stop the test case in progress and move on to the next              │
    │     ( ) Pause the test session and disconnect from the agent (CTRL+C)       │
    │     ( ) Exit and stop the Checkbox service on the agent at 127.0.0.1        │
    │     ( ) End this test session preserving its data and launch a new one      │
    │                                                                             │
    └─────────────────────────────────────────────────────────────────────────────┘
     Press <Enter> or <ESC> to continue


The different choices are explained in the  :ref:`Checkbox remote
explanation <remote_session_control>`. Let's select the option "Exit and
stop the Checkbox service on the agent" by highlighting it with the arrows
and pressing ``Space``, then press ``Enter``. Checkbox exits, and you can
see the Checkbox agent Systemd service is not running anymore:

.. code-block:: none

    systemctl is-active snap.checkbox.agent.service
    inactive

If you try reconnecting to the agent, the controller will wait 5 minutes
for the agent to be reactivated, after what it will time out:

.. code-block:: none

    checkbox.checkbox-cli control 127.0.0.1
    .....
    Connection timed out.

Restart the agent by typing:

.. code-block:: none

    sudo systemctl start snap.checkbox.agent.service

Wrapping up
===========

In this section, you played with the remote mode of Checkbox which allows to
control an agent through the network. You stopped and started the Systemd
service that turns any device into a Checkbox agent, and you connected to
the Checkbox agent using a Checkbox controller in order to select the test
plan and the test cases to run, either by hand or using a launcher.
