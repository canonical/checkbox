
## <a id='top'>environ keys for strict-confinement tests</a>

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

## Detailed test cases contains environ variable
### <a id='dbus-cold-boot-reboot'>dbus-cold-boot-reboot</a>
- **summary:**
Perform cold reboot via dbus

- **description:**
```
This test will check your system shutdown/booting cycle via dbus command.
```

- **file:**
[source file](confinement.pxu#L1)

- **environ:**
STRESS_BOOT_WAKEUP_DELAY RTC_DEVICE_FILE

- **command:**
```
set -e
rtcwake -d "${RTC_DEVICE_FILE:-rtc0}" -v -m on -s "${STRESS_BOOT_WAKEUP_DELAY:-120}" &
test-strict-confinement.reboot cold
```
[Back to top](#top)

### <a id='dbus-cold-boot-test'>dbus-cold-boot-test</a>
- **summary:**
Cold boot system configuration test via dbus

- **description:**
```
This is a job to check system bootup without error after cold reboot.
```

- **file:**
[source file](confinement.pxu#L24)

- **environ:**
LD_LIBRARY_PATH

- **command:**
```
reboot_check_test.sh -c "$PLAINBOX_SESSION_SHARE/before_reboot" -d "$PLAINBOX_SESSION_SHARE/cold_reboot" -s -f
```
[Back to top](#top)

### <a id='dbus-warm-boot-test'>dbus-warm-boot-test</a>
- **summary:**
Warm boot system configuration test via dbus

- **description:**
```
This is a job to check system bootup without error after warm reboot.
```

- **file:**
[source file](confinement.pxu#L59)

- **environ:**
LD_LIBRARY_PATH

- **command:**
```
reboot_check_test.sh -c "$PLAINBOX_SESSION_SHARE/before_reboot" -d "$PLAINBOX_SESSION_SHARE/warm_reboot" -s -f
```
[Back to top](#top)
