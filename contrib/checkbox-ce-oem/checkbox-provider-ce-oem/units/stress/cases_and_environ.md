
## <a id='top'>environ keys for stress tests</a>

- LD_LIBRARY_PATH
    - Affected Test Cases:
        - [ce-oem-init-boot-loop-data](#ce-oem-init-boot-loop-data)
        - [ce-oem-post-cold-boot-loop-by-pdu-reboot1](#ce-oem-post-cold-boot-loop-by-pdu-reboot1)
        - [ce-oem-post-cold-boot-loop-by-pdu-rebootreboot_id](#ce-oem-post-cold-boot-loop-by-pdu-rebootreboot_id)
- STRESS_BOOT_WAKEUP_DELAY
    - Affected Test Cases:
        - [ce-oem-cold-boot-loop-by-pdu-reboot1](#ce-oem-cold-boot-loop-by-pdu-reboot1)
        - [ce-oem-cold-boot-loop-by-pdu-rebootreboot_id](#ce-oem-cold-boot-loop-by-pdu-rebootreboot_id)
- STRESS_BOOT_WAIT_DELAY
    - Affected Test Cases:
        - [ce-oem-cold-boot-loop-by-pdu-rebootreboot_id](#ce-oem-cold-boot-loop-by-pdu-rebootreboot_id)
- NETWORK_PDU_TYPE
    - Affected Test Cases:
        - [ce-oem-cold-boot-loop-by-pdu-rebootreboot_id](#ce-oem-cold-boot-loop-by-pdu-rebootreboot_id)
- NETWORK_PDU_CONF
    - Affected Test Cases:
        - [ce-oem-cold-boot-loop-by-pdu-rebootreboot_id](#ce-oem-cold-boot-loop-by-pdu-rebootreboot_id)

## Detailed test cases contains environ variable
### <a id='ce-oem-init-boot-loop-data'>ce-oem-init-boot-loop-data</a>
- **summary:**
Generate the baseline data set to test against

- **description:**
```
This creates baseline data sets which be considered the master
copies and all further tests will be compared against these.
```

- **file:**
[source file](boot.pxu#L1)

- **environ:**
LD_LIBRARY_PATH

- **command:**
```
reboot_check_test.sh -d "$PLAINBOX_SESSION_SHARE/before_reboot"
```
[Back to top](#top)

### <a id='ce-oem-post-cold-boot-loop-by-pdu-reboot1'>ce-oem-post-cold-boot-loop-by-pdu-reboot1</a>
- **summary:**
Post cold reboot service check - loop 1

- **description:**
```
Check there are no failed services after the cold reboot
```

- **file:**
[source file](boot.pxu#L43)

- **environ:**
LD_LIBRARY_PATH

- **command:**
```
reboot_check_test.sh -c "$PLAINBOX_SESSION_SHARE/before_reboot" -d "$PLAINBOX_SESSION_SHARE/reboot_cycle1" -s
```
[Back to top](#top)

### <a id='ce-oem-post-cold-boot-loop-by-pdu-rebootreboot_id'>ce-oem-post-cold-boot-loop-by-pdu-rebootreboot_id</a>
- **summary:**
Post cold reboot service check - loop {reboot_id}

- **template_summary:**
None

- **description:**
```
Check there are no failed services after the cold reboot
```

- **file:**
[source file](boot.pxu#L90)

- **environ:**
LD_LIBRARY_PATH

- **command:**
```
   reboot_check_test.sh -c "$PLAINBOX_SESSION_SHARE/before_reboot" -d "$PLAINBOX_SESSION_SHARE/reboot_cycle{reboot_id}" -s
```
[Back to top](#top)

### <a id='ce-oem-cold-boot-loop-by-pdu-reboot1'>ce-oem-cold-boot-loop-by-pdu-reboot1</a>
- **summary:**
Cold reboot with PDU - loop 1

- **description:**
```
This tests powers off the system and then powers it on using Network PDU
The 'NETWORK_PDU_CONF,NETWORK_PDU_TYPE,STRESS_BOOT_WAIT_DELAY,STRESS_BOOT_WAKEUP_DELAY' need to be provided as following format
format:
    NETWORK_PDU_CONF=$ip:$outlet_port
    NETWORK_PDU_TYPE=$vendor
    STRESS_BOOT_WAKEUP_DELAY=$seconds
    STRESS_BOOT_WAIT_DELAY=$seconds
e.g.
    NETWORK_PDU_CONF=10.102.30.40:2
    NETWORK_PDU_TYPE=apc
    STRESS_BOOT_WAKEUP_DELAY=100
    STRESS_BOOT_WAIT_DELAY=60
```

- **file:**
[source file](boot.pxu#L16)

- **environ:**
STRESS_BOOT_WAKEUP_DELAY

- **command:**
```
cold_reboot_by_pdu.sh -t "$NETWORK_PDU_TYPE" -p "$NETWORK_PDU_CONF" -d "$STRESS_BOOT_WAKEUP_DELAY"
```
[Back to top](#top)

### <a id='ce-oem-cold-boot-loop-by-pdu-rebootreboot_id'>ce-oem-cold-boot-loop-by-pdu-rebootreboot_id</a>
- **summary:**
Cold reboot with PDU - loop {reboot_id}

- **template_summary:**
None

- **description:**
```
   This tests powers off the system and then powers it on using Network PDU
   The 'NETWORK_PDU_CONF,NETWORK_PDU_TYPE,STRESS_BOOT_WAIT_DELAY,STRESS_BOOT_WAKEUP_DELAY' need to be provided as following format
   format:
       NETWORK_PDU_CONF=$ip:$outlet_port
       NETWORK_PDU_TYPE=$vendor
       STRESS_BOOT_WAKEUP_DELAY=$seconds
       STRESS_BOOT_WAIT_DELAY=$seconds
   e.g.
       NETWORK_PDU_CONF=10.102.30.40:2
       NETWORK_PDU_TYPE=apc
       STRESS_BOOT_WAKEUP_DELAY=100
       STRESS_BOOT_WAIT_DELAY=60
```

- **file:**
[source file](boot.pxu#L59)

- **environ:**
STRESS_BOOT_WAKEUP_DELAY STRESS_BOOT_WAIT_DELAY NETWORK_PDU_TYPE NETWORK_PDU_CONF

- **command:**
```
   sleep "${{STRESS_BOOT_WAIT_DELAY:-120}}"
   cold_reboot_by_pdu.sh -t "${{NETWORK_PDU_TYPE}}" -p "${{NETWORK_PDU_CONF}}" -d "${{STRESS_BOOT_WAKEUP_DELAY:-120}}"
```
[Back to top](#top)
