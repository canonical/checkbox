# edgex-checkbox-provider


This project contains the checkbox tests of the [Edgex Foundry](https://docs.edgexfoundry.org/) snaps.
[Checkbox](https://checkbox.readthedocs.io/en/latest/) is a test automation software performed by the Canonical certification team. 
The [upstream repository](https://github.com/canonical/edgex-checkbox-provider) is hosted on Github; 
The tests run via the [Launchpad mirror](https://code.launchpad.net/checkbox-provider-edgex).

When edgexfoundry snap is released to a `$TRACK/beta` channel, the corresponding checkbox test will be triggered. 

## Usage
- ### Run tests using checkbox-edgexfoundry snap
    This is the recommended method as it runs all the tests in isolation.

    This snap is published in the snap store at https://snapcraft.io/checkbox-edgexfoundry, 
and built by launchpad at https://launchpad.net/~ce-certification-qa/+snap/checkbox-edgexfoundry-edge.

    The checkbox-edgexfoundry snap should be installed in [developer mode](https://snapcraft.io/docs/install-modes#heading--developer) to have full access. 
    Here is an example:
    ```bash
    sudo snap install checkbox-edgexfoundry --devmode --channel=latest/edge
    ```
    checkbox-edgexfoundry snap depends on extra environment variables, so setting test channel and release name:
    ```bash
    sudo DEFAULT_TEST_CHANNEL=<"channel"> checkbox-edgexfoundry.<release name>
    ```
    Here is an example:
    ```bash
    sudo DEFAULT_TEST_CHANNEL="2.1/beta" checkbox-edgexfoundry.jakarta

    ```
- ### Run tests using checkbox CLI
  ```bash
  cd edgex-checkbox-provider/
  sudo ./manage.py install
  checkbox-cli
  ```
  Scroll down and press SPACE to select the desired test plan:
  ```
   Select test plan
  ┌─────────────────────────────────────────────────┐
  │    ( ) Dock Hot Plug tests                      │
  │    ( ) EdgeX Fuji                               │
  │    ( ) EdgeX Geneva                             │
  │    ( ) EdgeX Hanoi                              │
  │    (X) EdgeX Ireland                            │
  │    ( ) EdgeX Jakarta                            │
  │    ( ) Firewire tests                           │
  └─────────────────────────────────────────────────┘
   Press <Enter> to continue                (H) Help
  ```

- ### Run test scripts directly

  Enter the desired test directory, then get a list of available options:

  ```bash
  sudo ./run-all-tests-locally.sh -h
  ```
  For example, to run a single test with a local snap:

  ```bash
  sudo ./run-all-tests-locally.sh -s edgexfoundry.snap -t test-rules-engine.sh
  ```

## Testing coverage
- Test the installation of edgexfoundry snap
- Test security services proxy certs work properly
- Test that all services can be started properly
- Test that config paths don't include previous snap revision after installation
- Test that config paths don't include previous snap revision after refresh
- Test that services start after refreshing
- Test that services start after refreshing to the same revision
- Test that the system management agent works with the snap
- Test that services are not listening on external network interfaces
- Test that the rules engine works with the snap
- Mandatory tests: see [units/test-plan.pxu#L113](./units/test-plan.pxu#L113)

## Limitations
- The current tests plan only covers the [edgexfoundry](https://snapcraft.io/edgexfoundry) snap. It does not cover any of the device or app service snaps.
- edgex-secretstore-token content interface is not be covered by tests.

