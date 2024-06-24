
## <a id='top'>environ keys for serial test</a>
- SERIAL_CONSOLE_PORTS
	- Affected Test Cases:
		- [ce-oem-serial/serial-console-list](#ce-oem-serial/serial-console-list)
- SERIAL_PORTS
	- Affected Test Cases:
		- [ce-oem-serial/serial-list](#ce-oem-serial/serial-list)

## Detailed test cases
### <a id='ce-oem-serial/serial-console-list'>ce-oem-serial/serial-console-list</a>
- **environ :**  SERIAL_CONSOLE_PORTS
- **summary :**  Generates a serial console resource based on user supplied configuration
- **description :**  
```
A serial console resource that relies on the user
specifying the number of serial console port. 
This is to allow template jobs to then be instantiated.
TYPE:NODE:BAUDRATE
SERIAL_CONSOLE_PORTS=USB:/dev/ttyUSB1:115200
```
- **command :**  
```
if [ -z "$SERIAL_CONSOLE_PORTS" ]; then
    exit 0
fi
serial_config_parser.py "$SERIAL_CONSOLE_PORTS"
```

[Back to top](#top)
### <a id='ce-oem-serial/serial-list'>ce-oem-serial/serial-list</a>
- **environ :**  SERIAL_PORTS
- **summary :**  Generates a serial resource based on user supplied configuration
- **description :**  
```
A serial resource that relies on the user
specifying the number of serial port. 
This is to allow template jobs to then be instantiated.
TYPE:NODE:BAUDRATE
SERIAL_PORTS="RS485:/dev/ttyS0:9600 RS485:/dev/ttyS1:9600 RS232:/dev/ttyS2:115200"
```
- **command :**  
```
if [ -z "$SERIAL_PORTS" ]; then
    exit 0
fi
serial_config_parser.py "$SERIAL_PORTS"
```

[Back to top](#top)
### <a id='ce-oem-serial/serial-console-tests'>ce-oem-serial/serial-console-tests</a>
- **environ :**  None
- **summary :**  To check if the serial port {{ type }} ({{ node }}) can work as a console
- **template_summary :**  To check if the serial ports can work as a console
- **description :**  
```
   Have to connect the serial port back to itself
   before starting this test
```
- **command :**  
```
   serial_test.py {{ node }} --mode console --type {{ type }} --baudrate {{ baudrate }}
```

[Back to top](#top)
### <a id='ce-oem-serial/serial-transmit-data-tests'>ce-oem-serial/serial-transmit-data-tests</a>
- **environ :**  None
- **summary :**  None
- **template_summary :**  Transmit data via serial ports
- **description :**  
```
   Have to connect the serial port to serial testing server
```
- **command :**  
```
   serial_test.py {{ node }} --mode client --type {{ type }} --group {{ group }} --baudrate {{ baudrate }}
```

[Back to top](#top)
