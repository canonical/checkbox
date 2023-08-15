# This is a file to introducing OP-TEE(Open Source - Trusted Execution Environment) test jobs.

## id: ce-oem-optee/device-node
  This job will check if OP-TEE node (teepriv0 and tee0) have been probed.
  And it relies on the manifest "has_optee" to be true.

## id: ce-oem-optee/xtest-check
  This job will check if xtest is in gadget snap. Since xtest and TA rely on the same signing key with optee-os and optee-client. Therefore, xtest will be build-in in gadget snap.
  
## Test coverage
  We have covered the default tests of optee-test, which include: 
  - Benchmark
  - Regression
  - PKCS11
  
  For the *Benchmark* and *Regression* tests, TA (Trusted Applications) need to be installed before the test

  For the *PKCS11* tests, there are no specific requirements.

## Test cases for optee-test (optee-test.json)
  We parse the source of xtest that in optee-test. And dump it into *optee-test.json*. And we have a [python script](https://git.launchpad.net/~rickwu4444/+git/tools/tree/parse_optee_test_cases) to do it offline. 