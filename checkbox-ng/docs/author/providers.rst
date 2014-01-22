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
        Should contain one or more files in the :doc:`Checkbox job file format <checkbox-job-format>`.
    * bin
        Should contain one or more executable programs.
    * data
        Can contain any files that may be neccesary for implementing the jobs 
        contained in the provider, e.g. image files.
    * whitelists
        Should contain one or more files in the :doc:`Checkbox whitelist format <whitelists>`.

* description
    A short description of the provider.

Tutorial
========

To best illustrate how providers work, we will walk through creating one
step-by-step. At the end of this tutorial you will have a provider which adds
a new :term:`whitelist`, several new jobs and the scripts and test data 
supporting those jobs. Before starting this tutorial you will need to have a 
running version of :term:`PlainBox` installed. You can either install it from 
the  repositories of Debian or its derivatives by running ``apt-get install 
plainbox``, or if you prefer to work with the source, see :doc:`Getting 
started with development <../dev/intro>`. There is also a Launchpad PPA with
the very latest development build for Ubuntu, which is `ppa:checkbox-dev/ppa`.

#. To get started we create an initial template for our provider by running
   ``plainbox startprovider 2014.com.example:myprovider``.

#. This will create a directory called ``2014.com.example:myprovider``
   where this year is of course the current year (2014 is when this document
   was written). Change to this directory and you will see that it contains::

    /bin
    /data
    /integration-tests
    /jobs
    manage.py
    README.md
    /whitelists

   The ``manage.py`` script is a helper script for developing the provider.
   It provides a set of commands which assist in validating the correctness
   of the provider and making it ready for distribution.

#. Let’s create some jobs first by changing to the jobs directory. It currently
   contains a file called category.txt which serves as an example of how
   jobs should look. Let’s delete it and instead create a file called
   ``myjobs.txt``. This can contain the following simple jobs::

    plugin: shell
    name: myjobs/shell_command
    command: true
    _description:
     An example job that uses a command provided by the shell.

    plugin: shell
    name: myjobs/provider_command
    command: mycommand
    _description:
      An example job that uses a test command provided by this provider.
  
   At this point we can check that everything looks okay by running the command
   ``./manage.py info`` which displays some information about the provider. The
   output should be something like::

    [Provider MetaData]
	name: 2014.com.example:myprovider
	version: 1.0
    [Job Definitions]
	'myjobs/builtin_command', from jobs/myjobs.txt:1-5
	'myjobs/provider_command', from jobs/myjobs.txt:7-11
    [White Lists]    
        'category', from whitelists/category.whitelist:1-1

   This shows all three jobs from the job file we added - great!

#. Next we need to change directory to ``bin`` to add the command used by the
   job ``myjobs/this_provider_command``. We create a file there called 
   ``mycommand`` which contains the following text::

    #!/bin/sh
    test `cat $CHECKBOX_SHARE/data/testfile` = 'expected'

   This needs to be executable to be used in the job command so we need to run
   ``chmod a+x mycommand`` to make it executable.

   You'll notice the command uses a file in ``$CHECKBOX_SHARE/data`` - we'll
   add this file to our provider next. 

#. Because the command we’re using uses a file that we expect to be located in
   ``$CHECKBOX_SHARE/data``, we need to add this file to our provider so that 
   after the provider is installed this file is available in that location. 
   First we need to change to the directory called ``data``, then as indicated 
   by the contents of the script we wrote in the previous step, we need to 
   create a file there called ``testfile`` with the contents::

    expected

   As simple as that!

#. Lastly we need to add a :term:`whitelist` that utilizes the jobs we created
   earlier. We need to change to the directory called ``whitelists``. As with
   the ``jobs`` directory  there is already an example file there called 
   ``category.whitelist``. We can delete that and add a file called 
   ``mywhitelist.whitelist``. The contents should be::

    myjobs/shell_command
    myjobs/provider_command

   The ``miscellanea/submission_resources`` and ``graphics/glxgears`` jobs
   are from the default provider that is part of PlainBox.

   We can check that everything is correct with the whitelist by running the 
   ``./manage.py info`` command again. The output should be like::

    [Provider MetaData]
	name: 2014.com.example:myprovider
	version: 1.0
    [Job Definitions]
	'myjobs/builtin_command', from jobs/myjobs.txt:1-5
	'myjobs/provider_command', from jobs/myjobs.txt:7-11
    [White Lists]
	'mywhitelist', from whitelists/mywhitelist.whitelist:1-2 
  
   Our new :term:`whitelist` is listed there.

#. Now we have a provider we need to test it to make sure everything is
   correct. The first thing to do is to install the provider so that it
   it visible to PlainBox. Run ``./manage.py develop`` then run 
   ``plainbox dev list provider``. Your provider should be in the list
   that is displayed.

#. We should also make sure the whole provider works end-to-end by running
   the :term:`whitelist` which it provides. Run the following command - 
   ``plainbox run -w whitelists/mywhitelist.whitelist``.

#. Assuming everything works okay, we can now package the provider for 
   distribution. This involves creating a basic ``debian`` directory
   containing all of the files needed for packaging your provider. Create
   a directory called ``debian`` at the base of your provider, and then
   create the following files within it.

   ``compat``::

    9

   ``control``::

    Source: plainbox-myprovider
    Section: utils
    Priority: optional
    Maintainer: Brendan Donegan <brendan.donegan@canonical.com>
    Standards-Version: 3.9.3
    X-Python3-Version: >= 3.2
    Build-Depends: debhelper (>= 9.2),
                   lsb-release,
                   python3 (>= 3.2),
                   python3-plainbox

    Package: plainbox-myprovider
    Architecture: all
    Depends: plainbox-provider-checkbox
    Description: My whitelist provider
     A provider for PlainBox.

   ``rules``::

    #!/usr/bin/make -f
    %:
        dh "$@"

    override_dh_auto_build:
        $(CURDIR)/manage.py install

   Note that the ``rules`` file must be executable. Make it so with 
   ``chmod a+x rules``. Also, be careful with the indentation in the
   file - all indents must be actual TAB characters, not four spaces
   for example.

   ``source/format``::

    3.0 (native)

   Finally we should create a ``changelog`` file. The easiest way to do this
   is to run the command ``dch --create 'Initial release.'``. You'll need to
   edit the field ``PACKAGE`` to the name of your provider and the field
   ``VERSION`` to something like ``0.1``.
