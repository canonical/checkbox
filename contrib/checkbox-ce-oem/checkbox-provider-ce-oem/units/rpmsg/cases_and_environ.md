
## <a id='top'>environ keys for rpmsg tests</a>

- RPMSG_RP_FIRMWARE_MAPPING
    - Affected Test Cases:
        - [ce-oem-rpmsg/rp-firmware-mapping](#ce-oem-rpmsg/rp-firmware-mapping)
- RPMSG_RP_FIRMWARE_PATH
    - Affected Test Cases:
        - [ce-oem-rpmsg/rp-firmware-mapping](#ce-oem-rpmsg/rp-firmware-mapping)

## Detailed test cases contains environ variable
### <a id='ce-oem-rpmsg/rp-firmware-mapping'>ce-oem-rpmsg/rp-firmware-mapping</a>
- **summary:**
List Remote Processor firmwares and RPMSG node mapping

- **description:**
```
List firmware and RPMSG node mapping for reload Remote Processor firmware test
RPMSG_RP_FIRMWARE_MAPPING="remoteproc0:test-1.elf remoteproc0:test-2.elf"
RPMSG_RP_FIRMWARE_PATH="/home/user1"
```

- **file:**
[source file](jobs.pxu#L36)

- **environ:**
RPMSG_RP_FIRMWARE_MAPPING RPMSG_RP_FIRMWARE_PATH

- **command:**
```
rpmsg_load_firmware.py resource-reload --path "$RPMSG_RP_FIRMWARE_PATH" --mapping "$RPMSG_RP_FIRMWARE_MAPPING"
```
[Back to top](#top)
