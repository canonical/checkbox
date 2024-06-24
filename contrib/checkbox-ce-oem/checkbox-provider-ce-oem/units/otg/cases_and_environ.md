
## <a id='top'>environ keys for otg test</a>
- OTG
	- Affected Test Cases:
		- [otg_ports](#otg_ports)

## Detailed test cases
### <a id='otg_ports'>otg_ports</a>
- **environ :**  OTG
- **summary :**  Gather list of USB ports and UDC.
- **description :**  
```
A USB port and UDC mapping resource that relies on the user specifying in config varirable.
Usage of parameter: OTG={port1}:{node1} {port2}:{node2} ...
e.g. OTG=USB-C1:11200000 USB-Micro:112a1000
```
- **command :**  
```
if [ "$OTG" ]; then
    multiple-otg.sh -c "$OTG"
else
    echo "OTG config variable: not found"
fi
```

[Back to top](#top)
### <a id='ce-oem-otg/g_serial-USB_port'>ce-oem-otg/g_serial-USB_port</a>
- **environ :**  None
- **summary :**  Check {USB_port} can be detected as a serial device
- **template_summary :**  None
- **description :**  
```
   Check that after connecting the device under test (DUT) to another device
   (host), {USB_port} can be detected as a serial device by the host.
```
- **command :**  
```
   # shellcheck disable=SC2050
   if [ {Mode} != "otg" ]; then
       echo -e "Error: USB mode is {Mode} mode, but expected in otg mode."
       exit 1 
   fi
   multiple-otg.sh -u {UDC} -f acm
```

[Back to top](#top)
### <a id='ce-oem-otg/g_mass_storage-USB_port'>ce-oem-otg/g_mass_storage-USB_port</a>
- **environ :**  None
- **summary :**  Check {USB_port} can be detected as a mass storage device
- **template_summary :**  None
- **description :**  
```
   Check that after connecting the device under test (DUT) to another device
   (host), {USB_port} can be detected as a mass storage device by the host.
```
- **command :**  
```
   # shellcheck disable=SC2050
   if [ {Mode} != "otg" ]; then
       echo -e "Error: USB mode is {Mode} mode, but expected in otg mode."
       exit 1 
   fi
   multiple-otg.sh -u {UDC} -f mass_storage
```

[Back to top](#top)
### <a id='ce-oem-otg/g_ether-USB_port'>ce-oem-otg/g_ether-USB_port</a>
- **environ :**  None
- **summary :**  Check {USB_port} can be detected as USB ethernet device.
- **template_summary :**  None
- **description :**  
```
   Check that after connecting the device under test (DUT) to another device
   (host), {USB_port} can be detected as a USB ethernet device by the host.
```
- **command :**  
```
   # shellcheck disable=SC2050
   if [ {Mode} != "otg" ]; then
       echo -e "Error: USB mode is {Mode} mode, but expected in otg mode."
       exit 1 
   fi
   multiple-otg.sh -u {UDC} -f ecm
```

[Back to top](#top)
