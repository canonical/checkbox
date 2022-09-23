# edgex-checkbox-provider

This project contains the [Checkbox](https://checkbox.readthedocs.io/en/latest/) tests of the [Edgex Foundry](https://docs.edgexfoundry.org/) snaps.

The upstream repository is hosted on Github: https://github.com/canonical/edgex-checkbox-provider

A mirror is available on Launchpad: https://code.launchpad.net/checkbox-provider-edgex  
The mirror and upstream are synced automatically every 5 hours. The import may be triggered manually.

When a snap is released to a `$TRACK/beta` channel, the corresponding checkbox tests are triggered on [Ubuntu certified hardware](https://ubuntu.com/certified). The tests reference the mirror that is available on Launchpad.

## Usage
### Run tests using checkbox-edgexfoundry snap
This is the recommended method as it runs all the tests in isolation.

This snap is built on
[launchpad](https://launchpad.net/~ce-certification-qa/+snap/checkbox-edgexfoundry-edge)
from the mirror (see above) and published as
[checkbox-edgexfoundry](https://snapcraft.io/checkbox-edgexfoundry).

The checkbox-edgexfoundry snap should be installed in [developer mode](https://snapcraft.io/docs/install-modes#heading--developer) to have full access. 

To install:
```bash
sudo snap install checkbox-edgexfoundry --devmode --edge
```

Set `DEFAULT_TEST_CHANNEL` to snap channel, and CLI name to the EdgeX release name:
```bash
sudo DEFAULT_TEST_CHANNEL="<channel>" checkbox-edgexfoundry.<release name>
```

For example:
```bash
sudo DEFAULT_TEST_CHANNEL="2.1/beta" checkbox-edgexfoundry.jakarta
```

#### Modify snapped tests
The checkbox-edgexfoundry snap packages all the test files inside during the build.
To modify those test files without rebuilding the snap, 
get the checkbox-edgexfoundry snap and unsquash it:

```
snap download checkbox-edgexfoundry --edge
unsquashfs checkbox-edgexfoundry_99.snap 
```

Update the test you are working on in `./squashfs-root/providers/checkbox-provider-edgex/data/`.

Optionally, to save time, modify jakarta.pxu to remove all tests other than the one you are testing.

Once done, run the tests with:

```
mksquashfs ./squashfs-root checkbox-edgexfoundry.snap  -noappend -comp xz -all-root -no-xattrs -no-fragments
sudo snap install ./checkbox-edgexfoundry.snap --devmode
snap connect checkbox-edgexfoundry:checkbox-runtime checkbox16:checkbox-runtime
sudo DEFAULT_TEST_CHANNEL="2.1/beta" checkbox-edgexfoundry.jakarta
```

### Run tests using checkbox CLI
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

### Run test scripts directly
Enter the desired test directory, then get a list of available options:

```bash
sudo ./run-all-tests-locally.sh -h
```
For example, to run a single test with a local snap:

```bash
sudo ./run-all-tests-locally.sh -s edgexfoundry.snap -t test-rules-engine.sh
```

To run tests against a snap from a specific channel:
```bash
sudo DEFAULT_TEST_CHANNEL="<channel>" ./run-all-tests-locally.sh
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
- Test that snap configure hook settings are supported by the edgexfoundry snap
- Test that edgex-device-virtual creates devices and produces readings
- Mandatory tests: see [units/test-plan.pxu#L113](./units/test-plan.pxu#L113)

## Limitations
- The current tests plan only covers the [edgexfoundry](https://snapcraft.io/edgexfoundry) snap. It does not cover any of the device or app service snaps.
- edgex-secretstore-token content interface is not be covered by tests.
