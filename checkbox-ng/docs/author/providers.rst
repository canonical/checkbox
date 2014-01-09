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
a new whitelist, several new jobs and the scripts and test data supporting
those jobs. Before starting this tutorial you will need to have a running
version of Checkbox installed. You can either install it from the Ubuntu 
repositories by running ``apt-get install checkbox``, or if you prefer to work 
with the source, see :doc:`Getting started with development <../dev/intro>`.

#. To get started we create an initial template for our provider by running
   ``plainbox startprovider `date +"%Y"`.com.example:myprovider``.

#. This will create a directory called ``<thisyear>.com.example:myprovider`` 
   where this year is of course the current year. Change to this directory 
   and you will see that it contains::

    bin
    data
    integration-tests
    jobs
    manage.py
    README.md
    whitelists

#. Let’s create some jobs first by changing to the jobs directory. It currently
   contains a file called category.txt which serves as an example of how
   jobs should look. Let’s delete it and instead create a file called
   ``myjobs.txt``. This can contain the following simple jobs::

    plugin: shell
    name: myjobs/builtin_command
    command: true
    _description:
     An example job that uses built in commands.

    plugin: shell
    name: myjobs/this_provider_command
    command: mycommand
    _description:
      An example job that uses a test command provided by this provider.

    plugin: shell
    name: myjobs/other_provider_command
    command: removable_storage_test usb -l
    _description:
     An example job that uses a test command provided by another provider.
  
   At this point we can check that everything is working by running the command
   ``./manage.py info`` which displays some information about the provider. The
   output should be something like::

    [Provider MetaData]
	name: 2014.com.example:myprovider
	version: 1.0
    [Job Definitions]
	'myjobs/builtin_command', from jobs/myjobs.txt:1-5
	'myjobs/other_provider_command', from jobs/myjobs.txt:13-17
	'myjobs/this_provider_command', from jobs/myjobs.txt:7-11
    [White Lists]    
        'category', from whitelists/category.whitelist:1-1

   This shows all three jobs from the job file we added - great!

#. Next we need to change directory to ``bin`` to add the command used by the
   job ``myjobs/this_provider_command``. We create a file there called 
   ``mycommand`` which contains the following text::

    !#/usr/bin/bash
    test `cat $CHECKBOX_SHARE/data/testfile` == 'expected'

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

#. Lastly we need to add a whitelist that utilizes the jobs we created earlier.
   This whitelist can include jobs from other providers as well (and needs to
   include at least one from the default provider in fact). We need to change
   to the directory called ``whitelists``. As with the ``jobs`` directory 
   there is already an example file there called ``category.whitelist``. We can
   delete that and add a file called ``mywhitelist.whitelist``. The contents
   should be::

    miscellanea/submission_resources
    myjobs/builtin_command
    myjobs/other_provider_command
    myjobs/this_provider_command
    graphics/glxgears

   The ``miscellanea/submission_resources`` and ``graphics/glxgears`` jobs
   are from the default provider that is part of PlainBox.

   We can check that everything is correct with the whitelist by running the 
   ``./manage.py info`` command again. The output should be like::

    [Provider MetaData]
	name: 2014.com.example:myprovider
	version: 1.0
    [Job Definitions]
	'myjobs/builtin_command', from jobs/myjobs.txt:1-5
	'myjobs/other_provider_command', from jobs/myjobs.txt:13-17
	'myjobs/this_provider_command', from jobs/myjobs.txt:7-11
    [White Lists]
	'mywhitelist', from whitelists/mywhitelist.whitelist:1-5 
  
   Our new whitelist is listed there.

#. Now we have a provider we need to test it to make sure everything is correct.
