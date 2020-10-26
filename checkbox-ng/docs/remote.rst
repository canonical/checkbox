.. _remote:

Checkbox Remote
^^^^^^^^^^^^^^^

It is possible to run Checkbox tests on a device that you don't or cannot have
traditional control over (mouse/keyboard).

By using Checkbox Remote facilities you can use Checkbox on one device to
control Checkbox running on a different device.

This is especially useful on headless devices.

Comparison with SSH
===================

It's easy to lose SSH connection with the DUT, and if the device doesn't offer
screen-like funcitonality then the Checkbox session has to be started over.

When a UI is drawn a lot of data is transmitted through the network. Checkbox
Remote sends lean data only.

Nomenclature
============

*Checkbox Slave* - the Checkbox instance that runs on the System or Device
under test and _executes_ the tests.

*Checkbox Master* - Checkbox instance that controls the execution of tests on
the Slave, such as a laptop.

Invocation:
  Slave:
    ``checkbox-cli slave``

  Master:
    ``checkbox-cli master HOST [/PATH/TO/LAUNCHER]``

    HOST can be an IP or a hostname that your device can resolve.

    LAUNCHER (optional) a launcher file to use that exists somewhere on the
    machine you are using as the Master.


  Example:
    ``checkbox-cli master dut8.local /home/ubuntu/testplans/sutton-client``

Custom port
===========

By default Slave listens on port 18871. To change that ``--port`` option can be
used. The same option used on Master specifies which port to connect to.

  Example:
    ``checkbox-cli slave --port 10101``

    ``checkbox-cli master dut8.local --port 10101``

Session control
===============

  While Master is connected, sending SIGINT (hitting ctrl+c) to the application
  invokes the interrupt screen:

  .. image:: _images/interrupt.png

  First action is "Cancel the interruption", which returns to the session (Does
  nothing). You can also press ESC on the Interruption screen to select that
  action.

  Second action is "Disconnect the master". It leaves the session on the Slave
  running, but the Master exits. You can also hit ctrl+c again to select that
  action (terminate the master). You can reconnect to the Slave and resume
  testing like the interruption never happened.

  Third action is "Stop the Checkbox slave". It stops the session and terminates
  the Checkbox process on the Slave. It also stops the master.

  Fourth action is "Abandon the session". It stops and _removes_ the session on
  the Slave and immediately starts another one. After the new session is started
  Master is greeted with test plan selection screen. This is a good moment to
  disconnect the master if you wish to run testing at a later time.

Remote session characteristics
==============================

Differences between remote session and a local one are:

  * Unless session is explicitly abandoned, Checkbox Slave always resumes the
    last session.
  * After testing is done, Slave starts another session
  * Submission is done from the Master by default 
    (use: ``local_submission = No`` in launcher or config to change that)
  * When Master reconnects mid interactive test, the test is restarted.
  * Hitting ctrl+c in Master doesn't interrupt the running test.
