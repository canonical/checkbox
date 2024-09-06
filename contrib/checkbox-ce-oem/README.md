# checkbox-provider-ce-oem
This is a checkbox provider for both IoT and PC devices. And it will be built as SNAP named *checkbox-ce-oem*.
You can define specific plugs to connect to it and start using the test jobs and plans included in checkbox-provider-ce-oem.

# Use it as checkbox launcher
## Install required packages

### On Ubuntu classic environment (server and desktop)
```
# Install the generic checkbox content provider based on Ubuntu 22.04
$ sudo snap install checkbox22
$ sudo snap install checkbox-ce-oem --channel=22.04/edge --classic
```

### On Ubuntu Core environment
```
$ sudo snap install checkbox22
$ sudo snap install checkbox-ce-oem --channel=latest/stable --devmode
$ sudo snap connect checkbox-ce-oem:checkbox-runtime checkbox22:checkbox-runtime
$ sudo snap connect checkbox-ce-oem:provider-certification-client checkbox22:provider-certification-client
$ sudo snap connect checkbox-ce-oem:provider-checkbox checkbox22:provider-checkbox
$ sudo snap connect checkbox-ce-oem:provider-resource checkbox22:provider-resource
$ sudo snap connect checkbox-ce-oem:provider-tpm2 checkbox22:provider-tpm2
```

## Modify the checkbox configuration to fit your test environment
```
# show the checkbox configuration
$ sudo checkbox-ce-oem.configure -l
ALSADEVICE=hw:CARD=bytrt5660,DEV=0
MODEL_GRADE=signed
NET_DEVICE_INFO=ven_rsi_sdio ven_rsi_91x
OBEX_TARGET=00:02:72:C5:F9:1F
OPEN_AC_SSID=ubuntu-cert-ac-open
OPEN_BG_SSID=ubuntu-cert-bg-open
OPEN_N_SSID=ubuntu-cert-n-open
STRESS_BOOT_ITERATIONS=100
STRESS_BOOT_WAIT_DELAY=120
STRESS_BOOT_WAKEUP_DELAY=60
STRESS_S3_ITERATIONS=100
STRESS_S3_SLEEP_DELAY=60
STRESS_S3_WAIT_DELAY=120
STRESS_S4_ITERATIONS=100
STRESS_S4_SLEEP_DELAY=60
STRESS_S4_WAIT_DELAY=120
TEST_TARGET_IPERF=10.101.47.93
TPM2TOOLS_DEVICE_FILE=/dev/tpm0
TPM2TOOLS_TCTI_NAME=device
WATCHDOG_KERNEL_MOD=iTCO_wdt
WIFI_AP_SETUPTIME=30
WIFI_INTERFACE=mlan0
WPA_AC_PSK=insecure
WPA_AC_SSID=ubuntu-cert-ac-wpa
WPA_AX_PSK=insecure
WPA_AX_SSID=ubuntu-cert-ax-wpa
WPA_BG_PSK=insecure
WPA_BG_SSID=ubuntu-cert-bg-wpa
WPA_N_PSK=insecure
WPA_N_SSID=ubuntu-cert-n-wpa
WPA3_AX_PSK=insecure
WPA3_AX_SSID=ubuntu-cert-ax-wpa3
WWAN_APN=internet
WWAN_CONTROL_IF=ttyACM3
WWAN_NET_IF=ppp0
WWAN_SETUPTIME=30
RTC_DEVICE_FILE=/dev/rtc0
# modify checkbox configuration
$ sudo checkbox-ce-oem.configure WIFI_AP_SETUPTIME=50
```

## Launch checkbox session
```
$ checkbox-ce-oem.test-runner
```

# Use it as checkbox content provider
## Getting started
checkbox-ce-oem will define a slot *provider-ce-oem* to allow checkbox interface sanp to connect to access the test jobs and plans.

## In checkbox interface snap
You have to modify two parts and rebuild your SNAP of checkbox interface snap.
### snapcraft.yaml
Add a plug into plugs section in *snapcraft.yaml* of your checkbox interface snap if you are testing on Core image.
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
export LD_LIBRARY_PATH="$LD_LIBRARY_PATH:/snap/checkbox-ce-oem/current/usr/lib/$ARCH
```
### After rebuild SNAP for checkbox interface snap
Install the SNAP of checkbox interface snap and checkbox-ce-oem. Connect slot and plug of *provider-ce-oem*.

`$ sudo snap connect checkbox:provider-ce-oem checkbox-ce-oem`

### Start to using test jobs and plans in checkbox-provider-ce-oem
Now, you are able to include the job, plan or utility from checkbox-provider-ce-oem.
```
example for running a job:
$ sudo checkbox{interface snap}.checkbox-cli run com.canonical.contrib::location/gps_coordinate

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
SYS_LEDS={position1}:{path1} {position2}:{path2} ...
{path} under "/sys/class/leds/{path}"
e.g. SYS_LEDS=DL1:beat-yel-led DL2:shtdwn-grn-led

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
