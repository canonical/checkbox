=================================
How to Freeze a Checkbox Version
=================================

How to freeze Checkbox Snaps
============================


Snaps update automatically, and by default, the snapd daemon checks for updates
4 times a day. The ``snap refresh --hold`` command holds snap updates for
individual snaps, or for all snaps on the system, either indefinitely or for a
specified period of time.

.. code-block:: bash

   $ snap refresh --hold=<duration> <snap1> <snap2>...

This option has been available since ``snapd 2.58``, and it is available for all
the Ubuntu versions in which Checkbox is supported.

To postpone the Checkbox snaps updates indefinitely, we can use
``--hold=forever``. Here is how you can stop the Checkbox snap automatic updates
and freeze it in the current version:

.. code-block:: bash

   $ snap refresh --hold=forever checkbox checkbox22

To check which snaps are being held, you can look for ``held`` in the ``notes``
column when running ``snap list``:

.. code-block::

   $ snap list
   Name        Version        Rev    Tracking       Publisher            Notes
   checkbox    3.3.0-dev19    5224   22.04/stable   ce-certification-qa  classic,held
   checkbox22  3.3.0-dev19    726    latest/stable  ce-certification-qa  held

To remove the hold, just run the ``snap refresh --unhold`` command for each
snap.

.. code-block::

   $ snap refresh --hold=forever checkbox checkbox22
   $ snap list
   Name        Version        Rev    Tracking       Publisher            Notes
   checkbox    3.3.0-dev19    5224   22.04/stable   ce-certification-qa  classic
   checkbox22  3.3.0-dev19    726    latest/stable  ce-certification-qa  -

How to freeze Checkbox Debs
============================

Using Ubuntu snapshot service (20.04 or later)
----------------------------------------------

To freeze the Checkbox version of a deb package we will make use of the Ubuntu
snapshot service. This service allows you to see and use the Ubuntu archive, as
well as all PPAs (both private and public), as it was at any specified date and
time, for any time and date after 1 March 2023.

Snapshots are supported in Ubuntu 23.10 onwards, and also on updated
installations of Ubuntu 20.04 LTS (with ``apt`` 2.0.10) and Ubuntu 22.04
LTS(with ``apt`` 2.4.11).

Enable the snapshot Service
```````````````````````````

For Ubuntu 24.04
''''''''''''''''

The apt included in Ubuntu 24.04 and later automatically detects when snapshots
are supported for a repository and are enabled by default.

Nevertheless, for PPAs in Launchpad it is sometimes necessary to modify the URI
field to match the URL of the snapshot. In the case of checkbox, you have to
edit
``/etc/apt/sources.list.d/checkbox-dev-ubuntu-{ppa-name}-{ubuntu-version}.list``
and add a tilde before checkbox-dev.

For example:

.. code-block::

   # In “/etc/apt/sources.list.d/checkbox-dev-ubuntu-beta-noble.list”
   Types: deb
   URIs: https://ppa.launchpadcontent.net/~checkbox-dev/beta/ubuntu/
   Suites: noble
   Components: main
   Signed-By: {KEY} 

For Ubuntu 23.10 and earlier
''''''''''''''''''''''''''''
On Ubuntu 23.10 and earlier, edit
``/etc/apt/sources.list.d/checkbox-dev-ubuntu-{ppa-name}-{ubuntu-version}.list``
and add ``[snapshot=yes]`` into the standard prefix. You also need to modify the
PPA url to include the tilde before checkbox-dev so it points to the correct
snapshot URL. For example:

.. code-block::

   # In “/etc/apt/sources.list.d/checkbox-dev-ubuntu-beta-jammy.list”
   deb [snapshot=yes] https://ppa.launchpadcontent.net/~checkbox-dev/beta/ubuntu jammy main


Use a Snapshot ID with apt Commands
```````````````````````````````````
The Ubuntu snapshot service uses a Snapshot ID to indicate the desired date and
the UTC time of the snapshot in the format ``YYYYMMDDTHHMMSSZ``. For example,
``20230302T030400Z`` would be 03:04 UTC on 2 March 2023.

Once snapshots are enabled for a repository, it is possible to pass a specific
Snapshot ID to most apt or apt-get commands with ``--snapshot [Snapshot ID]`` or
``-S [Snapshot ID]``, for example:

.. code-block:: bash

   $ apt update --snapshot 20240416T000000Z
   $ apt policy checkbox-ng -S 20240416T000000Z
   $ apt install checkbox-ng --snapshot 20240416T000000Z


Using a specific Snapshot ID for all apt commands
`````````````````````````````````````````````````

It is possible to set apt to use a particular snapshot for all apt
commands of a PPA repository. To do this, the specific Snapshot ID (e.g.
20240416T000000Z) can be used in place of “yes” in the relevant source.

For Ubuntu 24.04
''''''''''''''''

.. code-block::
   
   # In “/etc/apt/sources.list.d/checkbox-dev-ubuntu-beta-noble.list”
   Types: deb
   URIs: https://ppa.launchpadcontent.net/~checkbox-dev/beta/ubuntu/
   Suites: noble
   Components: main
   Signed-By: {KEY}
   Snapshot: 20240416T000000Z

For Ubuntu 23.10 and earlier
''''''''''''''''''''''''''''

.. code-block::

   # In “/etc/apt/sources.list.d/checkbox-dev-ubuntu-beta-jammy.list”
   deb [snapshot=20240416T000000Z] https://ppa.launchpadcontent.net/~checkbox-dev/beta/ubuntu jammy main


Disable Snapshot Service for a repository
`````````````````````````````````````````

For Ubuntu 24.04
''''''''''''''''

For Ubuntu 24.04 and later, snapshots are enabled automatically for supported
repositories. If you want to disable them for the Checkbox repository, edit the
sources file To include ``Snapshot: no``.

.. code-block::

   # In “/etc/apt/sources.list.d/checkbox-dev-ubuntu-beta-noble.list”
   Types: deb
   URIs: https://ppa.launchpadcontent.net/~checkbox-dev/beta/ubuntu/
   Suites: noble
   Components: main
   Signed-By: {KEY}
   Snapshot: no


For Ubuntu 23.10 and earlier
''''''''''''''''''''''''''''

On Ubuntu 23.10 and earlier the included version of apt did not automatically
detect snapshot support, so snapshots should not be enabled unless you have
added ``[snapshot=yes]`` to the relevant source.

SUsing snapshots for 18.04 or earlier
-------------------------------------

The Ubuntu snapshot service is available for 18.04 (bionic) and 16.04 (xenial)
but the apt version included does not support the ``--snapshot`` option. In this
case, it is required to set up manually the URL in your sources to point to a
specific snapshot. This option is also possible for later versions of Ubuntu.

Set manually the URL to the snapshot
------------------------------------

To set the URL to point to a specific snapshot, you have to edit:
``/etc/apt/sources.list.d/checkbox-dev-ubuntu-{ppa-name}-{ubuntu-version}.list``
and change the URL:

* ``ppa.launchpadcontent.net``  ->  ``snapshot.ppa.launchpadcontent.net`` 
* Append the timestamp to the end of the URL

For example: 

.. code-block:: bash

   # In “/etc/apt/sources.list.d/checkbox-dev-ubuntu-beta-bionic.list”
   deb https://ppa.launchpadcontent.net/checkbox-dev/beta/ubuntu bionic main

Should be changed to:

.. code-block:: bash

   # In “/etc/apt/sources.list.d/checkbox-dev-ubuntu-beta-bionic.list”
   deb https://snapshot.ppa.launchpadcontent.net/checkbox-dev/beta/ubuntu/20240416T000000Z bionic main

To revert to the latest version, you can remove ``snapshot`` part and the
timestamp from the URL.


See also
========
-  `Managing updates (Snaps) <https://snapcraft.io/docs/managing-updates>`_
-  `Ubuntu Snapshot Service <https://snapshot.ubuntu.com/>`_
