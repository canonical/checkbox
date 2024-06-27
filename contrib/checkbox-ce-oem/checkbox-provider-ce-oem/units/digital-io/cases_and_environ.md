
## <a id='top'>environ keys for digital-io tests</a>

- DIGITAL_IO_LOOPBACK_GPIO
    - Affected Test Cases:
        - [ce-oem-digital-io/loopback_mapping_gpio](#ce-oem-digital-io/loopback_mapping_gpio)
- DIGITAL_IO_LOOPBACK_SERIAL
    - Affected Test Cases:
        - [ce-oem-digital-io/loopback_mapping_serial](#ce-oem-digital-io/loopback_mapping_serial)

## Detailed test cases contains environ variable
### <a id='ce-oem-digital-io/loopback_mapping_gpio'>ce-oem-digital-io/loopback_mapping_gpio</a>
- **summary:**
Generates a digital I/O loopback ports mapping for digital I/O loopback test

- **description:**
```
A digital I/O loopback ports mapping. By giving a pair of digital I/O port on machnie to generates test jobs.
Usage of parameter:
    DIGITAL_IO_LOOPBACK_GPIO=do_port:do_gpio_pin:di_port:di_gpio_pin do_port:do_gpio_pin:di_port:di_gpio_pin ...
e.g. DIGITAL_IO_LOOPBACK_GPIO=1:733:2:765 3:734:4:766
```

- **file:**
[source file](jobs.pxu#L1)

- **environ:**
DIGITAL_IO_LOOPBACK_GPIO

- **command:**
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
- **summary:**
Generates a digital I/O loopback ports mapping for digital I/O loopback test

- **description:**
```
A digital I/O loopback ports mapping. By giving a pair of digital I/O port on machnie to generates test jobs.
Usage of parameter:
    DIGITAL_IO_LOOPBACK_SERIAL=do_port:do_byte_pin:di_port:di_byte_pin do_port:do_byte_pin:di_port:di_byte_pin ...
e.g. DIGITAL_IO_LOOPBACK_SERIAL=1:2:1:6 2:3:2:7 3:4:3:8 4:5:4:9
```

- **file:**
[source file](jobs.pxu#L41)

- **environ:**
DIGITAL_IO_LOOPBACK_SERIAL

- **command:**
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
