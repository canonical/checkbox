Adding tests from PTS to the Test Plan.
=======================================

To get the available tests run

$ phoronix-test-suite list-all-tests

The first column is the most important part of the listing, it will be used as
the job ID in the provider.

Let's pick `pts/tjbench` as an example.

Getting the list of dependencies for the new test.
--------------------------------------------------

`info` subcommand of PTS shows you extended info about the test (including
dependencies). But the dependencies are printed out like this: ::

    $ phoronix-test-suite info pts/tjbench

        (...)
        Software Dependencies:
        - Compiler / Development Libraries
        - Yasm Assembler
        - CMake
        (...)

To create a real list of dependencies I recommend creating a minimalistic
virtual machine with the target distro, and trying to install the test on it.
PTS will list all the dependencies it needs and will try installing them using
package manager (and prompting for password), like so: ::

    $ phoronix-test-suite install pts/go-benchmark 

    The following dependencies are needed and will be installed: 

    - golang

    s process may take several minutes.
    [sudo] password for user:

You can interrupt the process and grab that list.

The list of dependencies should be pasted to the ``Depends`` section of
``debian/control`` file on the ``packaging`` branch.

Adding the test to Checkbox job generator.
------------------------------------------

In order for Checkbox to "see" the test it has to be added to the resource job
that generates the test cases.
In ``units/pts.pxu`` there is a job with an id ``pts-job-generator``.
To add a job, add three ``echo`` invocation to the command part of the unit. ::

    echo id: pts/tjbench
    echo "name: tjbench is a JPEG decompression/compression benchmark part of libjpeg-turbo."
    echo 

The one in the middle is pasted from the description part of the output of
``phoronix-test-suite info pts/tjbench``

Using prefetched data for testing.
----------------------------------
PTS needs a lot of data on the system to perform testing. The data includes test
programs with libraries and the data sets to push to those programs.
In order to minimize the load on the network and the time needed for
testing, this provider can use local cache with prefetched data.

To create the cache start with a clean system (or rm -rf ~/.phoronix-test-suite)
and install all the tests. Then use the ~/.phoronix-test-suite as the cache.
Commands: ::

    $ rm -rf ~/.phoronix-test-suite/
    $ phoronix-test-suite install pts/tjbench
    $ cp ~/.phoronix-test-suite /var/cache/pts-cache 

For checkbox to use the cache environment variable $PTS_PRELOAD_PATH needs to be
pointing to that cache. ::

    $ export PTS_PRELOAD_PATH=/var/cache/pts-cache
    $ checkbox-cli


The cache is copied over to checkbox session, so any changes to the files inside
are done to the session-related copy.

