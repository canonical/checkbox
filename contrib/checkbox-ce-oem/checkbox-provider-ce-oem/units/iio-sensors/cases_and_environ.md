
## <a id='top'>environ keys for iio-sensors test</a>
- IIO_SENSORS
	- Affected Test Cases:
		- [ce-oem-iio-sensors/resource](#ce-oem-iio-sensors/resource)

## Detailed test cases
### <a id='ce-oem-iio-sensors/resource'>ce-oem-iio-sensors/resource</a>
- **environ :**  IIO_SENSORS
- **summary :**  Generates a IIO sensors mapping for IIO sensor test
- **description :**  
```
A IIO sensors mapping. By giving an IIO sensors on machnie to generates test jobs.
Usage of parameter:
    IIO_SENSORS=device:sensor_type device:sensor_type ...
e.g. IIO_SENSORS=0:pressure 1:accelerometer 2:humidityrelative
```
- **command :**  
```
iio_sensor_test.py sensor-resource "$IIO_SENSORS"
```

[Back to top](#top)
### <a id='ce-oem-iio-sensors/check_sensor_type_index'>ce-oem-iio-sensors/check_sensor_type_index</a>
- **environ :**  None
- **summary :**  To test industrial IO {{ type }}-{{ index }}
- **template_summary :**  None
- **description :**  
```
None
```
- **command :**  
```
   echo "## Perform the industrial I/O {{ type }}-{{ index }} sensor test"
   iio_sensor_test.py test -t {{ type }} -i {{ index }}
```

[Back to top](#top)
