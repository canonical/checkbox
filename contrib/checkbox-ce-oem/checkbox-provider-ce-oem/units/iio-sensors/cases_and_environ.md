
## <a id='top'>environ keys for iio-sensors tests</a>

- IIO_SENSORS
    - Affected Test Cases:
        - [ce-oem-iio-sensors/resource](#ce-oem-iio-sensors/resource)

## Detailed test cases contains environ variable
### <a id='ce-oem-iio-sensors/resource'>ce-oem-iio-sensors/resource</a>
- **summary:**
Generates a IIO sensors mapping for IIO sensor test

- **description:**
```
A IIO sensors mapping. By giving an IIO sensors on machnie to generates test jobs.
Usage of parameter:
    IIO_SENSORS=sensor_name:sensor_type|sensor_name:sensor_type:total_input_num(if sensor_type is adc) ...
e.g. IIO_SENSORS=adc128s052:adc:7|lps25h-press:pressure
```

- **file:**
[source file](jobs.pxu#L1)

- **environ:**
IIO_SENSORS

- **command:**
```
iio_sensor_test.py sensor-resource "$IIO_SENSORS"
```
[Back to top](#top)
