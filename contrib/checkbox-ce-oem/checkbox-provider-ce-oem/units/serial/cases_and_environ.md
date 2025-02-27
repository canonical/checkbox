
## <a id='top'>environ keys for serial tests</a>

- SERIAL_CONSOLE_PORTS
    - Affected Test Cases:
        - [ce-oem-serial/serial-console-list](#ce-oem-serial/serial-console-list)
- SERIAL_PORTS
    - Affected Test Cases:
        - [ce-oem-serial/serial-list](#ce-oem-serial/serial-list)

## Detailed test cases contains environ variable
### <a id='ce-oem-serial/serial-console-list'>ce-oem-serial/serial-console-list</a>
- **summary:**
Generates a serial console resource based on user supplied configuration

- **description:**
```
A serial console resource that relies on the user
specifying the number of serial console port. 
This is to allow template jobs to then be instantiated.
TYPE:NODE:BAUDRATE
SERIAL_CONSOLE_PORTS=USB:/dev/ttyUSB1:115200
```

- **file:**
[source file](jobs.pxu#L1)

- **environ:**
SERIAL_CONSOLE_PORTS

- **command:**
```
if [ -z "$SERIAL_CONSOLE_PORTS" ]; then
    exit 0
fi
serial_config_parser.py "$SERIAL_CONSOLE_PORTS"
```
[Back to top](#top)

### <a id='ce-oem-serial/serial-list'>ce-oem-serial/serial-list</a>
- **summary:**
Generates a serial resource based on user supplied configuration

- **description:**
```
A serial resource that relies on the user
specifying the number of serial port. 
This is to allow template jobs to then be instantiated.
TYPE:NODE:BAUDRATE
SERIAL_PORTS="RS485:/dev/ttyS0:9600 RS485:/dev/ttyS1:9600 RS232:/dev/ttyS2:115200"
```

- **file:**
[source file](jobs.pxu#L44)

- **environ:**
SERIAL_PORTS

- **command:**
```
if [ -z "$SERIAL_PORTS" ]; then
    exit 0
fi
serial_config_parser.py "$SERIAL_PORTS"
```
[Back to top](#top)
