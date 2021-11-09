#!/bin/bash -e

# get the directory of this script
# snippet from https://stackoverflow.com/a/246128/10102404
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null && pwd )"

# load the utils
# shellcheck source=/dev/null
source "$SCRIPT_DIR/utils.sh"

DEFAULT_TEST_CHANNEL=${DEFAULT_TEST_CHANNEL:-beta}

snap_remove

# install the snap to make sure it installs
if [ -n "$REVISION_TO_TEST" ]; then
    snap_install "$REVISION_TO_TEST" "$REVISION_TO_TEST_CHANNEL" "$REVISION_TO_TEST_CONFINEMENT"
else
    snap_install edgexfoundry "$DEFAULT_TEST_CHANNEL"
fi

# wait for services to come online
# NOTE: this may have to be significantly increased on arm64 or low RAM platforms
# to accomodate time for everything to come online
sleep 120

# enable kuiper/rules engine, as it's disabled by default
snap set edgexfoundry kuiper=on
sleep 15

# make sure that kuiper/rules engine is started
if [ -n "$(snap services edgexfoundry.kuiper | grep edgexfoundry.kuiper | grep inactive)" ] ; then
    echo "kuiper is not running"
    snap_remove
    exit 1
fi

# make sure that app-service-configurable is started as well
if [ -n "$(snap services edgexfoundry.app-service-configurable | grep edgexfoundry.app-service-configurable | grep inactive)" ] ; then
    echo "app-service-configurable is not running"
    snap_remove
    exit 1
fi

# create a stream
if [ -z "$(edgexfoundry.kuiper-cli create stream stream1 '()WITH(FORMAT="JSON",TYPE="edgex")' | grep '\bStream stream1 is created\b')" ] ; then
    echo "cannot create kuiper stream"
    snap_remove
    exit 1
fi

# create a rule-log
if [ -z "$(edgexfoundry.kuiper-cli create rule rule1 '
{
   "sql":"SELECT * from stream1",
   "actions":[
      {
         "log":{
            
         }
      }
   ]
}' | grep '\bRule rule1 was created successfully\b')" ] ; then
    echo "cannot create kuiper rule (action: log)"
    snap_remove
    exit 1
fi

# create a rule-mqtt
if [ -z "$(edgexfoundry.kuiper-cli create rule rule2 '
{
   "sql":"SELECT * from stream1",
   "actions":[
      {
         "mqtt":{
            "clientId": "stream1",
            "protocolVersion": "3.1",
            "server": "tcp://localhost:6379",
            "topic": "sink-result"
         }
      }
   ]
}' | grep '\bRule rule2 was created successfully\b')" ] ; then
    echo "cannot create kuiper rule (action: mqtt)"
    snap_remove
    exit 1
fi

# get rule's status to check if rule (action: log) works
if [ -n "$(edgexfoundry.kuiper-cli getstatus rule rule1 | grep '\bStopped: canceled manually or by error\b')" ] ; then
    echo "cannot run rule's action - log"
    snap_remove
    exit 1
fi

# get rule's status to check if rule (action: mqtt) works
if [ -n "$(edgexfoundry.kuiper-cli getstatus rule rule2 | grep '\bStopped: canceled manually or by error\b')" ] ; then
    echo "cannot run rule's action - mqtt"
    snap_remove
    exit 1
fi

# stop a rule
if [ -z "$(edgexfoundry.kuiper-cli stop rule rule1 | grep '\bRule rule1 was stopped\b')" || -z "$(edgexfoundry.kuiper-cli stop rule rule2 | grep '\bRule rule2 was stopped\b')" ] ; then
    echo "cannot stop rule"
    snap_remove
    exit 1
fi

# drop a rule
if [ -z "$(edgexfoundry.kuiper-cli drop rule rule1 | grep '\bRule rule1 is dropped\b')" || -z "$(edgexfoundry.kuiper-cli drop rule rule2 | grep '\bRule rule2 is dropped\b')" ] ; then
    echo "cannot drop rule"
    snap_remove
    exit 1
fi

# drop a stream
if [ -z "$(edgexfoundry.kuiper-cli drop stream stream1 | grep '\bStream stream1 is dropped\b')" ] ; then
    echo "cannot drop stream"
    snap_remove
    exit 1
fi

# disable the kuiper for app-service-configurable
snap set edgexfoundry kuiper=off
sleep 15

# check that kuiper/rules engine is no longer running 
if [ -z "$(snap services edgexfoundry.kuiper | grep edgexfoundry.kuiper | grep inactive)" ]; then
    echo "kuiper failed to stop"
    snap_remove
    exit 1
fi

# check that app-service-configurable is no longer running as well
if [ -z "$(snap services edgexfoundry.app-service-configurable | grep edgexfoundry.app-service-configurable | grep inactive)" ]; then
    echo "kuiper failed to stop app-service-configurable"
    snap_remove
    exit 1
fi

# remove the snap to run the next test
snap_remove

