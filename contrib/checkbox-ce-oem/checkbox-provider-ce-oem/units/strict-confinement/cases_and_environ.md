
## <a id='top'>environ keys for strict-confinement test</a>
- STRESS_BOOT_WAKEUP_DELAY
	- Affected Test Cases:
		- [dbus-cold-boot-reboot](#dbus-cold-boot-reboot)
- RTC_DEVICE_FILE
	- Affected Test Cases:
		- [dbus-cold-boot-reboot](#dbus-cold-boot-reboot)
- LD_LIBRARY_PATH
	- Affected Test Cases:
		- [dbus-cold-boot-test](#dbus-cold-boot-test)
		- [dbus-warm-boot-test](#dbus-warm-boot-test)

## Detailed test cases
### <a id='strict-confine/mediacard/sdhc-insert'>strict-confine/mediacard/sdhc-insert</a>
- **environ :**  None
- **summary :**  Test that insertion of an SDHC card is detected
- **description :**  
```
Verify the SDHC card insertion by checking journal log.
```
- **command :**  
```
test-strict-confinement.run-watcher insertion mediacard
```

[Back to top](#top)
### <a id='strict-confine/mediacard/sdhc-storage'>strict-confine/mediacard/sdhc-storage</a>
- **environ :**  None
- **summary :**  Test reading & writing to a SDHC Card
- **description :**  
```
This test is automated and executes after the mediacard/sdhc-insert
test is run. It tests reading and writing to the SDHC card.
```
- **command :**  
```
test-strict-confinement.usb-read-write
```

[Back to top](#top)
### <a id='strict-confine/mediacard/sdhc-remove'>strict-confine/mediacard/sdhc-remove</a>
- **environ :**  None
- **summary :**  Test that removal of an SDHC card is detected
- **description :**  
```
Verify the SDHC card insertion by checking journal log.
```
- **command :**  
```
test-strict-confinement.run-watcher removal mediacard
```

[Back to top](#top)
### <a id='dbus-cold-boot-reboot'>dbus-cold-boot-reboot</a>
- **environ :**  STRESS_BOOT_WAKEUP_DELAY RTC_DEVICE_FILE
- **summary :**  Perform cold reboot via dbus
- **description :**  
```
This test will check your system shutdown/booting cycle via dbus command.
```
- **command :**  
```
set -e
rtcwake -d "${RTC_DEVICE_FILE:-rtc0}" -v -m on -s "${STRESS_BOOT_WAKEUP_DELAY:-120}" &
test-strict-confinement.reboot cold
```

[Back to top](#top)
### <a id='dbus-cold-boot-test'>dbus-cold-boot-test</a>
- **environ :**  LD_LIBRARY_PATH
- **summary :**  Cold boot system configuration test via dbus
- **description :**  
```
This is a job to check system bootup without error after cold reboot.
```
- **command :**  
```
reboot_check_test.sh -c "$PLAINBOX_SESSION_SHARE/before_reboot" -d "$PLAINBOX_SESSION_SHARE/cold_reboot" -s -f
```

[Back to top](#top)
### <a id='dbus-warm-boot-reboot'>dbus-warm-boot-reboot</a>
- **environ :**  None
- **summary :**  Perform warm reboot via dbus
- **description :**  
```
Perform warm reboot of the system via dbus command.
```
- **command :**  
```
test-strict-confinement.reboot warm
```

[Back to top](#top)
### <a id='dbus-warm-boot-test'>dbus-warm-boot-test</a>
- **environ :**  LD_LIBRARY_PATH
- **summary :**  Warm boot system configuration test via dbus
- **description :**  
```
This is a job to check system bootup without error after warm reboot.
```
- **command :**  
```
reboot_check_test.sh -c "$PLAINBOX_SESSION_SHARE/before_reboot" -d "$PLAINBOX_SESSION_SHARE/warm_reboot" -s -f
```

[Back to top](#top)
### <a id='strict-confinement/timedatectl-timezone'>strict-confinement/timedatectl-timezone</a>
- **environ :**  None
- **summary :**  Test timezone control with timedatectl
- **description :**  
```
Test timezon control with timedatectl command in strict confinement mode.
```
- **command :**  
```
test-strict-confinement.timedatectl-timezone
```

[Back to top](#top)
### <a id='strict-confinement/timedatectl-ntp'>strict-confinement/timedatectl-ntp</a>
- **environ :**  None
- **summary :**  Test NTP service with timedatectl
- **description :**  
```
The test ensures that the system's local time can sync with the NTP service.
Additionally, it verifies that the system's local time can be set up when
the NTP service is inactive in strict confinement mode.
```
- **command :**  
```
test-strict-confinement.timedatectl-ntp
```

[Back to top](#top)
### <a id='strict-confine/temperature-test'>strict-confine/temperature-test</a>
- **environ :**  None
- **summary :**  Check Thermal temperature of {{ name }} - {{ type }}
- **template_summary :**  None
- **description :**  
```
   Test a thermal temperature for {{ name }} - {{ type }}.
```
- **command :**  
```
   test-strict-confinement.thermal-test monitor -n {{ name }} --extra-commands "dd if=/dev/zero of=/dev/null"
```

[Back to top](#top)
