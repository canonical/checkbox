=========
Providers
=========

Providers are entities which provide Plainbox with jobs, scripts and whitelists, as well as miscellaneous data that may be used by tests. They work
by providing a configuration file which tells Plainbox the name and location of the provider. The provider needs to install this file to 
`/usr/share/plainbox-providers-1` (alternatively they can be placed in `~/.local/share/plainbox-providers-1`).

An example of such a file is::

    [PlainBox Provider]
    name = 2013.com.canonical:myprovider
    location = /usr/share/plainbox-providers-1/myprovider
    description = My Plainbox test provider

Note that normally this file is created automatically during the provider installation process and it should not be necessary to create such a file by hand.

It has these fields:

* name
    The format for the provider name is an RFC3720 IQN. This is specified in 
    :rfc:`3720#section-3.2.6.3.1`. It is used by PlainBox to uniquely identify 
    the provider.

* location
    The filesystem path where the providers directories are installed. This 
    location should contain at least one of the following directories:

    * jobs
        Should contain one or more files in the
        :doc:`Checkbox job file format <jobs>`.
    * bin
        Should contain one or more executable programs.
    * data
        Can contain any files that may be neccesary for implementing the jobs 
        contained in the provider, e.g. image files.
    * whitelists
        Should contain one or more files in the :doc:`Checkbox whitelist format <whitelists>`.

* description
    A short description of the provider.
