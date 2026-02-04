# Checkbox OEM Provider

This is a checkbox provider for both IoT and PC devices, built as a snap named *checkbox-oem*.

# Quick Start

The snap uses the [custom-frontend](https://canonical-checkbox.readthedocs-hosted.com/latest/tutorial/custom_frontend/)
interface, so you need to connect it to the checkbox runtime.

## Running a test locally

```
# Setup
$ snap install --devmode checkbox24
$ snap install --edge checkbox-oem
$ sudo snap connect checkbox24:custom-frontend checkbox-oem
$ sudo snap connect checkbox24:hardware-observe
# Running test from provider
$ checkbox24.checkbox run com.canonical.contrib::kernel/check-kernel
```

## Running a remote test

```
### DUT
# Setup
$ snap install --devmode checkbox24
$ snap install --edge checkbox-oem
$ sudo snap connect checkbox24:custom-frontend checkbox-oem
$ sudo snap connect checkbox24:hardware-observe
# Starting agent
$ snap start checkbox24.agent

### Host
# Setup
$ snap install --devmode checkbox24
$ snap install --edge checkbox-oem
$ sudo snap connect checkbox24:custom-frontend checkbox-oem
$ sudo snap connect checkbox24:hardware-observe
# Running a test
$ checkbox24.checkbox control <DUT IP ADDRESS>
```

# Building the snap

To build the snap, you need to create a `snapcraft.yaml` file, which can be done using the `Makefile` with the desired `SNAPBASE`. For example:

```
$ make SNAPBASE=core24
$ cd build
$ snapcraft pack
```
