
## <a id='top'>environ keys for rpmsg test</a>
- RPMSG_RP_FIRMWARE_MAPPING
	- Affected Test Cases:
		- [ce-oem-rpmsg/rp-firmware-mapping](#ce-oem-rpmsg/rp-firmware-mapping)
- RPMSG_RP_FIRMWARE_PATH
	- Affected Test Cases:
		- [ce-oem-rpmsg/rp-firmware-mapping](#ce-oem-rpmsg/rp-firmware-mapping)

## Detailed test cases
### <a id='ce-oem-rpmsg/detect-device'>ce-oem-rpmsg/detect-device</a>
- **environ :**  None
- **summary :**  Check if the RPMSG devices is initialed.
- **description :**  
```
None
```
- **command :**  
```
rpmsg_tests.py --type detect
```

[Back to top](#top)
### <a id='ce-oem-rpmsg/pingpong'>ce-oem-rpmsg/pingpong</a>
- **environ :**  None
- **summary :**  Check if M series core RPMSG is loaded and pingpong demo is completed.
- **description :**  
```
None
```
- **command :**  
```
rpmsg_tests.py --type pingpong
```

[Back to top](#top)
### <a id='ce-oem-rpmsg/serial-tty'>ce-oem-rpmsg/serial-tty</a>
- **environ :**  None
- **summary :**  Check if M series core RPMSG is loaded and RPMSG TTY works.
- **description :**  
```
None
```
- **command :**  
```
rpmsg_tests.py --type serial-tty
```

[Back to top](#top)
### <a id='ce-oem-rpmsg/rp-firmware-mapping'>ce-oem-rpmsg/rp-firmware-mapping</a>
- **environ :**  RPMSG_RP_FIRMWARE_MAPPING RPMSG_RP_FIRMWARE_PATH
- **summary :**  List Remote Processor firmwares and RPMSG node mapping
- **description :**  
```
List firmware and RPMSG node mapping for reload Remote Processor firmware test
RPMSG_RP_FIRMWARE_MAPPING="remoteproc0:test-1.elf remoteproc0:test-2.elf"
RPMSG_RP_FIRMWARE_PATH="/home/user1"
```
- **command :**  
```
rpmsg_load_firmware.py resource-reload --path "$RPMSG_RP_FIRMWARE_PATH" --mapping "$RPMSG_RP_FIRMWARE_MAPPING"
```

[Back to top](#top)
### <a id='ce-oem-rpmsg/reload-rp-firmware-test'>ce-oem-rpmsg/reload-rp-firmware-test</a>
- **environ :**  None
- **summary :**  Reload Remote Processor firmware to {firmware} via RPMSG {device}
- **template_summary :**  Reload Remote Processor firmware via RPMSG
- **description :**  
```
None
```
- **command :**  
```
   rpmsg_load_firmware.py test-reload --device {device} --file {firmware} --path {path}
```

[Back to top](#top)
