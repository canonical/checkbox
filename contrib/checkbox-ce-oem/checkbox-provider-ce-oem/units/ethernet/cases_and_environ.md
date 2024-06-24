
## <a id='top'>environ keys for ethernet test</a>
- TCP_MULTI_CONNECTIONS_SERVER_IP
	- Affected Test Cases:
		- [ce-oem-ethernet/tcp-multi-connections](#ce-oem-ethernet/tcp-multi-connections)
- TCP_MULTI_CONNECTIONS_START_PORT
	- Affected Test Cases:
		- [ce-oem-ethernet/tcp-multi-connections](#ce-oem-ethernet/tcp-multi-connections)
- TCP_MULTI_CONNECTIONS_END_PORT
	- Affected Test Cases:
		- [ce-oem-ethernet/tcp-multi-connections](#ce-oem-ethernet/tcp-multi-connections)
- TCP_MULTI_CONNECTIONS_PAYLOAD_SIZE
	- Affected Test Cases:
		- [ce-oem-ethernet/tcp-multi-connections](#ce-oem-ethernet/tcp-multi-connections)
- TCP_ECHO_SERVER_IP
	- Affected Test Cases:
		- [ce-oem-ethernet/tcp-echo-stress-interface](#ce-oem-ethernet/tcp-echo-stress-interface)
- TCP_ECHO_SERVER_PORT
	- Affected Test Cases:
		- [ce-oem-ethernet/tcp-echo-stress-interface](#ce-oem-ethernet/tcp-echo-stress-interface)
- TCP_ECHO_LOOP_ITERATIONS
	- Affected Test Cases:
		- [ce-oem-ethernet/tcp-echo-stress-interface](#ce-oem-ethernet/tcp-echo-stress-interface)

## Detailed test cases
### <a id='ce-oem-ethernet/tcp-multi-connections'>ce-oem-ethernet/tcp-multi-connections</a>
- **environ :**  TCP_MULTI_CONNECTIONS_SERVER_IP TCP_MULTI_CONNECTIONS_START_PORT TCP_MULTI_CONNECTIONS_END_PORT TCP_MULTI_CONNECTIONS_PAYLOAD_SIZE
- **summary :**  Check if the system can handle multiple connections on TCP without error.
- **description :**  
```
This job will connect to server listened ports(200 ports in total),
and send the payload(64KB) for few times of each port. This job will
send the payload after all ports connection is established.
Need a server(the same as DUT) to run the following command
before running the test. 
e.g. Run a server to listen on port range from 1024 to 1223.
$ tcp_multi_connections.py server -p 1024 -e 1223
```
- **command :**  
```
tcp_multi_connections.py client -H "$TCP_MULTI_CONNECTIONS_SERVER_IP" -p "$TCP_MULTI_CONNECTIONS_START_PORT" -e "$TCP_MULTI_CONNECTIONS_END_PORT" -P "$TCP_MULTI_CONNECTIONS_PAYLOAD_SIZE"
```

[Back to top](#top)
### <a id='ce-oem-ethernet/tcp-echo-stress-interface'>ce-oem-ethernet/tcp-echo-stress-interface</a>
- **environ :**  TCP_ECHO_SERVER_IP TCP_ECHO_SERVER_PORT TCP_ECHO_LOOP_ITERATIONS
- **summary :**  Check if TCP echo via {{ interface }} without error.
- **template_summary :**  None
- **description :**  
```
   This job will use BASH to handle TCP socket via /dev/tcp.
   Need a server to run the following command before running the test.
   $ nc -lk -p {port_num}
```
- **command :**  
```
tcpecho_stress.sh -s {{ interface }} -i "$TCP_ECHO_SERVER_IP" -p "$TCP_ECHO_SERVER_PORT" -l "$TCP_ECHO_LOOP_ITERATIONS" -o "${PLAINBOX_SESSION_SHARE}"/tcp_echo.log
```

[Back to top](#top)
