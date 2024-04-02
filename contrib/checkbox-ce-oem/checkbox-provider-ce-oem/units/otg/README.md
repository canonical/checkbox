# This is a file introducing USB OTG test jobs.


## id: otg_ports
  This resource job requires the checkbox environment variable "OTG". It defines
  which USB ports need to support OTG function, and we are going to test them.
  Usage of parameter: OTG={port1}:{node1} {port2}:{node2} ...
>OTG=USB-C1:11200000 USB-Micro:112a1000

The "port" here means the physical port number or port ID for your DUT.
It should be something like USB1/USB2 or any wording that can identify the
port you are going to test.
The "node" here is the node defined in the device tree, and we need something
like "38100000" to be filled in the checkbox environment variable.
>/sys/firmware/devicetree/base/soc@0/usb@32f10100/usb@38100000/

You can use the following command to find the USB dr_mode that defined in
the device tree.
```
$ sudo find / -name dr_mode
find: File system loop detected; ‘/run/mnt/base’ is part of the same file system loop as ‘/’.
find: File system loop detected; ‘/snap/core20/1977’ is part of the same file system loop as ‘/’.
/sys/firmware/devicetree/base/soc@0/usb@32f10108/usb@38200000/dr_mode
/sys/firmware/devicetree/base/soc@0/usb@32f10100/usb@38100000/dr_mode
```
This resource job will combine port name, node address, dr_mode, and USB Device
Controller (UDC) together and print it out port by port as output.
```
USB_port: J3
USB_Node: 38200000
Mode: host
UDC: None

USB_port: J2
USB_Node: 38100000
Mode: otg
UDC: 38100000.usb
```

## id: ce-oem-otg/g_serial-{USB_port}
## id: ce-oem-otg/g_mass_storage-{USB_port}
## id: ce-oem-otg/g_ether-{USB_port}
  Above tree template jobs will be generated based on the output of otg_ports. We will focus on g_serial, g_mass_storage, and g_ether only, as USB OTG gadgets support lots of features, and it is unlikely that we will be able to cover all of them. For more details, you can refer to the following [web page](http://trac.gateworks.com/wiki/linux/OTG)
  We are currently focusing on the ARM platform, as we have not yet put effort into studying the related path for the X86 platform.
