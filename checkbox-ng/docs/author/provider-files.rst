=========================
Provider Definition Files
=========================

Provider Definition Files are how :term:`PlainBox` learns about
:term:`providers <provider>`.

.. warning:: 

    Normally provider definition files are generated automatically by
    manage.py. They are generated both by ``manage.py install`` and
    ``manage.py develop``. It should not be necessary to create such
    a file by hand.

Lookup Directories
==================

PlainBox discovers and loads providers based on '.provider' files placed in one
of the following three directories:

* ``/usr/local/share/plainbox-providers-1``
* ``/usr/share/plainbox-providers-1``
* ``$XDG_DATA_HOME/plainbox-providers-1`` typically
  ``$HOME/.local/share/plainbox-providers-1``

File Structure
==============

Each provider file has similar structure based on the well-known ``.ini`` file
syntax. Square braces denote sections, each of which contains arbitrary
key-value entries.

Currently only one section is used, *PlainBox Provider*.

The [PlainBox Provider] Section
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

The following keys may be defined in this section:

name
    The format for the provider name is an RFC3720 IQN. This is specified in 
    :rfc:`3720#section-3.2.6.3.1`. It is used by PlainBox to uniquely identify 
    the provider.

version
    The version of this provider. It must be a sequence of decimal numbers with
    arbitrary many dots separating particular parts of the version string.

description
    A short description of the provider. This value can be localized.

jobs_dir
    Absolute pathname to a directory with :term:`job definitions <job>`
    as individual ``.txt`` files using the :doc:`job file format <jobs>`.

whitelists_dir
    Absolute pathname to a directory with :term:`whitelists <whitelist>`
    as individual ``.whitelist`` files using the
    :doc:`whitelist format <whitelists>`.

bin_dir
    Absolute pathname to a directory with additional executables required by
    any of the job definitions.

data_dir
    Absolute pathname to a directory with additional data files required by
    any of the job definitions.

locale_dir
    Absolute pathname to a directory with translation catalogues.
    The value should be suitable for :py:func:`bindtextdomain()`. This should
    not be specified, unless in special circumstances.

location
    Absolute pathname to a *base* directory that can be used to derive all of
    the other directories. If defined, any of the dir variables mentioned above
    gets an implicit default values:

    ================  =====================
        Variable          Default Value
    ================  =====================
    jobs_dir          $location/jobs
    whitelists_dir    $location/whitelists
    bin_dir           $location/bin
    data_dir          $location/data
    locale_dir        $location/locale
    locale_dir (alt)  $location/build/mo
    ================  =====================

Example
=======

An example provider definition file looks like this::

    [PlainBox Provider]
    name = 2013.com.canonical:myprovider
    version = 1.0 
    description = My Plainbox test provider
    location = /opt/2013.com.canonical.myprovider/
