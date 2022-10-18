Welcome to the Checkbox project source code repository!

[Checkbox] is composed of many different parts. Each of them are stored in a different directory:

```
.
├── checkbox-core-snap
├── checkbox-ng
├── checkbox-snap
├── checkbox-support
├── metabox
└── providers
    ├── base
    ├── certification-client
    ├── certification-server
    ├── docker
    ├── edgex
    ├── gpgpu
    ├── iiotg
    ├── ipdt
    ├── phoronix
    ├── resource
    ├── sru
    └── tpm2
```

Here is a brief explanation about each part:

- `checkbox-ng`: the core application
- `checkbox-support`: Python scripts and helper modules (for instance information parsers for different Linux utilities) used by Checkbox and its providers
- `providers`: the main [providers] (`base`[^1], `resource`) along with other public providers[^2]
- `checkbox-core-snap`: snapcraft recipe to build the Checkbox core snap which contains the Checkbox runtime and the public providers (i.e. the `checkbox[16|18|20|22]` snaps in the Snap store)
- `checkbox-snap`: snapcraft recipe to build the Checkbox test runner (i.e. the `checkbox` snap in the Snap store)
- `metabox`: application to help test and validate Checkbox in different configurations using Linux containers or virtual machines

[Checkbox]: https://checkbox.readthedocs.io/en/latest/
[providers]: https://checkbox.readthedocs.io/en/latest/understanding.html#provider
[^1]: formerly known as "Checkbox provider" or `plainbox-provider-checkbox`
[^2]: due to Checkbox flexibility, other providers can be used and might be hosted elsewhere (e.g. providers specific to private projects).