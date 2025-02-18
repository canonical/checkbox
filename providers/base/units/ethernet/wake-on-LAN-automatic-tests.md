# This is a file introducing Wake-on-LAN automatic test jobs

  To make the test of Wake-on-LAN automatic, we need:
  The device under test (DUT) obtains its own network interface's MAC and IP address, retrieves the Wake-on-LAN server's IP and port from environment variables, sends the IP and MAC to the Wake-on-LAN server, it records the current timestamp and suspends itself after receiving a successful response from the server.

  A Wake-on-LAN HTTP server that receives requests from the device under test (DUT), extracts the DUT's MAC and IP addresses from the request, and then sends a Wake-on-LAN command to the DUT in an attempt to power it on.

  Once the DUT wakes up, it compares the previously recorded timestamp with the time when the system last exited suspend mode. If the system wakes up within a reasonable timeframe, it can be inferred that the wake-up was triggered by the Wake-on-LAN request, indicating a successful test. Otherwise, the system was woken up by the RTC, it implies that the Wake-on-LAN attempt failed.

## id: ethernet/wol_auto_S3_{{ interface }}

## Test Case enviroment
WOL server:
  - apt install wakeonlan
  - pip install fastapi
  - pip install uvicorn
  - running wol_server.py

DUT:
  - manifest:
    - has_ethernet_adapter
    - has_ethernet_wake_on_lan_support
    - has_wake_on_lan_server

  - enviroment variable:
    - SERVER_WAKE_ON_LAN
      - Specifies the address of the server responsible for handling Wake-on-LAN requests.
      - Format: <IP_address>:<port>
      - Example: SERVER_WAKE_ON_LAN=192.168.0.1:8090
    - WAKE_ON_LAN_DELAY
      - The time (in seconds) to wait between sending the Wake-on-LAN packet and checking for a response from the target device.
      - Example: WAKE_ON_LAN_DELAY=60
    - WAKE_ON_LAN_RETRY
      - The number of times to retry sending the Wake-on-LAN packet if the initial attempt fails.
      - Example: WAKE_ON_LAN_RETRY=3

## Test scripts
### 1. wol_client.py
```
usage: wol_client.py [-h] --interface INTERFACE --target TARGET [--delay DELAY] [--retry RETRY] [--waketype WAKETYPE] [--powertype POWERTYPE] [--timestamp_file TIMESTAMP_FILE]

  options:
    -h, --help            show this help message and exit
    --interface INTERFACE
                          The network interface to use.
    --target TARGET       The target IP address or hostname.
    --delay DELAY         Delay between attempts (in seconds).
    --retry RETRY         Number of retry attempts.
    --waketype WAKETYPE   Type of wake operation.eg 'g' for magic packet
    --powertype POWERTYPE
                          Type of s3 or s5.
    --timestamp_file TIMESTAMP_FILE
                          The file to store the timestamp of test start.
```
### 2. wol_check.py
```
usage: wol_check.py [-h] --interface INTERFACE [--powertype POWERTYPE] [--timestamp_file TIMESTAMP_FILE] [--delay DELAY] [--retry RETRY]

  options:
    -h, --help            show this help message and exit
    --interface INTERFACE
                          The network interface to use.
    --powertype POWERTYPE
                          Waked from s3 or s5.
    --timestamp_file TIMESTAMP_FILE
                          The file to store the timestamp of test start.
    --delay DELAY         Delay between attempts (in seconds).
    --retry RETRY         Number of retry attempts.
```
### 3. wol_server.py

Listen on the specified port to receive and handle the DUT's requests.

```
uvicorn wol_server:app --host 0.0.0.0 --port 8090
```

## Work process of the Wake-on-LAN automatic test
1. The DUT gets its own NIC's MAC and IP, fetches WOL server info from environment variables, sends data to the server, receives a success response, records timestamp, sets rtcwake, and suspends.

2. The WOL server receives DUT requests, extracts MAC, IP, delay, and retry count. After sending a success response, it waits, sends a WOL command, waits, and pings. If the ping fails, it retries up to the specified retry times.

3. After system resume up, the DUT compares the resume time to the stored timestamp. If the elapsed time is between 0 and 1.5(delay*retry), WOL is assumed; otherwise, an RTC wake-up is inferred.

## Limitation and Future work
The initial plan was to automate Wake-on-LAN testing for both S3 and S5 system states. The test would be split into two sub-test jobs:

1. Pre-S3/S5 Job (wol_client.py): This job would run before entering either the S3 or S5 state. Its primary function would be to gather information, send requests, and record timestamps.
2. Post-Recovery Job (wol_check.py): This job, running on the S3 or S5 system itself after recovery, would perform log checks to determine if WoL triggered system wake-up.

However, due to current limitations in Checkbox, we cannot guarantee a strict execution order for test jobs. This makes the initial approach infeasible. Consequently, with the current setup, we can only automate WoL testing for S3.

We would like to keep the two scripts separately. This allows for future implementation of automated WoL testing for S5 if we can find a way to specify the strictly execution order of test jobs in the future.
