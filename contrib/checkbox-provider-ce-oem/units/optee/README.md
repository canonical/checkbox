# Introduction to OP-TEE (Open Source - Trusted Execution Environment) Test Jobs

## id: ce-oem-optee/device-node
This job checks if the OP-TEE node (teepriv0 and tee0) has been probed.
It relies on the manifest "has_optee" to be true.

## id: ce-oem-optee/xtest-check
This job checks if xtest is in the gadget snap. Since xtest and TA (Trusted Application) rely on the same signing key as optee-os and optee-client, xtest is built into the gadget snap.
However, if you intend to use your own built optee-test, you can assign the checkbox config variable to make this job use a specific tool.
The checkbox config variable "OPTEE_TOOL" should be given the full application name, including SNAP name and APP name if it's a SNAP, otherwise, the APP name should be fine.
For example:
- SNAP named "optee-test" and APP name "xtest": `OPTEE_TOOL=optee-test.xtest`
- APP named "xtest": `OPTEE_TOOL=xtest`

## id: ce-oem-optee-test-list
This resource job generates a list of optee-test against optee-test.json (Please check the section about "Test cases for optee-test").
It includes "regression" and "benchmark" tests of optee-test.
The checkbox config variable "OPTEE_CASES" allows you to provide a path to optee-test.json if needed. Otherwise, it will use the default JSON file in the provider.
Please ensure that the file can be accessed by checkbox.
For example: `OPTEE_CASES=/home/user/optee-test.json`

## id: ce-oem-optee-test-list-pkcs11
This resource job generates a list of optee-test against optee-test.json (Please check the section about "Test cases for optee-test").
It includes the "pkcs11" test of optee-test.
The checkbox config variable "OPTEE_CASES" allows you to provide a path to optee-test.json if needed. Otherwise, it will use the default JSON file in the provider.
Please ensure that the file can be accessed by checkbox.
For example: `OPTEE_CASES=/home/user/optee-test.json`

## Test Coverage
We have covered the default tests of optee-test, which include:
- Benchmark
- Regression
- PKCS11

For the "Benchmark" and "Regression" tests, Trusted Applications (TA) need to be installed before the test.

For the "PKCS11" tests, there are no specific requirements.

## Test Cases for optee-test (optee-test.json)
We parse the source of xtest within optee-test and dump it into "optee-test.json." We have a [Python script](https://git.launchpad.net/~rickwu4444/+git/tools/tree/parse_optee_test_cases) to perform this task offline.
