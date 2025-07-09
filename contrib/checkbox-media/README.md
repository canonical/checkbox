# Welcome to the Checkbox Media project!

This repository contains the Checkbox Media Provider (Media-specific test cases and test plans for [Checkbox]) as well as everything that is required to build the [checkbox-media] snap in the snapstore.

# Checkbox Media Provider

Located in the `checkbox-provider-media` directory, it contains:

- the test cases (also called "jobs" in the Checkbox jargon) and test plans to be run by Checkbox (in the `units` directory)

# Requirements

- Ubuntu Noble (24.04)
- Supported hardware platforms:
  - Intel platforms with recent GPU (>= Broadwell)

# Installation

Install the Checkbox runtime and build/install the media provider snaps:

```shell
sudo snap install --classic snapcraft
sudo snap install checkbox24
lxd init --auto
git clone https://github.com/canonical/checkbox-media
cd checkbox-media
snapcraft
sudo snap install --dangerous --classic ./checkbox-media_1.0_amd64.snap
```

Make sure that the provider service is running and active:

```shell
systemctl status snap.checkbox-media.remote-slave.service
```

# Install dependencies

Some test need dependencies, so in order to run all tests, you might way to install those dependencies.
A helper script is available to install them:

```shell
checkbox-media.install-ffmpeg
```

# Automated Run

To run the full test plan:

```shell
checkbox-media.test-ffmpeg
```
# Develop the Checkbox Media provider

Since snaps are immutable, it is not possible to modify the content of the scripts or the test cases. Fortunately, Checkbox provides a functionality to side-load a provider on the DUT.

Therefore, if you want to edit a job definition, a script or a test plan, run the following commands on the DUT:

```shell
cd $HOME
git clone https://github.com/canonical/checkbox-media
mkdir /var/tmp/checkbox-providers
cp -r $HOME/checkbox-media/checkbox-provider-media /var/tmp/checkbox-providers/
```

You can then modify the content of the provider in `/var/tmp/checkbox-providers/checkbox-provider-media/`, and it's this version that will be used when you run the tests.

Please refer to the [Checkbox documentation] on side-loading providers for more information.

[Checkbox]: https://checkbox.readthedocs.io/
[Checkbox documentation]: https://checkbox.readthedocs.io/en/latest/side-loading.html
