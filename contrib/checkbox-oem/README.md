# Checkbox OEM Provider

This is a checkbox provider for both IoT and PC devices, built as a snap named
*checkbox-oem*. It can be used as a standalone test launcher or as a content
provider supplying test jobs and plans to another checkbox interface snap.

# Use as a launcher

## Ubuntu Classic

```
$ sudo snap install checkbox26
$ sudo snap install checkbox-oem --channel=26.04/stable --classic
```

## Ubuntu Core

```
$ sudo snap install checkbox26
$ sudo snap install checkbox-oem --channel=uc26/stable --devmode
```

The following connections should be established automatically:

```
$ sudo snap connect checkbox-oem:checkbox-runtime              checkbox26:checkbox-runtime
$ sudo snap connect checkbox-oem:provider-certification-client checkbox26:provider-certification-client
$ sudo snap connect checkbox-oem:provider-checkbox             checkbox26:provider-checkbox
$ sudo snap connect checkbox-oem:provider-resource             checkbox26:provider-resource
$ sudo snap connect checkbox-oem:provider-tpm2                 checkbox26:provider-tpm2
```

# Use together with checkbox-ce-oem

*checkbox-oem* can be combined with *checkbox-ce-oem* to run both sets of tests
from a single launcher. You should connect the required interfaces and only
have one agent running, as follows:

```
# Classic
$ sudo snap stop --disable checkbox-ce-oem.remote-slave

# Core
$ sudo snap connect checkbox-oem:provider-ce-oem   checkbox-ce-oem:provider-ce-oem
$ sudo snap stop --disable checkbox-oem.remote-slave
$ sudo snap stop --disable checkbox-ce-oem.remote-slave
$ sudo snap start --enable checkbox26.agent
```

# Use as a content provider

*checkbox-oem* exposes a `provider-oem` slot so that another checkbox interface
snap can connect to it and access its test jobs and plans.

```
$ sudo snap connect <checkbox-snap>:provider-oem checkbox-oem:provider-oem
```

