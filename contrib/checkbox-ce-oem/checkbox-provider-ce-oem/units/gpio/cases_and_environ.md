
## <a id='top'>environ keys for gpio test</a>
- EXPECTED_GADGET_GPIO
	- Affected Test Cases:
		- [ce-oem-gpio/check-slots](#ce-oem-gpio/check-slots)

## Detailed test cases
### <a id='ce-oem-gpio/check-slots'>ce-oem-gpio/check-slots</a>
- **environ :**  EXPECTED_GADGET_GPIO
- **summary :**  Check gadget snap defined GPIO slots.
- **description :**  
```
Use checkbox config EXPECTED_GADGET_GPIO to define the expected GPIO.
Usage EXPECTED_GADGET_GPIO=499,500:502
Sprate by comma, and also colon to define a range of ports
```
- **command :**  
```
check_gpio.py check-gpio -c "$EXPECTED_GADGET_GPIO"
```

[Back to top](#top)
### <a id='ce-oem-gpio-gadget-slots'>ce-oem-gpio-gadget-slots</a>
- **environ :**  None
- **summary :**  Generates a GPIO list that defined in the gadget snap
- **description :**  
```
Generates a GPIO list that is defined in the gadget snap.
This GPIO list will be used to check if the GPIO nodes have
been exported after connecting the interfaces.
```
- **command :**  
```
check_gpio.py dump
```

[Back to top](#top)
### <a id='ce-oem-gpio/node-export-test'>ce-oem-gpio/node-export-test</a>
- **environ :**  None
- **summary :**  To test node of GPIO {gpio_number} been exported
- **template_summary :**  None
- **description :**  
```
None
```
- **command :**  
```
check_gpio.py check-node -n {gpio_number} -s {slot}
```

[Back to top](#top)
