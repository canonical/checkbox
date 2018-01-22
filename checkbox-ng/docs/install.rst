Installation
============

Debian Jessie and Ubuntu 14.04
------------------------------

You can install :term:`Plainbox` straight from the archive:

.. code-block:: bash

    $ sudo apt-get install plainbox

Ubuntu (Development PPA)
------------------------

Plainbox can be installed from a :abbr:`PPA (Personal Package Archive)` on
Ubuntu Precise (12.04) or newer.

.. code-block:: bash

    $ sudo add-apt-repository ppa:checkbox-dev/ppa && sudo apt-get update && sudo apt-get install plainbox

From python package index
-------------------------

Plainbox can be installed from :abbr:`pypi (python package index)`. Keep in
mind that you will need python3 version of ``pip``:

.. code-block:: bash

    $ pip3 install plainbox

We recommend using virtualenv or installing with the ``--user`` option.

From a .snap (for Ubuntu Snappy)
--------------------------------

You can build a local version of plainbox.snap and install it on any snappy
device (it is architecture independent for now, it doesn't bundle python
itself). You will have to have access to the checkbox source repository for
this.

.. code-block:: bash

    $ bzr branch lp:checkbox
    $ cd checkbox/plainbox/
    $ make

This will give you a new .snap file in the ``dist/`` directory. You can install
that snappy on a physical or virtual machine running snappy with the
``snappy-remote`` tool. Note that you will have to have the latest version of
the tool only available in the snappy PPA at this time. Refer to `snappy
umentation <https://developer.ubuntu.com/en/snappy/start/>`_ for details.

If you followed snappy documentation to run an amd64 image in kvm you can try
this code snippet to get started. Note that you can pass the use ``-snapshot``
option to kvm to make all the disk changes temporary. This will let you make
destructive changes inside the image without having to re-create the original
image each time.

.. code-block:: bash

    wget http://releases.ubuntu.com/15.04/ubuntu-15.04-snappy-amd64-generic.img.xz
    unxz ubuntu-15.04-snappy-amd64-generic.img.xz
    kvm -snapshot -m 512 -redir :8090::80 -redir :8022::22 ubuntu-15.04-snappy-amd64-generic.img
    snappy-remote --url=ssh://localhost:8022 install plainbox_0.22.dev0_all.snap

The password for the ``ubuntu`` user is ``ubuntu``. After installing you can
log in (or use the KVM window) and invoke the ``plainbox.plainbox`` executable
directly.
