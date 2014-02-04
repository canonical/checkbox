Installation
============

Debian Jessie and Ubuntu 14.04
------------------------------

You can install :term:`PlainBox` straight from the archive:

.. code-block:: bash

    $ sudo apt-get install plainbox

Ubuntu (Development PPA)
------------------------

PlainBox can be installed from a :abbr:`PPA (Personal Package Archive)` on
Ubuntu Precise (12.04) or newer.

.. code-block:: bash

    $ sudo add-apt-repository ppa:checkbox-dev/ppa && sudo apt-get update && sudo apt-get install plainbox

From python package index
-------------------------

PlainBox can be installed from :abbr:`pypi (python package index)`. Keep in
mind that you will need python3 version of ``pip`` and you will need to have
``python3-lxml`` installed (package names may differ depending on your
platform):

.. code-block:: bash

    $ pip3 install plainbox

We recommend using virtualenv or installing with the ``--user`` option.
