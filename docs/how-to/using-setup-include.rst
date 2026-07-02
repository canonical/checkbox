Using ``setup_include``
^^^^^^^^^^^^^^^^^^^^^^^

Use ``setup_include`` when a test plan needs to prepare the device under test
before Checkbox starts the normal bootstrapping phase. This is useful to pull in
heavy dependencies or prepare the system to bootstrap correctly (e.g., installing
drivers).

The execution sequence of a test plan that uses ``setup_include`` is

  setup  →  bootstrap  →  testing phase

Creating a setup job
--------------------

Define the preparation as a ``setup job`` unit. For example, this setup job
installs a snap that later graphics tests will use:

.. code-block:: yaml

    unit: setup job
    id: setup/install_example_tool
    summary: Install the example-tool snap
    plugin: shell
    user: root
    command: |
      if snap list example-tool >/dev/null 2>&1; then
        snap refresh example-tool
      else
        snap install example-tool
      fi
    estimated_duration: 1m

Including it in a test plan
---------------------------

List the setup job in the test plan's ``setup_include`` section, then include
the regular jobs that depend on the prepared system state:

.. code-block:: yaml

    unit: test plan
    id: example-tool-tests
    name: Example tool tests
    setup_include:
      - setup/install_example_tool
    bootstrap_include:
      - example-tool/detect_devices
    include:
      - example-tool/run_conformance

With this structure, Checkbox installs ``example-tool`` first. It then runs the
bootstrap job that discovers devices or generates tests, and finally runs the
main test selection.

Using manifest values
---------------------

Use ``requires_manifest`` when a setup job should only run for specific manifest
values. List a manifest entry directly when the required value is ``true``:

.. code-block:: yaml

    unit: setup job
    id: setup/install_touchscreen_tool
    summary: Install touchscreen test dependencies
    plugin: shell
    user: root
    requires_manifest:
      - has_touchscreen
      - has_touchscreen_special_pen
    command: snap install touchscreen-tool-pen

Use an explicit key/value mapping when the setup job requires a manifest value to
be ``false``:

.. code-block:: yaml

    unit: setup job
    id: setup/install_non_touchscreen_tool
    summary: Install non-touchscreen test dependencies
    plugin: shell
    user: root
    requires_manifest:
      - has_touchscreen: false
    command: snap install non-touchscreen-tool

When to use a setup job
-----------------------

Use a setup job when all of these are true:

* The action must happen before bootstrapping.
* The action prepares the machine.
* Failure should prevent the test plan from continuing normally.

Common examples include installing additional test suites, loading required
kernel modules or starting services. For fields and validation rules,
see :ref:`setup-job`.
