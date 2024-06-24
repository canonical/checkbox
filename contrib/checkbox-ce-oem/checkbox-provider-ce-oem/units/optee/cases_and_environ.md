
## <a id='top'>environ keys for optee test</a>
- OPTEE_CASES
	- Affected Test Cases:
		- [ce-oem-optee-test-list](#ce-oem-optee-test-list)
		- [ce-oem-optee-test-list-pkcs11](#ce-oem-optee-test-list-pkcs11)

## Detailed test cases
### <a id='ce-oem-optee/device-node'>ce-oem-optee/device-node</a>
- **environ :**  None
- **summary :**  Check OP-TEE device node has been probed in the system.
- **description :**  
```
None
```
- **command :**  
```
node="$(find /dev -type c -regex '.*/\(tee\|teepriv\)[0-9]')"
if [[ -n $node ]]; then
  echo -e "\nInfo: Find OP-TEE node in the system!"
  for x in $node
    do
      echo -e "\n$x"
    done
else
  echo -e "\nError: Not able to find OP-TEE node in the system!"
  exit 1
fi
```

[Back to top](#top)
### <a id='ce-oem-optee/xtest-check'>ce-oem-optee/xtest-check</a>
- **environ :**  None
- **summary :**  Check if xtest is in the system.
- **description :**  
```
None
```
- **command :**  
```
tool=$(look_up_xtest.py)
exit_status=$?
if [[ "$exit_status" -eq 0 ]]; then
    echo "Info: Found xtest runnable $tool"
else
    echo "Error: Not able to found xtest runnable tool"
    exit 1
fi
```

[Back to top](#top)
### <a id='ce-oem-optee/ta-install'>ce-oem-optee/ta-install</a>
- **environ :**  None
- **summary :**  Install Trusted Applications for xtest
- **description :**  
```
None
```
- **command :**  
```
tool=$(look_up_xtest.py)
ta_path=""
if [[ "$tool" == "x-test.xtest" ]]; then
    ta_path="$(find /var/snap -wholename */lib/optee_armtz)"
else
    gadget=$(awk -F"." '{ print $1}' <<< "$tool")
    ta_path="/snap/$gadget/current/lib/optee_armtz/"
fi
if [[ -z "$(find "$ta_path" -mindepth 1 -type f -o -type d)" ]]; then
    echo -e "\nError: Not able to find TA!"
    exit 1
else
    echo -e '\nAttempting to install TA ...'
    if ! "$tool" --install-ta "$ta_path"; then
        echo -e '\nError: TA installed FAIL!'
        exit 1
    else
        echo -e '\nInfo: TA installed SUCCESS!'
    fi
fi
```

[Back to top](#top)
### <a id='ce-oem-optee-test-list'>ce-oem-optee-test-list</a>
- **environ :**  OPTEE_CASES
- **summary :**  Collect the test cases support by OP-TEE test(xtest)
- **description :**  
```
None
```
- **command :**  
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
- **environ :**  OPTEE_CASES
- **summary :**  Collect the test cases related with PKCS11 support by OP-TEE test(xtest)
- **description :**  
```
None
```
- **command :**  
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
### <a id='ce-oem-optee/xtest-suite-description'>ce-oem-optee/xtest-suite-description</a>
- **environ :**  None
- **summary :**     OP-TEE test by using xtest to test suite {{ suite }} {{ description }}
- **template_summary :**  None
- **description :**  
```
None
```
- **command :**  
```
   {{ tool }} -t {{ suite }} {{ test_id }}
```

[Back to top](#top)
### <a id='ce-oem-optee/xtest-pkcs11-description'>ce-oem-optee/xtest-pkcs11-description</a>
- **environ :**  None
- **summary :**     OP-TEE test by using xtest to test PKCS11 related {{ description }}
- **template_summary :**  None
- **description :**  
```
None
```
- **command :**  
```
   {{ tool }} -t {{ suite }} {{ test_id }}
```

[Back to top](#top)
