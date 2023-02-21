# checkbox-provider-ce-oem
This is a checkbox provider for both IoT and PC devices. And it will be built as SNAP named *checkbox-ce-oem*. 
You can define specific plugs to connect to it and start using the test jobs and plans included in checkbox-provider-ce-oem.

# Getting started
checkbox-ce-oem will define a slot *provider-ce-oem* to allow checkbox interface sanp to connect to access the test jobs and plans.

## In checkbox interface snap
You have to modify two parts and rebuild your SNAP of checkbox interface snap.
### snapcraft.yaml
Add a plug into plugs section in *snapcraft.yaml* of your checkbox interface snap.
```
example:

plugs:
    provider-ce-oem:
    interface: content
    target: $SNAP/providers/checkbox-provider-ce-oem

```
### wrapper_local
Add export PATH for checkbox-ce-oem in *wrapper_local* of your checkbox interface snap.
```
example:
export PATH="$PATH:$SNAP/usr/bin:$SNAP/usr/sbin:$SNAP/sbin:/snap/bin:$SNAP/bin:/snap/checkbox-ce-oem/current/usr/bin/:/snap/checkbox-ce-oem/current/usr/sbin"
```
### After rebuild SNAP for checkbox interface snap
Install the SNAP of checkbox interface snap and checkbox-ce-oem. Connect slot and plug of *provider-ce-oem*.

`$ sudo snap connect checkbox:provider-ce-oem checkbox-ce-oem`

### Start to using test jobs and plans in checkbox-provider-ce-oem
Now, you are able to include the job, plan or utility from checkbox-provider-ce-oem.
```
example for running a job:
$ sudo checkbox{interface snap}.checkbox-cli run com.canonical.qa.ceoem::location/gps_coordinate

example for using utility:
$ sudo checkbox{interface snap}.shell
$ checkbox{interface snap}.shell> lsmtd
```
### Config informations
Some of the jobs that in provider-ce-oem requires addtional variables define in checkbox config. Please refer to following:

```
id: ce-oem-gpio-leds 
GPIO_LEDS={name1}:{port1} {name2}:{port2} ...
e.g. GPIO_LEDS=dl1:488 dl2:489 dl44:507 

id: ce-oem-sysfs-leds
SYS_LEDS={path1}:{position1} {path2}:{position1} ...
{path} under "/sys/class/leds/{path}"
e.g. SYS_LEDS=beat-yel-led:DL1 shtdwn-grn-led:DL2

id: ce-oem-gpio-button-mapping
GPIO_BUTTONS={name1}:{port1} {name2}:{port2} ...
e.g. GPIO_BUTTONS=sys_restore:71 ip_addr:72 sys_discover:465

id: ce-oem-interrupts-button-mapping
INTERRUPTS_BUTTONS={name1} {name2} ...
Button {name} under "/proc/interrupts"
e.g. INTERRUPTS_BUTTONS=s1 s2

id: ce-oem-mtd/check-total-numbers
TOTAL_MTD_NUM = {numbers}
e.g. TOTAL_MTD_NUM=2

id: ce-oem-buzzer/input-pcspkr
BEEP_PATH={pc-speaker-path}
e.g. BEEP_PATH=/dev/input/event1

id: ce-oem-gpio-buzzer-mapping
GPIO_BUZZER=name1:port1:enable_value1 name2:port2:enable_value2 ...
e.g. GPIO_BUZZER=buzzer1:498:0

id: ce-oem-pwm-buzzer-mapping
PWM_BUZZER=name1:chip1:port1:enable_value1 name2:chip2:port2:enable_value2 ...
e.g. PWM_BUZZER=buzzer1:1:0:1

id: ce-oem-rtc/rtc_number
TOTAL_RTC_NUM={total-num-of-rtc}
e.g. TOTAL_RTC_NUM=2

id: ce-oem-serial/rs485-list
RS485_PORTS={port1} {port2}
e.g. RS485_PORTS=/dev/ttymxc1 /dev/ttymxc2
``` 