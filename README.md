Welcome to the Checkbox project source code repository!

# What is Checkbox?

[Checkbox] is a flexible test automation software. It’s the main tool used in the [Ubuntu Certification program].

You can use Checkbox without any modification to check if your system is behaving correctly or you can develop your own set of tests to check your needs.

Checkbox optionally generates test reports in different formats (HTML, JSON, text) that can be used to easily share the results of a test session.

For more information, check the [official documentation].

![Test report exported in HTML](docs/_images/checkbox-test-report.png)

![Test selection screen in Checkbox](docs/_images/checkbox-snappy-3-select-jobs.png)

# Getting started

To get started, setup a test environment, run Checkbox and its providers, run the associated tests and share your contributions with everyone, please check the [contributing guide].


# Content of the source code repository

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
    ├── gpgpu
    ├── iiotg
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
[official documentation]: https://checkbox.readthedocs.io/en/latest/
[contributing guide]: CONTRIBUTING.md
[providers]: https://checkbox.readthedocs.io/en/latest/understanding.html#provider
[Ubuntu Certification program]: https://ubuntu.com/certified
[^1]: formerly known as "Checkbox provider" or `plainbox-provider-checkbox`
[^2]: due to Checkbox flexibility, other providers can be used and might be hosted elsewhere (e.g. providers specific to private projects).
