# Checkbox release process (Debian packages)

## PPA/Repositories

* [Stable]\: The official release of Checkbox
* [Testing]\: Release candidates of Checkbox before it becomes the official
release
* [Development]\: Daily builds (that may contain experimental features)

## Projects released as Debian packages

* [checkbox-ng](https://github.com/canonical/checkbox/tree/main/checkbox-ng)
* [checkbox-support](https://github.com/canonical/checkbox/tree/main/checkbox-support)
* [providers/base](https://github.com/canonical/checkbox/tree/main/providers/base)
* [providers/resource](https://github.com/canonical/checkbox/tree/main/providers/resource)
* [providers/certification-client](https://github.com/canonical/checkbox/tree/main/providers/certification-client)
* [providers/certification-server](https://github.com/canonical/checkbox/tree/main/providers/certification-server)
* [providers/sru](https://github.com/canonical/checkbox/tree/main/providers/sru)
* [providers/tpm2](https://github.com/canonical/checkbox/tree/main/providers/tpm2)
* [providers/ipdt](https://github.com/canonical/checkbox/tree/main/providers/ipdt)
* [providers/phoronix](https://github.com/canonical/checkbox/tree/main/providers/phoronix)
* [providers/gpgpu](https://github.com/canonical/checkbox/tree/main/providers/gpgpu)

## Release steps summary

Steps | Release candidate(s) (RC) | Stable release | Dry mode
:--- | :---: | :---: | :---:
Parse each project and check for new commits | :heavy_check_mark: | :heavy_check_mark: | :heavy_check_mark:
Bump and tag versions | :heavy_check_mark: | :heavy_check_mark: | :heavy_check_mark:
Create release changelog (since the latest stable tag) | :heavy_check_mark: | :heavy_check_mark: | :heavy_check_mark:
Push release tags to Github | :heavy_check_mark: | :heavy_check_mark: | :x:[^1]
Update the PPA recipes and kick-off the builds | :heavy_check_mark: | :heavy_check_mark: | :x:
Open a new release for development | :x: | :heavy_check_mark: | :x:
Create a pull request including the new [SemVer](https://semver.org/spec/v2.0.0.html) | :x: | :heavy_check_mark: | :x:

## How to trigger the GitHub Actions release workflow

All the release steps above are fully automated but initiating a release is a
manual process requiring some user input.

The same workflow support two types of release, **testing** and **stable**.
Additionally, the release manager can perform a **dry run** to:
* Identify which projects are going to be released 
* Review the release changelog

Since `workflow_dispatch` only supports a maximum of 10 user inputs[^2], all
config options are grouped into a single JSON parameter. For all the release
scenarios below, just copy-paste the JSON snippet into the workflow input field
(pre-filled with `{}`).

```
╭-----------------------------------^----╮
|  Use workflow from                     |
|  ╭----------------╮                    |
|  | Branch: main v |                    |
|  ╰----------------╯                    |
|                                        |
|  JSON of options *                     |
|  ╭--------------------------------╮    |
|  | {}                             |    |
|  ╰--------------------------------╯    |
|                                        |
|  ╭--------------╮                      |
|  | Run workflow |                      |
|  ╰--------------╯                      |
╰----------------------------------------╯
```

### Triggering the first release candidate

Before applying RC tags, it's recommended to first perform a **dry run** of the **testing** mode and select all the projects:

```
{
    "mode": "testing",
    "dry_run": true,
    "checkbox-ng": true,
    "checkbox-support": true,
    "provider-base": true,
    "provider-resource": true,
    "provider-tpm2": true,
    "provider-sru": true,
    "provider-certification-server": true,
    "provider-certification-client": true,
    "provider-gpgpu": true,
    "provider-ipdt": true,
    "provider-phoronix": true
}
```

After reviewing the changelog, **dry run** can be set to false:

```
{
    "mode": "testing",
    "dry_run": false,
    "checkbox-ng": true,
    "checkbox-support": true,
    "provider-base": true,
    "provider-resource": true,
    "provider-tpm2": true,
    "provider-sru": true,
    "provider-certification-server": true,
    "provider-certification-client": true,
    "provider-gpgpu": true,
    "provider-ipdt": true,
    "provider-phoronix": true
}
```

### Requesting another release candidate for a subset of projects

If the validation of the release candidates identifies issues or regressions,
running the workflow again will create new RC tags (project-vX.Y.Zrc**N+1**).

In the example below, new RC are required for `checkbox-support` and the `base`
provider:

```
{
    "mode": "testing",
    "dry_run": false,
    "checkbox-support": true,
    "provider-base": true
}
```

The same workflow can run using the JSON config below of course:

```
{
    "mode": "testing",
    "dry_run": false,
    "checkbox-ng": false,
    "checkbox-support": true,
    "provider-base": true,
    "provider-resource": false,
    "provider-tpm2": false,
    "provider-sru": false,
    "provider-certification-server": false,
    "provider-certification-client": false,
    "provider-gpgpu": false,
    "provider-ipdt": false,
    "provider-phoronix": false
}
```

### Triggering a stable release

Stable releases **MUST** follow release candidates, it's not possible to jump
from a stable tag to an other stable tag. The next JSON config will apply the
stable release tag to the same commit the latest RC tag was applied to.

```
{
    "mode": "stable",
    "dry_run": false,
    "checkbox-ng": true,
    "checkbox-support": true,
    "provider-base": true,
    "provider-resource": true,
    "provider-tpm2": true,
    "provider-sru": true,
    "provider-certification-server": true,
    "provider-certification-client": true,
    "provider-gpgpu": true,
    "provider-ipdt": true,
    "provider-phoronix": true
}
```

[^1]:Actually a `git push --dry-run` is executed
[^2]:https://github.com/community/community/discussions/8774

[Stable]: https://launchpad.net/~hardware-certification/+archive/ubuntu/public
[Testing]: https://code.launchpad.net/~checkbox-dev/+archive/ubuntu/testing
[Development]: https://code.launchpad.net/~checkbox-dev/+archive/ubuntu/ppa
[Launchpad Builders status]: https://launchpad.net/builders

