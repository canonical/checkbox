# Checkbox release process

> **_NOTE:_** Check the [Launchpad Builders status] before triggering a release.
Sometimes, the builders will be down and this might prevent building the
packages.

## Promote the previous beta release to stable

Internal teams (mostly QA and Certification) are using the version in the beta
snap channels or the Testing PPA to complete their tests. If this version is
validated, it can then be pushed to stable for other teams and external
stakeholders.

Therefore, if there has been no negative feedback from internal teams after a
cycle of testing the beta release, run the [Stable release workflow] to copy deb
packages to the stable PPA and promote all snaps to stable.

Then, it's time to build the new beta version.

## Tag the release

- Clone the repository
  ```
  git clone git@github.com:canonical/checkbox.git
  ```
- Tag the release
  ```
  git tag -s "v2.4" -m "Bump version: 2.3 → 2.4"
  ```
- Push the tag to origin
  ```
  git push --tags
  ```
  > **_NOTE:_** Having to clone and not push the tag from an existing
  workflow is actually a Github Action limitation[^1]:
  > *if a workflow run pushes code using the repository's GITHUB_TOKEN, a new
  workflow will not run even when the repository contains a workflow configured
  to run when push events occur.*

## How packages versions are generated? ##

Both Debian packages and checkbox snaps rely on [setuptools_scm] to extract 
package versions from git metadata.

```
>>> from setuptools_scm import get_version
>>> get_version()
'2.9.dev38+g896ae8978
```

## Monitor the build and publish workflows

3 workflows are triggered on tag push events:

- [checkbox deb packages] *(built and published to the testing PPA)*
- [checkbox snap packages] *(built and uploaded to their respective beta
  channels)*
- [checkbox core snap packages] *(built and uploaded to their respective beta
  channels)*

In addition to the above workflows, a draft release is created on Github with
an auto-generated changelog.

Check the related Github Action logs to see if everything runs as expected:

- Snapcraft is not blocked during the snap build process. For example, in this
[build], the i386 build was blocked on an error (`Chroot problem`) for hours
before finally completing
- the expected number of snaps are built. Snapcraft does not return 1 when only
a few of the snaps are built, which leads to Github Actions being marked as
successful even though some snaps are not built (and therefore not pushed to
the store)

# References

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
* [providers/gpgpu](https://github.com/canonical/checkbox/tree/main/providers/gpgpu)

[^1]:https://docs.github.com/en/actions/security-guides/automatic-token-authentication#using-the-github_token-in-a-workflow

[setuptools_scm]: https://github.com/pypa/setuptools_scm/
[Stable release workflow]: https://github.com/canonical/checkbox/actions/workflows/checkbox-stable-release.yml
[Bumpversion]: https://github.com/c4urself/bump2version
[Stable]: https://launchpad.net/~hardware-certification/+archive/ubuntu/public
[Testing]: https://code.launchpad.net/~checkbox-dev/+archive/ubuntu/testing
[Development]: https://code.launchpad.net/~checkbox-dev/+archive/ubuntu/ppa
[Launchpad Builders status]: https://launchpad.net/builders
[checkbox deb packages]: https://github.com/canonical/checkbox/actions/workflows/deb-beta-release.yml
[checkbox snap packages]: https://github.com/canonical/checkbox/actions/workflows/checkbox-snap-beta-release.yml
[checkbox core snap packages]: https://github.com/canonical/checkbox/actions/workflows/checkbox-core-snap-beta-release.yml
[build]: https://github.com/canonical/checkbox/actions/runs/4371649401/jobs/7649877336
