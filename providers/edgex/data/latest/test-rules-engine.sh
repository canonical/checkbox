#!/bin/bash -e

# This test validates the rules engine (aka Kuiper) that is supported by
# the edgexfoundry snap. There are four test scenarios:
# 1. when enable/disable Kuiper and ensures that both 
# Kuiper and app-service-configurable are started/stopped;
# 2. ensure Kuiper can create a stream from edgex source;
# 3. ensure Kuiper can create a type of rule with log sink, 
# or a type of rule with MQTT sink;
# 4. validate the operation of stream and rule (status, stop, delete).

# get the directory of this script
# snippet from https://stackoverflow.com/a/246128/10102404
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null && pwd )"

# load the latest release utils
# shellcheck source=/dev/null
source "$SCRIPT_DIR/utils.sh"

START_TIME=$(date +"%Y-%m-%d %H:%M:%S")

snap_remove

# install the snap to make sure it installs
if [ -n "$REVISION_TO_TEST" ]; then
    snap_install "$REVISION_TO_TEST" "$REVISION_TO_TEST_CHANNEL" "$REVISION_TO_TEST_CONFINEMENT"
else
    snap_install edgexfoundry "$DEFAULT_TEST_CHANNEL"
fi

# wait for services to come online
snap_wait_all_services_online

# install and start edgex-device-virtual
# TODO: change channel to latest/stable when available
snap remove edgex-device-virtual
snap install edgex-device-virtual --channel=latest/edge
snap start edgex-device-virtual

i=0
reading_count=0

while [ "$reading_count" -eq 0 ] ; 
do
    ((i=i+1))
    echo "waiting for edgex-device-virtual produce readings, current retry count: $i/60"
    sleep 1
    #max retry avoids forever waiting
    if [ "$i" -ge 60 ]; then
        echo "waiting for edgex-device-virtual produce readings, reached maximum retry count of 60"
        print_error_logs
        snap_remove
        exit 1
    fi
    reading_count=$(curl -s -X 'GET'   'http://localhost:59880/api/v2/reading/count' | jq -r '.Count')
done
echo "edgex-device-virtual is producing readings now"

# change kuiper's log level to DEBUG, before the first start
sed -i -e 's@debug\: false@debug\: true@' /var/snap/edgexfoundry/current/kuiper/etc/kuiper.yaml
# enable kuiper/rules engine, as it's disabled by default
snap set edgexfoundry kuiper=on
snap_wait_port_status 59720 open


# make sure that kuiper/rules engine is started
if [ -n "$(snap services edgexfoundry.kuiper | grep edgexfoundry.kuiper | grep inactive)" ] ; then
    echo "kuiper is not running"
    print_error_logs
    snap_remove
    exit 1
fi

# make sure that app-service-configurable is started as well
if [ -n "$(snap services edgexfoundry.app-service-configurable | grep edgexfoundry.app-service-configurable | grep inactive)" ] ; then
    echo "app-service-configurable is not running"
    print_error_logs
    snap_remove
    exit 1
fi

# create a stream
if [ -z "$(edgexfoundry.kuiper-cli create stream stream1 '()WITH(FORMAT="JSON",TYPE="edgex")' | grep '\bStream stream1 is created\b')" ] ; then
    echo "cannot create kuiper stream"
    print_error_logs
    snap_remove
    exit 1
else
    echo "create kuiper stream successfully"
fi

# create rule_log
create_rule_log=$(edgexfoundry.kuiper-cli create rule rule_log '
{
   "sql":"SELECT * from stream1",
   "actions":[
      {
         "log":{
            
         }
      }
   ]
}' | grep '\bRule rule_log was created successfully\b')

if [ -z "$create_rule_log" ] ; then
    >&2 echo $create_rule_log 
    echo "cannot create kuiper rule_log)"
    print_error_logs
    snap_remove
    exit 1
else
    echo "create rule_log sucessfully"
fi

# if mqtt broker not exit, then install it
if [ -z "$(lsof -i -P -n -S 2 | grep 1883)" ]; then
    snap install mosquitto
    mqtt_broker_is_installed=true
    echo "mosquitto installed"
fi

# create rule_mqtt
create_rule_mqtt=$(edgexfoundry.kuiper-cli create rule rule_mqtt '
{
   "sql":"SELECT * from stream1",
   "actions":[
      {
         "mqtt":{
            "clientId": "stream1",
            "protocolVersion": "3.1",
            "server": "tcp://localhost:1883",
            "topic": "sink-result"
         }
      }
   ]
}' | grep '\bRule rule_mqtt was created successfully\b')

if [ -z "$create_rule_mqtt" ] ; then
    >&2 echo $create_rule_mqtt 
    echo "cannot create kuiper rule_mqtt"
    print_error_logs
    snap_remove
    exit 1
else
    echo "create rule_mqtt) sucessfully"
fi

# create rule_edgex_message_bus
create_rule_edgex_message_bus=$(edgexfoundry.kuiper-cli create rule rule_edgex_message_bus '
{
   "sql":"SELECT * from stream1",
   "actions": [
      {
         "edgex": {
            "connectionSelector": "edgex.redisMsgBus",
            "topicPrefix": "edgex/events/device", 
            "messageType": "request",
            "deviceName": "device-test"
         }
      }
   ]
}' | grep '\bRule rule_edgex_message_bus was created successfully\b')

if [ -z "$create_rule_edgex_message_bus" ] ; then
    >&2 echo $create_rule_edgex_message_bus    
    echo "cannot create kuiper rule_edgex_message_bus)"
    print_error_logs
    snap_remove
    exit 1
else
    echo "create rule_edgex_message_bus) sucessfully"
fi

# get rule's status to check if rule_log works
if [ -n "$(edgexfoundry.kuiper-cli getstatus rule rule_log | grep '\bStopped: canceled manually or by error\b')" ] ; then
    >&2 echo $(edgexfoundry.kuiper-cli getstatus rule rule_log)
    echo "cannot run rule_log"
    print_error_logs
    snap_remove
    exit 1
else
    echo "run rule_log sucessfully"
fi

# get rule's status to check if rule_mqtt works
if [ -n "$(edgexfoundry.kuiper-cli getstatus rule rule_mqtt | grep '\bStopped: canceled manually or by error\b')" ] ; then
    >&2 echo $(edgexfoundry.kuiper-cli getstatus rule rule_mqtt)
    echo "cannot run rule_mqtt"
    print_error_logs
    snap_remove
    exit 1
else
    echo "run rule_mqtt sucessfully"
fi

i=0
while [ -n "$(edgexfoundry.kuiper-cli getstatus rule rule_edgex_message_bus| grep '"source_stream1_0_records_in_total": 0')" ] ; 
do
    ((i=i+1))
    echo "waiting for readings come into stream, current retry count: $i/60"
    sleep 1
    #max retry avoids forever waiting
    if [ "$i" -ge 60 ]; then
        echo "waiting for readings come into stream reached maximum retry count of 60"
        print_error_logs
        snap_remove
        exit 1
    fi
done
echo "readings come into stream now"

if [ -n "$(edgexfoundry.kuiper-cli getstatus rule rule_edgex_message_bus| grep '\bStopped: canceled manually or by error\b')" ] ||
   [ -n "$(edgexfoundry.kuiper-cli getstatus rule rule_edgex_message_bus| grep '"sink_edgex_0_0_records_out_total": 0')" ] ; then
    echo "rule_edgex_message_bus status:"
    >&2 echo $(edgexfoundry.kuiper-cli getstatus rule rule_edgex_message_bus)
    echo "cannot run rule_edgex_message_bus"
    print_error_logs
    snap_remove
    exit 1
else
    echo "run rule_edgex_message_bus sucessfully"
fi

# stop a rule
if [ -z "$(edgexfoundry.kuiper-cli stop rule rule_log | grep '\bRule rule_log was stopped\b')" ] || 
   [ -z "$(edgexfoundry.kuiper-cli stop rule rule_mqtt | grep '\bRule rule_mqtt was stopped\b')" ] ; then
    >&2 echo $(edgexfoundry.kuiper-cli stop rule rule_log)
    >&2 echo $(edgexfoundry.kuiper-cli stop rule rule_mqtt)
    echo "cannot stop rule"
    print_error_logs
    snap_remove
    exit 1
else
    echo "stop rule_log sucessfully"
    echo "stop rule_mqtt sucessfully"
fi

# drop a rule
if [ -z "$(edgexfoundry.kuiper-cli drop rule rule_log | grep '\bRule rule_log is dropped\b')" ] || 
   [ -z "$(edgexfoundry.kuiper-cli drop rule rule_mqtt | grep '\bRule rule_mqtt is dropped\b')" ] ; then
    >&2 echo $(edgexfoundry.kuiper-cli drop rule rule_log)
    >&2 echo $(edgexfoundry.kuiper-cli drop rule rule_mqtt)
    echo "cannot drop rule"
    print_error_logs
    snap_remove
    exit 1
else
    echo "drop rule_log sucessfully"
    echo "drop rule_mqtt sucessfully"
fi

# drop a stream
if [ -z "$(edgexfoundry.kuiper-cli drop stream stream1 | grep '\bStream stream1 is dropped\b')" ] ; then
    >&2 echo $(edgexfoundry.kuiper-cli drop stream stream1)
    echo "cannot drop stream"
    print_error_logs
    snap_remove
    exit 1
else
    echo "drop stream sucessfully"
fi

# disable the kuiper for app-service-configurable
snap set edgexfoundry kuiper=off
snap_wait_port_status 59720 close

# check that kuiper/rules engine is no longer running 
if [ -z "$(snap services edgexfoundry.kuiper | grep edgexfoundry.kuiper | grep inactive)" ]; then
    echo "kuiper failed to stop app-service-configurable"
    print_error_logs
    snap_remove
    exit 1
fi

# check that app-service-configurable is no longer running as well
if [ -z "$(snap services edgexfoundry.app-service-configurable | grep edgexfoundry.app-service-configurable | grep inactive)" ]; then
    echo "kuiper failed to stop app-service-configurable"
    print_error_logs
    snap_remove
    exit 1
fi

# remove the snap to run the next test
snap remove edgex-device-virtual
snap_remove

# remove the MQTT broker if we installed it
if [ "$mqtt_broker_is_installed" = true ] ; then
    snap remove --purge mosquitto
    echo "mosquitto removed"
fi

