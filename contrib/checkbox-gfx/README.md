# Welcome to the Checkbox GFX project!

This repository contains the Checkbox GFX Provider (GFX-specific test cases and test plans for [Checkbox]) as well as everything that is required to build the [checkbox-gfx] snap in the snapstore.

# Checkbox GFX Provider

Located in the `checkbox-provider-gfx` directory, it contains:

- the test cases (also called "jobs" in the Checkbox jargon) and test plans to be run by Checkbox (in the `units` directory)

# Requirements

- Ubuntu Noble (24.04)
- Supported hardware platforms:
  - Intel platforms with recent GPU (>= Broadwell)

# Installation

Install the Checkbox runtime and build/install the gfx provider snaps:

```shell
sudo snap install --classic snapcraft
sudo snap install checkbox24
lxd init --auto
git clone https://github.com/canonical/checkbox-gfx
cd checkbox-gfx
snapcraft
sudo snap install --dangerous --classic ./checkbox-gfx_1.0_<arch>.snap
```

Make sure that the provider service is running and active:

```shell
systemctl status snap.checkbox-gfx.run-agent.service
```

# Install dependencies

Most tests need dependencies, and a helper script is available to install each category of tests:

```shell
checkbox-gfx.install-vulkan
checkbox-gfx.install-opengl
checkbox-gfx.install-opencl
```

# Automated Run

Each category of tests is run separately:

```shell
checkbox-gfx.test-opencl
checkbox-gfx.test-opengl
checkbox-gfx.test-opengl-short
checkbox-gfx.test-vulkan
```

Due to some tests causing dropped SSH connections, running the tests remotely should be done like this:

1. Install checkbox-gfx on both the remote machine and the local machine
2. From the checkbox-gfx directory, run the following command

```shell
checkbox-gfx.checkbox-cli control <REMOTE IP> bin/<test bin>
```

# Develop the Checkbox GFX provider

Since snaps are immutable, it is not possible to modify the content of the scripts or the test cases. Fortunately, Checkbox provides a functionality to side-load a provider on the DUT.

Therefore, if you want to edit a job definition, a script or a test plan, run the following commands on the DUT:

```shell
cd $HOME
git clone https://github.com/canonical/checkbox-gfx
mkdir /var/tmp/checkbox-providers
cp -r $HOME/checkbox-gfx/checkbox-provider-gfx /var/tmp/checkbox-providers/
```

You can then modify the content of the provider in `/var/tmp/checkbox-providers/checkbox-provider-gfx/`, and it's this version that will be used when you run the tests.

Please refer to the [Checkbox documentation] on side-loading providers for more information.

[Checkbox]: https://checkbox.readthedocs.io/
[Checkbox documentation]: https://checkbox.readthedocs.io/en/latest/side-loading.html
