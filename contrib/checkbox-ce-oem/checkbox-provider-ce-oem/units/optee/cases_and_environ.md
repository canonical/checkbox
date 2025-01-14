
## <a id='top'>environ keys for optee tests</a>

- OPTEE_CASES
    - Affected Test Cases:
        - [ce-oem-optee-test-list](#ce-oem-optee-test-list)
        - [ce-oem-optee-test-list-pkcs11](#ce-oem-optee-test-list-pkcs11)

## Detailed test cases contains environ variable
### <a id='ce-oem-optee-test-list'>ce-oem-optee-test-list</a>
- **summary:**
Collect the test cases support by OP-TEE test(xtest)

- **description:**
```
None
```

- **file:**
[source file](jobs.pxu#L68)

- **environ:**
OPTEE_CASES

- **command:**
```
filepath=""
if [[ -n "$OPTEE_CASES" ]]; then
    filepath="$OPTEE_CASES"
else
    filepath="$PLAINBOX_PROVIDER_DATA/optee-test.json"
fi
parse_optee_test.py "$filepath"
```
[Back to top](#top)

### <a id='ce-oem-optee-test-list-pkcs11'>ce-oem-optee-test-list-pkcs11</a>
- **summary:**
Collect the test cases related with PKCS11 support by OP-TEE test(xtest)

- **description:**
```
None
```

- **file:**
[source file](jobs.pxu#L83)

- **environ:**
OPTEE_CASES

- **command:**
```
filepath=""
if [[ -n "$OPTEE_CASES" ]]; then
    filepath="$OPTEE_CASES"
else
    filepath="$PLAINBOX_PROVIDER_DATA/optee-test.json"
fi
parse_optee_test.py "$filepath" -p
```
[Back to top](#top)
