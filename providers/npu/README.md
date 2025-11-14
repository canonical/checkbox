# Checkbox Provider - NPU

This provider includes tests for devices with an NPU. As of right now, it is intended only for Intel NPUs.  The tests only run as long as the manifest entry `has_npu` is set to `true`.

The `intel-npu-driver` snap is required to be installed to run the tests and the `NPU_UMD_TEST_CONFIG` environment variable needs to be set to the location of the `npu-umd-test` configuration file. Files referenced in the configuration file are expected to be located under the same directory as the configuration file.
