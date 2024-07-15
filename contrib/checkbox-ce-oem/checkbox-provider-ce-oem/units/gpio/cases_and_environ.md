
## <a id='top'>environ keys for gpio tests</a>

- EXPECTED_GADGET_GPIO
    - Affected Test Cases:
        - [ce-oem-gpio/check-slots](#ce-oem-gpio/check-slots)

## Detailed test cases contains environ variable
### <a id='ce-oem-gpio/check-slots'>ce-oem-gpio/check-slots</a>
- **summary:**
Check gadget snap defined GPIO slots.

- **description:**
```
Use checkbox config EXPECTED_GADGET_GPIO to define the expected GPIO.
Usage EXPECTED_GADGET_GPIO=499,500:502
Sprate by comma, and also colon to define a range of ports
```

- **file:**
[source file](jobs.pxu#L1)

- **environ:**
EXPECTED_GADGET_GPIO

- **command:**
```
check_gpio.py check-gpio -c "$EXPECTED_GADGET_GPIO"
```
[Back to top](#top)
