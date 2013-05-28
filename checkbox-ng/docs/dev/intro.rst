Getting started with development
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

PlainBox uses python3 for development. The core is really system independent
but you will need Ubuntu to really make the best of it and experience it as we
do. We encourage everyone to use the most recent Ubuntu release for
development. Usually this brings the best, most recent tools without having to
search for software on the Internet.

PlainBox has almost no dependencies itself, almost, because we depend on the
mighty :term:`CheckBox` project to provide us with a lot of existing
infrastructure. Testing PlainBox requires additional packages and some
non-packaged software. You will typically want to install it and take advantage
of the integration we provide.

.. note::

    If you are working with the source please be aware that PlainBox requires
    an installed copy of CheckBox. CheckBox in turns is has many scripts that
    depend on various system packages, including python packages that cannot be
    installed from pypi. If you were planning on using :command:`virtualenv`
    then please make sure to create it with the ``--system-site-packages``
    option.

Get the source
--------------

Source code for PlainBox is kept along with several other related projects in
the `checkbox` project on launchpad. You will need to use bzr to get a local
copy.

.. code-block:: bash

    $ bzr branch lp:checkbox

.. note::
    If you would rather use ``git`` you can also do that (and in fact, some of
    us already do). Head to `git-lp homepage <http://zyga.github.com/git-lp/>`_
    and follow the guide there to use git-lp with this project.

Get the dependencies
--------------------

You will need some tools to work on CheckBox. Scripted installation of almost
everything required is available (except for VirtualBox and Vagrant, those are
still manual).

From the top of the checkbox checkout run `mk-venv`, that script will install
all the missing dependencies and set you up for work on your machine.

Getting Vagrant
---------------

While developing PlainBox you will often need to run potentially dangerous
commands on your system, such as asking it to suspend and wake up
automatically. We also need to support a range of Ubuntu releases, going all
the way back to Ubuntu 12.04. This may cause compatibility issues that are
unnoticed all until they hit our CI system. To minimize this PlainBox uses
:term:`Vagrant` to create lightweight execution environments that transparently
share your source tree and allow you to quickly create and share testing
environment that can be deployed by any developer in minutes. Vagrant uses
:term:`VirtualBox` and while both are packaged in Ubuntu, unless you are
running Ubuntu 13.04 you should download and install the software from their
upstream projects. 

If you are running Ubuntu 13.04

.. code-block:: bash

    $ sudo apt-get install vagrant

If you are running earlier version of Ubuntu follow those two links to get started:

 * http://downloads.vagrantup.com/
 * https://www.virtualbox.org/wiki/Downloads

If you have not installed VirtualBox before, you must add yourself to the
``vboxusers`` group, log out and log back in again.

.. code-block:: bash

    $ sudo usermod -G vboxusers -a $USER 

Initialize virtualenv
---------------------

PlainBox will use a few unpackaged and bleeding-edge releases from :term:`pypi`
those are installed by additional script. By default the script assumes you
have a `/ramdisk` directory but you can pass any path as an argument for an
alternate location.

.. code-block:: bash

    $ ./mk-venv

After everything is set up you can activate the virtualenv environment with the
dot command. Note that there *is* a space between the dot and the forward
slash. You can repeat this command in as many shells as you like.

.. code-block:: bash

    $ . /ramdisk/venv/bin/activate

Once virtualenv is activated your shell prompt will be changed to reflect that.
You should now be able to run :command:`plainbox --help` to ensure everything
is working properly.

Initialize vagrant
------------------

Vagrant allows us to ship a tiny text file :file:`Vagrantfile` that describes
the development and testing environment. This file tells :command:`vagrant` how
to prepare a virtual machine for testing. If you never used it before you may
want to keep a tab open on `vagrant getting started guide
<http:`http://docs.vagrantup.com/v1/docs/getting-started/index.html>`_

We did all the hard work so that you don't have to, to get everything ready
just run one command:

.. code-block:: bash

    $ vagrant up

This will download vanilla Ubuntu cloud images, initialize VirtualBox,
provision virtual machines (one for each supported Ubuntu release) and allow
you to ssh into them for testing with one command.

This will take a moment, depending on the speed of your network. Once that is
done you should be able to log into, say, ``precise`` and run
:command:`plainbox --help` to see if everything is all right.

.. code-block:: bash

    $ vagrant ssh precise
    vagrant@vagrant-ubuntu-precise-32:~$ plainbox --help
    usage: plainbox [-h] [-v] {run,special,self-test} ...

    positional arguments:
      {run,special,self-test}
        run                 run a test job
        special             special/internal commands
        self-test           run integration tests

    optional arguments:
      -h, --help            show this help message and exit
      -v, --version         show program's version number and exit
    $ exit

Running PlainBox tests
^^^^^^^^^^^^^^^^^^^^^^

PlainBox is designed to be testable so it would be silly if it was hard to run
tests. Actually, there are many different ways to run tests. They all run the
same code so don't worry.

To test the current code you are working on you can:

- Run the :command:`./test-in-vagrant.sh` from the top-level directory. This
  will take the longer but will go over *all* the tests on *all* the supported
  versions of Ubuntu. It will run CheckBox unit-tests, PlainBox unit-tests and
  it will even run integration tests that actually execute jobs. 

- Run :command:`plainbox self-test --unit-tests` or 
  :command:`plainbox self-test --integration-tests`. This will execute all the
  tests right on your machine, without any virtualization (well, unless you do
  that after running :command:`vagrant ssh`). Typically you would run unit
  tests while being in a ``virtualenv`` with the ``plainbox`` package in
  development mode, as created by running :command:`python setup.py develop`

- Run :command:`./setup.py test` this will install any required test
  dependencies from pypi and run unit tests.

- Run the script :command:`test-with-coverage.sh` while being in a virtualenv.
  This will also compute testing code coverage and is very much recommended
  while working on new code and tests.

Submitting Patches
^^^^^^^^^^^^^^^^^^

We use `Launchpad <https://launchpad.net>`_ for most of our project management.
All code changes should be submitted as merge requests. Launchpad has
`extensive documentation <https://help.launchpad.net/>`_ on how to use various
facilities it provides.

In general we are open to contributions but we reserve the right to reject
patches if they don't fit into the needs of the :term:`Hardware Certification`.
If you have an idea go and talk to us on :abbr:`IRC (Internet Relay Chat)` on
the `#ubuntu-quality <irc://freenode.net:8001/#ubuntu-quality>`_ channel. 

We have some basic rules patch acceptance:

0. Be prepare to alter your changes.

   This is a meta-rule. One of the points of code reviews is to improve the
   proposal. That implies the proposal may need to change. You must be prepared
   and able to change your code after getting feedback.

   To do that efficiently you must structure your work in a way where each
   committed change works for you rather than against you. The rules listed
   below are a reflection of this.

1. Each patch should be a single logical change that can be applied.
  
   Don't clump lots of changes into one big patch. That will only delay review,
   make accepting feedback difficult and annoying. This may mean that the history
   has many small patches that can land in trunk in a FIFO mode. The oldest patch
   of your branch may be allowed to land and should make sense. This has
   implications on how general code editing should be performed. If you break some
   APIs then firsts introduce a working replacement, then change usage of the API
   and lastly remove any dead code.
  
2. Don't keep junk patches in your branch.
   
   Don't keep patches such as "fix typo" in your branch, that makes the review
   process more difficult as some reviewers will read your patches one by one.
   This is especially important if your changes are substantial.

3. Don't merge with trunk, rebase on trunk.

   This way you can keep your local delta as a collection of meaningful,
   readable patches. Reading the full diff and following the complex merge
   history (especially for long-lived branches) is difficult in practice.

4. Keep unrelated changes in separate branches.

   If you ware working on something and found a bug that needed immediate
   fixing, typo or anything else that is small and quick to fix, do it. Then
   take that patch out of your development branch and into a dedicated branch
   and propose it. As the small change is reviewed and lands you can remove
   that patch from your development branch.
  
   This is intended to help both the developer and the reviewer. Seemingly
   trivial patches may turn out to be more complicated than initially assumed
   (and may have their own feedback cycle and iterations). The reviewer can
   focus on logical changes and not on a collection of unrelated alterations.
   Lastly we may need to apply some fixes to other supported branches and
   release those.

5. Don't propose untested code.
   
   We generally like tests for new code. This is not a super-strict requirement
   but unless writing tests is incredibly hard we'd rather wait. If testing is
   hard we'd rather invest some time in refactoring the code or building
   required support infrastructure.
