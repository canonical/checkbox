
## <a id='top'>environ keys for digital-io test</a>
- DIGITAL_IO_LOOPBACK_GPIO
	- Affected Test Cases:
		- [ce-oem-digital-io/loopback_mapping_gpio](#ce-oem-digital-io/loopback_mapping_gpio)
- DIGITAL_IO_LOOPBACK_SERIAL
	- Affected Test Cases:
		- [ce-oem-digital-io/loopback_mapping_serial](#ce-oem-digital-io/loopback_mapping_serial)

## Detailed test cases
### <a id='ce-oem-digital-io/loopback_mapping_gpio'>ce-oem-digital-io/loopback_mapping_gpio</a>
- **environ :**  DIGITAL_IO_LOOPBACK_GPIO
- **summary :**  Generates a digital I/O loopback ports mapping for digital I/O loopback test
- **description :**  
```
A digital I/O loopback ports mapping. By giving a pair of digital I/O port on machnie to generates test jobs.
Usage of parameter:
    DIGITAL_IO_LOOPBACK_GPIO=do_port:do_gpio_pin:di_port:di_gpio_pin do_port:do_gpio_pin:di_port:di_gpio_pin ...
e.g. DIGITAL_IO_LOOPBACK_GPIO=1:733:2:765 3:734:4:766
```
- **command :**  
```
awk '{
    split($0, record, " ")
    for (i in record) {
        split(record[i], data, ":")
        printf "DO: %s\nDO_GPIO: %s\nDI: %s\nDI_GPIO: %s\n\n", data[1], data[2], data[3], data[4]
    }
}' <<< "$DIGITAL_IO_LOOPBACK_GPIO"
```

[Back to top](#top)
### <a id='ce-oem-digital-io/loopback_mapping_serial'>ce-oem-digital-io/loopback_mapping_serial</a>
- **environ :**  DIGITAL_IO_LOOPBACK_SERIAL
- **summary :**  Generates a digital I/O loopback ports mapping for digital I/O loopback test
- **description :**  
```
A digital I/O loopback ports mapping. By giving a pair of digital I/O port on machnie to generates test jobs.
Usage of parameter:
    DIGITAL_IO_LOOPBACK_SERIAL=do_port:do_byte_pin:di_port:di_byte_pin do_port:do_byte_pin:di_port:di_byte_pin ...
e.g. DIGITAL_IO_LOOPBACK_SERIAL=1:2:1:6 2:3:2:7 3:4:3:8 4:5:4:9
```
- **command :**  
```
awk '{
    split($0, record, " ")
    for (i in record) {
        split(record[i], data, ":")
        printf "DO: %s\nDO_REGISTER_BYTE: %s\nDI: %s\nDI_REGISTER_BYTE: %s\n\n", data[1], data[2], data[3], data[4]
    }
}' <<< "$DIGITAL_IO_LOOPBACK_SERIAL"
```

[Back to top](#top)
### <a id='ce-oem-digital-io/loopback_gpio_DODO-DIDI'>ce-oem-digital-io/loopback_gpio_DODO-DIDI</a>
- **environ :**  None
- **summary :**  To test loopback between DO{DO} and DI{DI}
- **template_summary :**  Loopback tests for the DO{DO}-DI{DI} pin control by GPIO
- **description :**  
```
None
```
- **command :**  
```
   echo "## Perform the digital I/O loopback test"
   echo "DO{DO} gpio pin is {DO_GPIO}"
   echo "DI{DI} gpio pin is {DI_GPIO}"
   digital_io_loopback_test.py -o {DO_GPIO} -i {DI_GPIO}
```

[Back to top](#top)
### <a id='ce-oem-digital-io/loopback_serial_DODO-DIDI'>ce-oem-digital-io/loopback_serial_DODO-DIDI</a>
- **environ :**  None
- **summary :**  To test loopback between DO{DO} and DI{DI}
- **template_summary :**  Loopback tests for the DO{DO}-DI{DI} pin control by serial console
- **description :**  
```
   The scripts will connect to the Digital IO controller via serial console
   the serial console port is defined in variable DIGITAL_IO_CONSOLE
```
- **command :**  
```
   if [[ -z "$DIGITAL_IO_CONSOLE" ]]; then
       echo "DIGITAL_IO_CONSOLE variable is not defined"
       exit 1
   fi
   echo "## Perform the digital I/O loopback test"
   echo "DO{DO} register byte is {DO_REGISTER_BYTE}"
   echo "DI{DI} register byte is {DI_REGISTER_BYTE}"
   digital_io_loopback_serial_test.py -o {DO_REGISTER_BYTE} -i {DI_REGISTER_BYTE} -s "$DIGITAL_IO_CONSOLE"
```

[Back to top](#top)
