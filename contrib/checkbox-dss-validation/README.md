# Welcome to the Checkbox DSS project!

This repository contains the Checkbox DSS Provider (test cases and test plans for validating Intel and NVIDIA GPU support in the [Data Science Stack](https://documentation.ubuntu.com/data-science-stack/en/latest/)) as well as everything that is required to build the `checkbox-dss` snap.

# Requirements

- Ubuntu Jammy (22.04)
- Supported hardware platforms:
  - No GPUs
  - Intel platforms with recent GPU (>= Broadwell)
  - Recent NVIDIA GPU

# Installation

Install the Checkbox runtime and build/install the dss provider snaps:

```shell
sudo snap install --classic snapcraft
sudo snap install checkbox22
lxd init --auto
git clone https://github.com/canonical/checkbox
cd checkbox/contrib/checkbox-dss-validation
snapcraft
sudo snap install --dangerous --classic ./checkbox-dss_3.0_amd64.snap
```

Make sure that the provider service is running and active:

```shell
systemctl status snap.checkbox-dss.remote-slave.service
```

# Install dependencies

> [!NOTE]
> We are migrating to using `setup_include` from Checkbox.
> While it is not available, installing dependencies is currently done in a separate test plan.

DSS 1.0/stable works on Microk8s, whereas DSS 1.1/stable onwards
DSS will work on Canonical K8s.
There are accordingly the following launchers available:

- `launchers/setup-microk8s.conf`
- `launchers/setup-canonical-k8s.conf`

Run Checkbox CLI with the Microk8s setup launcher as below
substituting the appropriate launcher to setup Canonical K8s:

```shell
checkbox-dss.checkbox-cli control 127.0.0.1 launchers/setup-microk8s.conf
```

By default, the Microk8s setup will attempt to install the following:

- `microk8s` snap from channel `1.28/stable` in `--classic` mode
- `data-science-stack` snap from channel `1.0/stable`
- `kubectl` snap from `1.29/stable`
- `intel-gpu-tools` package
- Setup the NVIDIA GPU Operator `v24.6.2` in `microk8s`
  - Only if there's a manifest entry with `com.canonical.contrib::has_nvidia_gpus = true`
- Setup the Intel GPU Plugin `v0.30.0` in `microk8s`
  - Only if there's a manifest entry with `com.canonical.contrib::has_intel_gpus = true`

The difference in the Canonical K8s launcher will be:

- Instead of `microk8s`, `k8s` snap from channel `1.32-classic/stable` in `--classic` mode.
- `data-science-stack` snap from channel `1.1/stable`

Please edit the environment section in the appropriate setup launcher to customize the versions.
You can add a `[manifest]` section too with the appropriate entries to setup appropriate GPUs.

# Automated Run

Use the launcher [`launchers/checkbox-dss.conf`](./launchers/checkbox-dss.conf)
to run the test plan:

```shell
checkbox-dss.checkbox-cli control 127.0.0.1 launchers/checkbox-dss.conf
```

# Cleanup

WARNING: The following steps will remove kubectl and microk8s from your machine. If you wish to keep them, do not run.

To clean up and uninstall all installed tests, run:

```shell
checkbox-dss.remove-deps
```

This will also remove the `data-science-stack` snap as well as any notebook servers
that are managed by `dss`.

# Develop the Checkbox DSS provider

Since snaps are immutable, it is not possible to modify the content of the scripts or the test cases. Fortunately, Checkbox provides a functionality to side-load a provider on the DUT.

Therefore, if you want to edit a job definition, a script or a test plan, run the following commands on the DUT:

```shell
cd $HOME
git clone https://github.com/canonical/checkbox
mkdir /var/tmp/checkbox-providers
cp -r $HOME/checkbox/contrib/checkbox-dss-validation/checkbox-provider-dss /var/tmp/checkbox-providers/
```

You can then modify the content of the provider in `/var/tmp/checkbox-providers/checkbox-provider-dss/`, and it's this version that will be used when you run the tests.

Please refer to the [Checkbox documentation] on side-loading providers for more information.

## Runninig the tests

The jobs in the provider are implemented as Python scripts, located in `checkbox-provider-dss/bin`, and their tests are in `checkbox-provider-dss/tests`. The Tox file at `checkbox-provider-dss/tox.ini` can be used to run the tests from that directory.

Please note that only Python 3.10 is currently tested, and will be the minimum supported version for the foreseeable future.

Running the tests locally may require some additional packages. Here's what a run from clean slate may look like:

```console
$ sudo apt install python3-dev python3-venv shellcheck pkg-config gcc
$ cd checkbox/contrib/checkbox-dss-validation/checkbox-provider-dss
$ python3 -m venv .venv
$ . .venv/bin/activate
$ pip install tox
$ tox
```

[Checkbox]: https://checkbox.readthedocs.io/
[Checkbox documentation]: https://checkbox.readthedocs.io/en/latest/side-loading.html
