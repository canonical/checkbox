
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
    IIO_SENSORS=device:sensor_type device:sensor_type ...
e.g. IIO_SENSORS=0:pressure 1:accelerometer 2:humidityrelative
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
