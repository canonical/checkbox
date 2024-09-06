.. _test_case:

=================
Writing Test Jobs
=================
Let's begin our journey in Checkbox test jobs by writing our first test job. Our
objective is to detect if the :term:`DUT` is correctly connected to the Internet.

Basic setup
===========

To follow this tutorial we recommend provisioning Checkbox from source. This is
ideal for prototyping. To provision Checkbox from source do the following:

.. code-block:: shell

    # first install python3 and python3-venv
    > sudo apt install python3 python3-venv python3-pip
    # clone the Checkbox repository
    > git clone https://github.com/canonical/checkbox.git
    # call the mk-venv script with the location of your virtualenv
    # Note: this mk-venv script sets up more than a normal virtual env. It also
    #       adds some Checkbox specific environment variables
    > cd checkbox/checkbox-ng
    > ./mk-venv ../../checkbox_venv
    # Activate the virtual environment
    > . ../../checkbox_venv/bin/activate
    # Install checkbox_support, it is a collection of utility scripts used by
    # many tests
    (checkbox_venv) > cd ../checkbox-support
    (checkbox_venv) > pip install -e .
    # Install the resource provider, we will use it further along in this tutorial
    (checkbox_venv) > cd ../providers/resource
    (checkbox_venv) > python3 manage.py develop

.. note::
    Remember to activate the virtual environment! You can also create an alias
    in your ``~/.bashrc`` to enable it when you need it.

Creating a new provider
=======================

Checkbox organizes and manages all jobs, test plans and other test units in various logical containers called :term:`Provider`. To be discovered by Checkbox, test units and related components must be defined within a provider.

Let's create a new Checkbox provider by using the Checkbox sub-command
``startprovider``.

.. code-block:: shell

   (checkbox_venv) > checkbox-cli startprovider 2024.com.tutorial:tutorial

Inside the provider you can see there are several directories. Definitions (the
descriptions of what we want to do) are contained in PXU files that we store in
the ``units`` subdirectory. We usually separate PXU files between the kind of
unit they contain (for example: resource, job, test plan, etc.) but for this
simple example we are going to use a single file.

Create the ``units/extended_tutorial.pxu``. This will be our first job:

.. code-block:: none

    id: network_test
    flags: simple
    _summary: A job that always passes
    command:
      echo This job passes!

.. note::
    The ``simple`` flag sets a few default fields for your unit, allowing you to
    easily develop a new test. See :ref:`jobs<job>` for a more comprehensive
    list of fields and flags

Now let's try to run this test job. Given that we have just created this
provider, Checkbox has no idea it exists. To make it discoverable, we have
to install it. The concept of a provider is very similar to a Python module.
The equivalent of the ``setup.py`` file for Checkbox is ``manage.py``. The
automated process should have created this file in the root of your provider. In order
to install a provider one can either use ``python3 manage.py install`` or
``python3 manage.py develop``. The difference is exactly the same between
``pip install`` and ``pip install -e``, namely, the second method allows us to
modify and use the provider without re-installing it.

Run the following command in the new `2024.com.tutorial:tutorial` directory:

.. code-block:: shell

    (checkbox_venv) > python3 manage.py develop

Now to run our test we can use the ``run`` sub-command. Try the following:

.. code-block:: none

    (checkbox_venv) > checkbox-cli run com.canonical.certification::network_test
    ===========================[ Running Selected Jobs ]============================
    =========[ Running job 1 / 1. Estimated time left (at least): 0:00:00 ]=========
    --------------------------[ A job that always passes ]--------------------------
    ID: com.canonical.certification::network_test
    Category: com.canonical.plainbox::uncategorised
    ... 8< -------------------------------------------------------------------------
    This job passes!
    ------------------------------------------------------------------------- >8 ---
    Outcome: job passed
    Finalizing session that hasn't been submitted anywhere: checkbox-run-2024-08-01T13.05.51
    ==================================[ Results ]===================================
     ☑ : A job that always passes


First concrete test example
===========================

OK, it worked, but this is not very useful. Let's go back and edit the job to
actually run a ping command. Replace the ``command`` section of the job with
``ping -c 1 1.1.1.1``, let's also update the summary as follows:

.. code-block:: none

    id: network_available
    flags: simple
    _summary: Test that the internet is reachable
    command:
      ping -c 1 1.1.1.1

.. note::

    Giving your test a significant ``summary`` and ``id`` is almost as important as
    giving it a significant output. These fields should provide enough context 
    to understand the test's purpose without reading the command section, 
    especially when troubleshooting failed tests.

Try to re-use the ``run`` command to test the update. You should now see something
like this:

.. code-block:: none

    (checkbox_venv) > checkbox-cli run com.canonical.certification::network_available
    ===========================[ Running Selected Jobs ]============================
    =========[ Running job 1 / 1. Estimated time left (at least): 0:00:00 ]=========
    ---------------------[ Test that the internet is reachable ]--------------------
    ID: com.canonical.certification::network_available
    Category: com.canonical.plainbox::uncategorised
     ... 8< ------------------------------------------------------------------------
     PING 1.1.1.1 (1.1.1.1) 56(84) bytes of data.
     64 bytes from 1.1.1.1: icmp_seq=1 ttl=57 time=19.5 ms

     --- 1.1.1.1 ping statistics ---
     1 packets transmitted, 1 received, 0% packet loss, time 0ms
     rtt min/avg/max/mdev = 19.507/19.507/19.507/0.000 ms
     ------------------------------------------------------------------------- >8--
    Outcome: job passed
    Finalizing session that hasn't been submitted anywhere: checkbox-run-2024-08-01T13.05.51
    ==================================[ Results ]===================================
     ☑ : Test that the internet is reachable

Dependencies
============

Let's keep in mind that our objective is to test if the network works correctly.
Currently we can check if we are able to ping some arbitrary host, but let's try
to actually measure the network speed and determine if it is acceptable.

Add the following job in ``units/extended_tutorial.pxu``:

Add a new test job to the same `.pxu` file:

.. code-block:: none

    id: network_speed
    flags: simple
    _summary: Test that the network speed is acceptable
    command:
      curl -Y 600 -o /dev/null \
        https://cdimage.ubuntu.com/ubuntu-mini-iso/noble/daily-live/current/noble-mini-iso-amd64.iso

Try to run the test via the run command (depending on your Internet connection speed, it might take a while since the ``curl`` command downloads an ISO file!). You should see something like this:

.. code-block:: none

    (checkbox_venv) > checkbox-cli run com.canonical.certification::network_speed
    ===========================[ Running Selected Jobs ]============================
    =========[ Running job 1 / 1. Estimated time left (at least): 0:00:00 ]=========
    -----------------[ Test that the network speed is acceptable ]------------------
    ID: com.canonical.certification::network_speed
    Category: com.canonical.plainbox::uncategorised
    ... 8< -------------------------------------------------------------------------
      % Total    % Received % Xferd  Average Speed   Time    Time     Time  Current
                                     Dload  Upload   Total   Spent    Left  Speed
    100  5105    0  5105    0     0   1237      0 --:--:--  0:00:04 --:--:--  1237
    ------------------------------------------------------------------------- >8 ---
    Outcome: job passed
    Finalizing session that hasn't been submitted anywhere: checkbox-run-2024-08-02T12.21.55
    ==================================[ Results ]===================================
     ☑ : Test that the network speed is acceptable



We can save time and resources skipping this test if the ping test didn't work.
Let's add a dependency of the second test on the first one like follows:

.. code-block:: none
    :emphasize-lines: 4

    id: network_speed
    flags: simple
    _summary: Test that the network speed is acceptable
    depends: network_available
    command:
      curl -Y 600 -o /dev/null \
        https://cdimage.ubuntu.com/ubuntu-mini-iso/noble/daily-live/current/noble-mini-iso-amd64.iso

Try to run the job via the following command
``checkbox-cli run com.canonical.certification::network_speed``.
As you can see, checkbox presents the following result:

.. code-block:: none

    [...]
    ==================================[ Results ]===================================
     ☑ : Test that the internet is reachable
     ☑ : Test that the network speed is acceptable

If asked to run a job that depends on another job, Checkbox will try to pull
the other job and its dependencies automatically. If Checkbox is unable to do
so we can always force this behavior by listing the jobs in order of dependence
in the run command:

.. code-block:: none

    (checkbox_venv) > checkbox-cli run com.canonical.certification::network_available \
      com.canonical.certification::network_speed

Finally let's test that this actually works. To do so we can temporarily change the
command section of ``network_available`` to ``exit 1``. This
is the new Result that Checkbox will present:

.. code-block:: none

    [...]
    -----------------[ Test that the network speed is acceptable ]------------------
    ID: com.canonical.certification::network_speed
    Category: com.canonical.plainbox::uncategorised
    Job cannot be started because:
      - required dependency 'com.canonical.certification::network_available' has failed
    Outcome: job cannot be started
    Finalizing session that hasn't been submitted anywhere: checkbox-run-2024-08-02T13.31.58
    ==================================[ Results ]===================================
     ☒ : Test that the internet is reachable
     ☐ : Test that the network speed is acceptable

Customize tests via environment variables
=========================================

Sometimes it is hard to set a unique value for a test parameter because it may
depend on a multitude of factors. Notice that our previous test has a very
ISP-generous interpretation of the acceptable speed, which might not align 
with all customers' expectations. At the same time, it is hard to define an acceptable speed for
any interface and all machines. In Checkbox we use environment variables
to customize testing parameters that have to be defined per-machine/test run.
Consider the following:

.. code-block:: none

    id: network_speed
    flags: simple
    _summary: Test that the network speed is acceptable
    environ:
      ACCEPTABLE_BYTES_PER_SECOND_SPEED
    command:
      echo Testing for the limit speed: ${ACCEPTABLE_BYTES_PER_SECOND_SPEED:-600}
      curl -y 1 -Y ${ACCEPTABLE_BYTES_PER_SECOND_SPEED:-600} -o /dev/null \
        https://cdimage.ubuntu.com/ubuntu-mini-iso/noble/daily-live/current/noble-mini-iso-amd64.iso

Before running the test we have to define a Checkbox configuration. Note that
if we were using a test plan, we could run it with a launcher, but the
``run`` command doesn't take a launcher parameter, so we have to use a
configuration file. Place the following in ``~/.config/checkbox.conf``.

.. code-block:: ini

    [environment]
    ACCEPTABLE_BYTES_PER_SECOND_SPEED=60000000

Running the test with the usual command, you will notice that now the limit is
higher:

.. code-block:: none

    (checkbox_venv) > checkbox-cli run com.canonical.certification::network_speed
    [...]
    Testing for the limit speed: 60000000
      % Total    % Received % Xferd  Average Speed   Time    Time     Time  Current
                                     Dload  Upload   Total   Spent    Left  Speed
    100  5105    0  5105    0     0   6645      0 --:--:-- --:--:-- --:--:--  6647
    ------------------------------------------------------------------------- >8 ---
    Outcome: job passed
    Finalizing session that hasn't been submitted anywhere: checkbox-run-2024-08-06T14.17.23
    ==================================[ Results ]===================================
     ☑ : Test that the network speed is acceptable


.. warning::

    Checkbox jobs do not automatically inherit any environment variable from
    the parent shell, global env or any other source. There are a few exceptions
    but in general:

    - Any variable that is not in the ``environ`` section of a job is not set
    - Any variable not declared in the ``environment`` section of a launcher or configuration file is not set

If you decide to parametrize your tests using environment variables, always
check if they are set or give them a default value via ``${...:-default}``.
If you expect a variable to be set and it is not, always fail the test stating
what variable you needed and what it was for. If you decide to use a default
value, always output the value the test is going to use in the test log so that
when you have to investigate why something went wrong, it is trivial to
reproduce the tests with the parameters that may have made it fail.

Resources
=========

Before even thinking to test if we are connected to the Internet a wise
question to ask would be: do we even have a network interface? :term:`Resource`
jobs gather information about a system, printing them in a ``key: value`` format
that Checkbox parses. Let's create a resource job to assess the network interface status.

Create a new job with the following content:

.. code-block:: none

    id: network_iface_info
    _summary: Fetches information of all network intefaces
    plugin: resource
    command:
      ip -details -json link show | jq -r '
          .[] | "interface: " + .ifname +
          "\nlink_info_kind: " + .linkinfo.info_kind +
          "\nlink_type: " + .link_type + "\n"'

We are using ``jq`` to parse the output of the ``ip`` command, which means we need to make sure ``jq`` is available. We need to declare this in
the correct spot, otherwise this will not work in a reproducible manner. Let's add
a packaging meta-data unit to our ``units/extended_tutorial.pxu`` file:

.. code-block:: none

    id: extended_tutorial_dependencies
    unit: packaging meta-data
    os-id: debian
    Depends:
      jq

If you now run the following command you will notice a validation error.

.. code-block:: none


    (checkbox_venv) > python3 manage.py validate
    [...]
    error: ../base/units/submission/packaging.pxu:3: field 'Depends', clashes with 1 other unit, look at: ../base/units/submission/packaging.pxu:1-3, units/extended_tutorial.pxu:1-4
    Validation of provider tutorial has failed

Opening the file that the validator complains about, you will notice that the
jq dependency is already required by a base provider test. We can rely on the
base provider, so we can safely remove this dependency from our provider.

.. warning::
   The next steps require the  command-line tool ``jq``. 
   If you don't have ``jq`` installed on your machine, install it either via
   ``sudo snap install jq`` or ``sudo apt install jq``.

Now that we have this new resource let's run it to see what the output is

.. code-block:: none

    (checkbox_venv) >  checkbox-cli run com.canonical.certification::network_iface_info
    ===========================[ Running Selected Jobs ]============================
    =========[ Running job 1 / 1. Estimated time left (at least): 0:00:00 ]=========
    ----------------[ Fetches information of all network intefaces ]----------------
    ID: com.canonical.certification::network_iface_info
    Category: com.canonical.plainbox::uncategorised
    ... 8< -------------------------------------------------------------------------
    interface: lo
    link_info_kind:
    link_type: loopback

    interface: enp2s0f0
    link_info_kind:
    link_type: ether

    interface: enp5s0
    link_info_kind:
    link_type: ether

    interface: wlan0
    link_info_kind:
    link_type: ether

    interface: lxdbr0
    link_info_kind: bridge
    link_type: ether

    interface: veth993f2cd0
    link_info_kind: veth
    link_type: ether

    interface: tun0
    link_info_kind: tun
    link_type: none

We now add a ``requires:`` constraint to our jobs so that, if no interface
that could possibly connect to the Internet is on the machine, we can
skip them instead of failing.

.. code-block:: none
    :emphasize-lines: 4,5

    id: network_available
    flags: simple
    _summary: Test that the Internet is reachable
    requires:
      network_iface_info.link_type == "ether"
    command:
      ping -c 1 1.1.1.1

If we now run the ``network_available`` test, Checkbox will also automatically
pull ``network_iface_info``. Note that this only happens because both are in
the same namespace.

.. code-block:: none

    (checkbox_venv) > checkbox-cli run com.canonical.certification::network_available
    ===========================[ Running Selected Jobs ]============================
    =========[ Running job 1 / 2. Estimated time left (at least): 0:00:00 ]=========
    ----------------[ Fetches information of all network intefaces ]----------------
    [...]
    =========[ Running job 2 / 2. Estimated time left (at least): 0:00:00 ]=========
    --------------------[ Test that the Internet is reachable ]---------------------
    [...]
    ==================================[ Results ]===================================
     ☑ : Fetches information of all network intefaces
     ☑ : Test that the internet is reachable

Are we done then? Almost, there are a few issues with our resource job. The
first and most relevant is that the ``resource`` constraint we have written
seems to work, but if we analyze the output what we have written actually
over-matches (as ``veth993f2cd0`` is also an ``ether`` device, but it is not a
valid interface to use to connect to the Internet). We can easily fix this by
updating the expression as follows but take note of what happened.

.. warning::
    It is actually difficult to write a significant resource expression. This
    time we got "lucky", and we could notice the mistake on our own machine, but
    this may not be the always the case. In general make your resource
    expressions as restrictive as possible.

.. code-block:: none

    id: network_available
    [...]
    requires:
      (network_iface_info.link_info_kind == "" and network_iface_info.link_type == "ether")

The second issue is harder to fix. Checkbox is currently built for a multitude
of Ubuntu versions, including 16.04. If we inspect the 16.04
`manual <https://manpages.ubuntu.com/manpages/xenial/man8/ip.8.html>`_ of the
``ip`` command we notice one thing: the version shipped with Xenial doesn't support
the ``--json`` flag.

.. warning::
    When you use a pre-installed package, always check if all versions support
    your use case and if there is a version available for all target versions.

If we want to contribute this new test upstream, the pull request will be
declined for this reason. We could work around this in a multitude of way but
what we should have done to begin with is ask ourselves: Is there a resource
job that already does what we need? We can ask Checkbox via the ``list``
command.

.. code-block:: none

    (checkbox_venv) > checkbox-cli list all-jobs -f "{id} -> {_summary} : {plugin}\n" | grep resource | grep device
    [...]
    device -> Collect information about hardware devices (udev) : resource
    [...]

We can now update our job, but with what ``requires``? Let's run the ``device``
job and check the output.

.. code-block:: none

    (checkbox_venv) > checkbox-cli run com.canonical.certification::device | grep -C 15 wlan
    [...]
    category: WIRELESS
    interface: wlan0
    [...]

    (checkbox_venv) > checkbox-cli run com.canonical.certification::device | grep -C 15 enp
    [...]
    category: NETWORK
    interface: enp5s0
    [...]

Let's propagate this newfound knowledge over to our ``requires`` constraint:

.. code-block:: none

    requires:
      (device.category == "NETWORK" or device.category == "WIRELESS")

Template Jobs
=============

Currently we are testing if any interface has access to the internet in our
demo test. This may not be exactly what we want. When testing a device we may
want to plug in every interface and test them all just to be sure that they all
work. Ideally, the test that we want to do is the same for each interface.

Templates allow us to do exactly this. Let's try to implement per-interface
connection checking.

.. note::

    We'll switch back to the tutorial resource job only because that way we can
    easily tweak it. It is desirable if you are developing a test and need a
    resource to have a "fake" resource that just emulates the real one with
    echo. The reason is that this way you can iterate on a different machine
    without relying on the "real" hardware while developing.

Create a new unit that uses the ``network_iface_info`` resource and, for now,
only print out the ``interface`` field to get the hang of it. It should look
something like this:

.. code-block:: none

    unit: template
    template-resource: network_iface_info
    template-unit: job
    id: network_available_{interface}
    template-id: network_available_interface
    command:
      echo Testing {interface}
    _summary: Test that the internet is reachable via {interface}
    flags: simple

.. note::
    If you are unsure about what a template will be expanded to, you can always
    use echo to print and debug it. This is the most immediate tool you have at
    your disposal. For a more principled solution see the Test Plan Extended
    Tutorial.

We can technically still use ``run`` to execute this job but note that the job
id is, and must, be calculated at runtime, as ids must be unique. Try to run
the following:

.. code-block:: none

    (checkbox_venv) > checkbox-cli run com.canonical.certification::network_available_interface
    ===========================[ Running Selected Jobs ]============================
    Finalizing session that hasn't been submitted anywhere: checkbox-run-2024-08-06T10.02.00
    ==================================[ Results ]===================================
    (checkbox_venv) >

As you can see, nothing was ran. There are two reasons:

- Templates don't automatically pull the ``template-resource`` dependency when
  executed via ``run``
- Templates can't be executed via ``run`` using their ``template-id``

We can easily solve the situation in this example by manually pulling the
dependency and using the explicit id of the job that will be generated or a
regex:

.. code-block:: none

    (checkbox_venv) > checkbox-cli run com.canonical.certification::network_iface_info "com.canonical.certification::network_available_wlan0"
    [...]
    ==================================[ Results ]===================================
     ☑ : Fetches information of all network intefaces
     ☑ : Test that the internet is reachable via wlan0

    # or alternatively with the regex (note the " " around the id, they are important!)
    (checkbox_venv) > checkbox-cli run com.canonical.certification::network_iface_info "com.canonical.certification::network_available_.*"
    [...]
    ==================================[ Results ]===================================
     ☑ : Fetches information of all network intefaces
     ☑ : Test that the internet is reachable via lo
     ☑ : Test that the internet is reachable via enp2s0f0
     ☑ : Test that the internet is reachable via enp5s0
     ☑ : Test that the internet is reachable via wlan0
     ☑ : Test that the internet is reachable via lxdbr0
     ☑ : Test that the internet is reachable via vetha6dd5923

This is a quick and dirty solution that can be handy if you want to run a test
and you can manually resolve the dependency chain that is not resolved by
Checkbox but this can be, in practice, often hard or impossible.
For a more principled solution see the the Test Plan Tutorial section.

Let's then modify the job so that it actually does the test and use the template
filter so that we don't generate tests for interfaces that we know will
not work:

.. code-block:: none
    :emphasize-lines: 6,7,10

    unit: template
    template-resource: network_iface_info
    template-unit: job
    id: network_available_{interface}
    template-id: network_available_interface
    template-filter:
      network_iface_info.link_type == "ether" and network_iface_info.link_info_kind == ""
    command:
      echo Testing {interface}
      ping -I {interface} 1.1.1.1 -c 1
    _summary: Test that the internet is reachable via {interface}
    flags: simple

Re-running the jobs, we now see way less jobs, although a few are failing:

.. code-block:: none

    (checkbox_venv) > checkbox-cli run com.canonical.certification::network_iface_info "com.canonical.certification::network_available_.*"
    [...]
    =========[ Running job 1 / 3. Estimated time left (at least): 0:00:00 ]=========
    --------------[ Test that the internet is reachable via enp2s0f0 ]--------------
    ID: com.canonical.certification::network_available_enp2s0f0
    Category: com.canonical.plainbox::uncategorised
    ... 8< -------------------------------------------------------------------------
    Testing enp2s0f0
    ping: Warning: source address might be selected on device other than: enp2s0f0
    PING 1.1.1.1 (1.1.1.1) from 192.168.43.79 enp2s0f0: 56(84) bytes of data.

    --- 1.1.1.1 ping statistics ---
    1 packets transmitted, 0 received, 100% packet loss, time 0ms
    ------------------------------------------------------------------------- >8 ---
    Outcome: job failed
    [...]
    ==================================[ Results ]===================================
     ☑ : Fetches information of all network intefaces
     ☒ : Test that the internet is reachable via enp2s0f0
     ☒ : Test that the internet is reachable via enp5s0
     ☑ : Test that the internet is reachable via wlan0

The fact that these tests are failing, on my machine, is due to the fact that
the interfaces are down. This is not clear from the output of the job nor
from the outcome (I.E. the outcome of a broken interface is the same as the
outcome of an unplugged one). This is not desirable, it makes reviewing the
test results significantly more difficult. There are two ways to fix this
issue, the first is to output more information about the interface we are
testing so that the reviewer can then go through the log and catch the fact
that the interface is down. This works but still requires manual intervention
every time we run the tests, as they fail, and we need to figure out why.

Another possibility is to generate the jobs, via the template, but make
Checkbox skip the tests when the interface is down. This produces a job per
interface, but marks the ones for interfaces that are "down" as skipped with
a clear reason.

Update the resource job with the following new line:

.. code-block:: none
    :emphasize-lines: 9

    id: network_iface_info
    _summary: Fetches information of all network intefaces
    plugin: resource
    command:
      ip -details -json link show | jq -r '
          .[] | "interface: " + .ifname +
          "\nlink_info_kind: " + .linkinfo.info_kind +
          "\nlink_type: " + .link_type +
          "\noperstate: " + .operstate + "\n"'

Now let's modify the template to add a ``requires`` to the generated job:

.. code-block:: none
    :emphasize-lines: 8,9

    unit: template
    template-resource: network_iface_info
    template-unit: job
    id: network_available_{interface}
    template-id: network_available_interface
    template-filter:
      network_iface_info.link_type == "ether" and network_iface_info.link_info_kind == ""
    requires:
      (network_iface_info.interface == "{interface}" and network_iface_info.operstate == "UP")
    command:
      echo Testing {interface}
      ping -I {interface} 1.1.1.1 -c 1
    _summary: Test that the internet is reachable via {interface}
    flags: simple

.. note::
   For historical reasons the grammar of resource expressions is currently
   broken. Even though they shouldn't be, parenthesis around this requires are
   compulsory!

Re-running the jobs we see the difference, now the jobs are there and skipped.
The reason why they were skipped is clear from the output log (and the eventual
submission).

.. code-block:: none
    :emphasize-lines: 6,7,12,13

    (checkbox_venv) > checkbox-cli run com.canonical.certification::network_iface_info "com.canonical.certification::network_available_.*"
    =========[ Running job 1 / 3. Estimated time left (at least): 0:00:00 ]=========
    --------------[ Test that the internet is reachable via enp2s0f0 ]--------------
    ID: com.canonical.certification::network_available_enp2s0f0
    Category: com.canonical.plainbox::uncategorised
    Job cannot be started because:
     - resource expression '(network_iface_info.interface == "enp2s0f0" and network_iface_info.operstate == "UP")' evaluates to false
    Outcome: job cannot be started
    [...]
    ==================================[ Results ]===================================
     ☑ : Fetches information of all network intefaces
     ☐ : Test that the internet is reachable via enp2s0f0
     ☐ : Test that the internet is reachable via enp5s0
     ☑ : Test that the internet is reachable via wlan0

Let me conclude this section by highlighting this last point. See the
difference between ``template-filter`` and ``requires``.

- The resources filtered by the ``template-filter`` do not generate a test, we
  do this when the generated test would not make sense (for example, connection
  test for the loopback interface)
- The resources that, when filtered by the ``resource`` expression is empty,
  marks the job as skipped. We do this when the job makes sense (for example,
  the interface exists) but the current situation makes it impossible for it
  to pass for an external reason (for example, the ethernet port may work but
  it is not currently plugged in)

Dealing with complexity - Python
================================

The ``network_available`` test that we have created during this tutorial is
very simple but, in the real world things are not as simple. For example,
right now we are only pinging once from the test, if the ping goes through
the test is considered successful; otherwise, it's a failure. This works in our simple scenario while
developing the test, but when hundreds of devices all try to ping at the same
time things can get messy quickly, and messages can get lost. One possible
evolution for this test is to do more pings and use the packet
loss output to decide if we can call the test a success or a failure.

Translating the test to Python
------------------------------

While we could do this with a tall jenga tower entirely constituted of pipes,
tee and ``awk`` commands, always keep in mind, the best foot gun is the one we
don't use. Checkbox allows you to write hundreds of lines of code in the
command section but this doesn't make it a good idea. When we need to evolve
beyond a few lines of bash we always suggest a rewrite in Python and to add
proper unit tests.

.. note::
    While there is no formal rule on the maximum size or complexity of a
    command section, as a rule of thumb avoid using nested ifs/for loops,
    multiple pipes and destructive redirection within a command section. You
    will thank us later.

Create a new directory in the provider: ``bin/``. Create
a new python file in ``bin/`` and call it ``network_available.py`` and make it
executable (``chmod +x network_available.py``).

Let's translate the previous test into Python first:

.. code-block:: python

    #!/usr/bin/env python3
    import sys
    import argparse
    import subprocess


    def parse_args(argv):
        parser = argparse.ArgumentParser()
        parser.add_argument(
            "interface", help="Interface to connectivity test"
        )
        return parser.parse_args(argv)


    def network_available(interface):
        print("Testing", interface)
        return subprocess.check_call(
            ["ping", "-I", interface, "-c", "1", "1.1.1.1"]
        )


    def main(argv=None):
        if argv is None:
            argv = sys.argv[1:]
        args = parse_args(argv)
        ping_test(args.interface)


    if __name__ == "__main__":
        main()

.. note::
    A few important things to notice about the script:

    #. We use Black to format all tests and source files in Checkbox with a custom config: ``line-length = 79``.
    #. We make files in ``bin/`` executable, this is convenient, but remember to put a shebang on the first line.
    #. If we call a subprocess (like ping) we try to avoid capturing the output if we don't need it. Makes it way easier to debug test failures when they occur.

Modify now the ``network_available_interface`` job to call our new script.
Remember that any script in the ``bin/`` directory is directly accessible by
any test in the same provider.

.. code-block::
    :emphasize-lines: 6

    unit: template
    [...]
    template-id: network_available_interface
    [...]
    command:
      network_available.py {interface}

.. note::
   Call the script by name without ``./`` in front

We are now ready to extract the information from the log of the command.
Update the script ``network_available`` as follows:

.. code-block:: python

    def parse_args(argv):
        parser = argparse.ArgumentParser()
        parser.add_argument(
            "interface", help="Interface which will be used to ping"
        )
        parser.add_argument(
            "--threshold",
            "-t",
            help="Maximum percentage of lost of packets to mark the test as ok",
            default="90",
        )
        return parser.parse_args(argv)


    def network_available(interface, threshold):
        print("Testing", interface)
        ping_output = subprocess.check_output(
            ["ping", "-I", interface, "-c", "10", "1.1.1.1"],
            universal_newlines=True,
        )
        print(ping_output)
        if "% packet loss" not in ping_output:
            raise SystemExit(
                "Unable to determine the % packet loss from the output"
            )
        perc_packet_loss = ping_output.rsplit("% packet loss", 1)[0].rsplit(
            maxsplit=1
        )[1]
        if float(perc_packet_loss) > float(threshold):
            raise SystemExit(
                "Detected packet loss ({}%) is higher than threshold ({}%)".format(
                    perc_packet_loss, threshold
                )
            )
        print(
            "Detected packet loss ({}%) is lower than threshold ({}%)".format(
                perc_packet_loss, threshold
            )
        )


    def main(argv=None):
        if argv is None:
            argv = sys.argv[1:]
        args = parse_args(argv)
        network_available(args.interface, args.threshold)

.. note::
    A few tips and tricks in the code above:

    - We print out the command output, try to not hide intermediate steps if possible.
    - We don't use a regex: if you can, use simple splits, they make debugging easier and the code more maintainable.
    - We not only output the decision, but also the parameters that took us to that conclusion. Makes it way easier to interpret the output log.

Unit testing the Python scripts
-------------------------------

Notice how we don't push you to make ``bin/`` script simple to understand.
Although the example in this tutorial is not the most complex, there are
situations and tests that do need to be more on the complex side, this is
why the ``bin/`` vs ``commands:`` separation came to be. One important thing
to consider though, is that with the complexity we are introducing, we are also
creating a future burden for whoever will have to maintain our test. For this
reason we highly encourage you (and straight up require if you want to
contribute to the main Checkbox repository), to write unit tests for your
scripts.

Create a new ``tests/`` directory and a ``test_network_available.py`` file
inside it.

.. note::
   You can call your tests however you want but we encourage to make the naming
   convention uniform at the very least. This tutorial will use the Checkbox
   naming convention.

The most important thing with your unit tests is that you provide, for each
function, at least the "happy path" that you have predicted will exist in
your script. If you have predicted some error path along it (or you have seen
it happen), create a test for it as well. It is important that each test checks
for exactly one situation, if possible. Consider the following:

.. code-block:: python

    import unittest
    import textwrap
    from unittest import mock

    import network_available


    class TestNetworkAvailable(unittest.TestCase):

        @mock.patch("subprocess.check_output")
        def test_nominal(self, check_output_mock):
            check_output_mock.return_value = textwrap.dedent(
                """
                PING 1.1.1.1 (1.1.1.1) from 192.168.1.100 wlan0: 56(84) bytes
                64 bytes from 1.1.1.1: icmp_seq=1 ttl=53 time=39.0 ms
                64 bytes from 1.1.1.1: icmp_seq=2 ttl=53 time=143 ms

                --- 1.1.1.1 ping statistics ---
                2 packets transmitted, 2 received, 0% packet loss, time 170ms
                rtt min/avg/max/mdev = 34.980/60.486/142.567/31.077 ms
                """
            ).strip()
            network_available.network_available("wlan0", "90")
            self.assertTrue(check_output_mock.called)

        @mock.patch("subprocess.check_output")
        def test_failure(self, check_output_mock):
            check_output_mock.return_value = textwrap.dedent(
                """
                PING 1.1.1.1 (1.1.1.1) from 192.168.1.100 wlan0: 56(84) bytes
                64 bytes from 1.1.1.1: icmp_seq=1 ttl=53 time=39.0 ms

                --- 1.1.1.1 ping statistics ---
                10 packets transmitted, a received, 90% packet loss, time 170ms
                rtt min/avg/max/mdev = 34.980/60.486/142.567/31.077 ms
                """
            ).strip()
            with self.assertRaises(SystemExit):
                network_available.network_available("wlan0", "0")

.. note::
   We use ``self.assertTrue(check_output_mock.called)`` instead of
   ``check_output_mock.assert_called_once()``. The reason is that we have to be
   compatible (in tests as well!) with Python 3.5 and
   ``Mock.assert_called_once`` was introduced in Python 3.6. If you don't know
   when a function was introduced, refer to `the Python documentation
   <https://docs.python.org/3/library/unittest.mock.html#unittest.mock.Mock.assert_called_once>`_.
   For example, if you check the documentation for `Mock.assert_called_once<https://docs.python.org/3/library/unittest.mock.html#unittest.mock.Mock.assert_called_once>`_ you will see *Added in version 3.6.*

To run the tests go to the root of the provider and run the following:

.. code-block:: none

    (checkbox_venv) > python3 manage.py test -u
    test_failure (test_network_available.TestNetworkAvailable.test_failure) ...
    [...]
    test_nominal (test_network_available.TestNetworkAvailable.test_nominal) ...
    [...]

    ----------------------------------------------------------------------
    Ran 2 tests in 0.002s

    OK

.. note::
   You can also run ``python3 manage.py test`` without the ``-u``. Every
   provider comes with a set of builtin tests like ``shellcheck``
   (for the ``commands:`` sections) and flake8 (for all ``bin/*.py`` files).
   Not providing ``-u`` will simply run all tests.

Gathering Coverage from Unit Tests
----------------------------------

In Checkbox we have a coverage requirement for new pull requests.
This is to ensure that new contributions do not add source paths that are not
explored in testing and therefore easy to break down the line with any change.

If you want to collect the coverage of your contribution you can run the
following:

.. code-block:: none

    (checkbox_venv) > python3 -m coverage run manage.py test -u
    (checkbox_venv) > python3 -m coverage report --include=bin/*
    Name                       Stmts   Miss  Cover
    ----------------------------------------------
    bin/network_available.py      25     10    60%
    ----------------------------------------------
    TOTAL                         25     10    60%
    (checkbox_venv) > python3 -m coverage report --include=bin/* -m
    Name                       Stmts   Miss  Cover   Missing
    --------------------------------------------------------
    bin/network_available.py      25     10    60%   8-18, 29, 49-52, 56
    --------------------------------------------------------
    TOTAL                         25     10    60%

    # You can also get an HTML report with the following
    # it is very convenient as you can see file per file what lines are covered
    # in
    (checkbox_venv) > python3 -m coverage html

As you can see we are way below the coverage target (90%) but this is difficult to
fix, we should add an end to end test of the main function, so that we
cover it but, most importantly, we leave trace in the test file of an expected
usage of the script. Add the following to ``tests/test_network_available.py``

.. code:: python

    class TestMain(unittest.TestCase):

        @mock.patch("subprocess.check_output")
        def test_nominal(self, check_output_mock):
            check_output_mock.return_value = textwrap.dedent(
                """
                PING 1.1.1.1 (1.1.1.1) from 192.168.1.100 wlan0: 56(84) bytes
                64 bytes from 1.1.1.1: icmp_seq=1 ttl=53 time=39.0 ms
                64 bytes from 1.1.1.1: icmp_seq=2 ttl=53 time=143 ms

                --- 1.1.1.1 ping statistics ---
                2 packets transmitted, 2 received, 0% packet loss, time 170ms
                rtt min/avg/max/mdev = 34.980/60.486/142.567/31.077 ms
                """
            ).strip()
            network_available.main(["--threshold", "20", "wlan0"])
            self.assertTrue(check_output_mock.called)



Dealing with complexity - Source builds
=======================================

There are very few situations where we need to include a source file to be
compiled in a provider. Checkbox supports building and delivering binaries
that can then be used in tests similarly to script we placed in the
``bin/`` directory but in most cases we would advise you against it. The most
common usage of this feature is to vendorize small license-compatible tools.

Source tests are stored in the root of the provider in a directory called
``src/``. Create the ``src/`` directory and inside create a new file called
``vfork_memory_share_test.c``. The objective of this test is going to be to
check if the `vfork <https://www.man7.org/linux/man-pages/man2/vfork.2.html>`_
syscall actually shares the memory between the parent and child process.

.. code:: C

    #include <unistd.h>
    #include <stdio.h>

    #define MAGIC_NUMBER 24

    static pid_t shared;

    int main(void){
      int pid = vfork();
      if(pid != 0){
        // we are in parent, we can't rely on us being suspended
        // so let's give the children process 1s to write to the shared variable
        // if we are not
        if(shared != MAGIC_NUMBER){
          printf("Parent wasn't suspended when spawning child, waiting\n");
          sleep(1);
        }
        if(shared != MAGIC_NUMBER){
          printf("Child failed to set the variable\n");
        }else{
          printf("Child set the variable, vfork shares the memory\n");
        }
        return shared != MAGIC_NUMBER;
      }
      // we are in children, we should now write to shared, parent will
      // discover this if vfork implementation uses mamory sharing as expected
      shared = MAGIC_NUMBER;
      _exit(0);
    }

To compile our source files, Checkbox relies on a Makefile that must be in the
``src/`` directory. Let's create it with all the basic rules we are going to
need:

.. code-block:: Makefile

    .PHONY:
    all: vfork_memory_share_test

    .PHONY: clean
    clean:
      rm -f vfork_memory_share_test

    vfork_memory_share_test: CFLAGS += -pedantic

    CFLAGS += -Wall

Now we can go back to the root of the provider and use ``manage.py`` to compile
our test file:

.. code:: none

    (checkbox_venv) > ./manage.py build
    cc -Wall -pedantic ../../src/vfork_memory_share_test.c -o vfork_memory_share_test
    # The following step is not necessary when you install a provider
    # but


Add a new test to our provider that calls our new binary by name like a script:

.. code-block:: none

    id: vfork_memory_share
    _summary: Check that vfork syscall shares the memory between parent and child
    flags: simple
    command:
      vfork_memory_share_test

Running it you should see the following:

.. code-block:: none

    (checkbox_venv) > checkbox-cli run com.canonical.certification::vfork_memory_share
    ===========================[ Running Selected Jobs ]============================
    =========[ Running job 1 / 1. Estimated time left (at least): 0:00:00 ]=========
    ----[ Check that vfork syscall shares the memory between parent and child ]-----
    ID: com.canonical.certification::vfork_memory_share
    Category: com.canonical.plainbox::uncategorised
    ... 8< -------------------------------------------------------------------------
    Child set the variable, vfork shares the memory
    ------------------------------------------------------------------------- >8 ---
    Outcome: job passed
    Finalizing session that hasn't been submitted anywhere: checkbox-run-2024-08-08T13.35.24
    ==================================[ Results ]===================================
     ☑ : Check that vfork syscall shares the memory between parent and child

.. warning::
   Checkbox is delivered for many platforms (x86, ARM, etc.) so be mindful of what you include
   in the ``src/`` directory, especially if you plan to contribute the test
   upstream. It must be compatible with all architectures we build for, Debian
   packages and snaps.

.. note::
   Before using a compilable tool see if you can obtain the same result/test
   using `Python's excellent module ctypes <https://docs.python.org/3/library/ctypes.html>`_.
   The above example is for example impossible to emulate via ctypes,
   completely cross-platform, compatible with any modern C standard compiler
   so it is a good candidate.
