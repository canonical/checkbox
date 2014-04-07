#!/bin/sh

OUTPUT=`mktemp -d`
gst_pipeline_test -t 5 "autoaudiosrc ! audioconvert ! level name=recordlevel interval=10000000 ! audioconvert ! wavenc ! filesink location=$OUTPUT/test.wav"
aplay $OUTPUT/test.wav
rm $OUTPUT/test.wav
rmdir $OUTPUT
