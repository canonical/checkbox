# Checkbox OEM Provider

This is a checkbox provider for both IoT and PC devices, built as a snap named
*checkbox-oem*. It can be used as a standalone test launcher or as a content
provider supplying test jobs and plans to another checkbox interface snap.

# Use as a launcher

## Ubuntu Classic

```
$ sudo snap install checkbox24
$ sudo snap install checkbox-oem --channel=24.04/stable --classic
```

## Ubuntu Core

```
$ sudo snap install checkbox24
$ sudo snap install checkbox-oem --channel=uc24/stable --devmode
$ sudo snap connect checkbox-oem:checkbox-runtime              checkbox24:checkbox-runtime
$ sudo snap connect checkbox-oem:provider-certification-client checkbox24:provider-certification-client
$ sudo snap connect checkbox-oem:provider-checkbox             checkbox24:provider-checkbox
$ sudo snap connect checkbox-oem:provider-resource             checkbox24:provider-resource
$ sudo snap connect checkbox-oem:provider-tpm2                 checkbox24:provider-tpm2
```

# Use together with checkbox-ce-oem

*checkbox-oem* can be combined with *checkbox-ce-oem* to run both sets of tests
from a single launcher. Connect the required interfaces as follows:

```
$ sudo snap connect checkbox-oem:checkbox-runtime  checkbox24:checkbox-runtime
$ sudo snap connect checkbox-oem:provider-ce-oem   checkbox-ce-oem:provider-ce-oem
```

# Use as a content provider

*checkbox-oem* exposes a `provider-oem` slot so that another checkbox interface
snap can connect to it and access its test jobs and plans.

```
$ sudo snap connect <checkbox-snap>:provider-oem checkbox-oem:provider-oem
```

