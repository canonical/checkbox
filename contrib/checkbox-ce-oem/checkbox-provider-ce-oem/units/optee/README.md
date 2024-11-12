# Introduction to OP-TEE (Open Source - Trusted Execution Environment) Test Jobs

## id: ce-oem-optee/device-node
This job checks if the OP-TEE node (teepriv0 and tee0) has been probed.
It relies on the manifest "has_optee" to be true.

## id: ce-oem-optee/ta-install
This job is to install TA for the x-test.
The checkbox configuration variable "XTEST" should be set to the SNAP name if your system has more than one SNAP that includes the xtest app. In some cases,
the system may have xtest in the gadget, and the user may need an additional x-test SNAP for debugging purposes.
For example:
- SNAP named "optee-test": `XTEST=optee-test`

## id: ce-oem-optee-test-list
This resource job generates a list of optee-test against optee-test.json (Please check the section about "Test cases for optee-test").
It includes "regression" and "benchmark" tests of optee-test.
The checkbox config variable "OPTEE_CASES" allows you to provide a path to optee-test.json if needed. Otherwise, it will use the default JSON file(optee version 3.19) in the provider.
Please ensure that the file can be accessed by checkbox.
You can assign variable "XTEST" if your system has more than one SNAP that includes the xtest app.
For example:
- `OPTEE_CASES=/home/user/optee-test.json`
- SNAP named "optee-test": `XTEST=optee-test`

## id: ce-oem-optee-test-list-pkcs11
This resource job generates a list of optee-test against optee-test.json (Please check the section about "Test cases for optee-test").
It includes the "pkcs11" test of optee-test.
The checkbox config variable "OPTEE_CASES" allows you to provide a path to optee-test.json if needed. Otherwise, it will use the default JSON file(optee version 3.19) in the provider.
Please ensure that the file can be accessed by checkbox.
You can assign variable "XTEST" if your system has more than one SNAP that includes the xtest app.
For example:
- `OPTEE_CASES=/home/user/optee-test.json`
- SNAP named "optee-test": `XTEST=optee-test`

## Test Coverage
We have covered the default tests of optee-test, which include:
- Benchmark
- Regression
- PKCS11

For the "Benchmark" and "Regression" tests, Trusted Applications (TA) need to be installed before the test.

For the "PKCS11" tests, there are no specific requirements.

## Test Cases for optee-test (optee-test.json)
We parse the source of xtest within optee-test and dump it into "optee-test.json." We have a [Python script](https://git.launchpad.net/~rickwu4444/+git/tools/tree/parse_optee_test_cases) to perform this task offline.
