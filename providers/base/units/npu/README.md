# NPU tests

This folder contains tests for devices with an NPU. As of right now, it is
intended only for Intel NPUs. The tests only run as long as the manifest entry
`has_npu` is set to `true`. The tests use the `npu-umd-test` utility from the
`intel-npu-driver` snap.

## Requirements for using the NPU

 - `intel-npu-driver` snap is installed
 - non-privileged user is in the `render` group

_These requirements are assumed to be satisfied when the tests are run since
this is necessary setup for usage of the Intel NPU._

## Configuration
The `NPU_UMD_TEST_CONFIG` environment variable can optionally be set to the
location of the `npu-umd-test` configuration file. Files referenced in the
configuration file are expected to be located under the same directory as the
configuration file. A default configuration file and model files are now
bundled with the `intel-npu-driver` snap and usable by passing
`--config=basic.yaml` to the utility (this is done by default in these checkbox
tests when the `NPU_UMD_TEST_CONFIG` variable is not defined)

## Known failures
Some tests are confirmed by Intel as known failures. One can get a list of them
by running the following command:

```bash
intel-npu-driver.known-failures
```

Known failures are not included in the default test plan but can be explicitly
included, the test ids are prefixed with `known-failures/`.
