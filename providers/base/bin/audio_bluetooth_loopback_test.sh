#!/bin/bash
#
# This file is part of Checkbox.
#
# Copyright 2014 Canonical Ltd.
#
# Authors: Daniel Manrique <roadmr@ubuntu.com>
#
# Checkbox is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License version 3,
# as published by the Free Software Foundation.
#
# Checkbox is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Checkbox.  If not, see <http://www.gnu.org/licenses/>.
#
# This simple script finds a bluetooth source and sink, and records from the
# source for 6 seconds, playing the recording back into the sink.  It helps a
# human validate that record/playback is working, human can speak into
# microphone and just ensure the speech can be heard instantly in the headset.

[ -x "`which pactl`" ] || exit 1
[ -x "`which pacat`" ] || exit 1

SINK=$(pactl list | sed -n '/monitor/d;s/Name: \(bluez_sink\.\)/\1/p')
SOURCE=$(pactl list | sed -n '/monitor/d;s/Name: \(bluez_source\.\)/\1/p')


if [ -n "$SINK" ] && [ -n "$SOURCE" ]; then
   PLAYBACK_LOG=$(mktemp --tmpdir audio_bluetooth_loopback.XXXXX)
   RECORD_LOG=$(mktemp --tmpdir audio_bluetooth_loopback.XXXXX)
   trap "rm $PLAYBACK_LOG $RECORD_LOG" EXIT
   # ensure we exit with failure if parec fails, and not with pacat
   # --playback's error code
   set -o pipefail
   # Use a short latency parameter so time between speech and hearing it is
   # short, makes for a nicer interactive experience
   LATENCY="--latency-msec=50"
   # time out after 6 seconds, forcibly kill after 8 seconds if pacat didn't
   # respond
   echo "Recording and playing back, please speak into bluetooth microphone"
   timeout -k 8 6 pacat $LATENCY --record -v -d $SOURCE 2>$RECORD_LOG | \
    pacat $LATENCY --playback -v -d $SINK 2>$PLAYBACK_LOG

   echo "RECORD LOG"
   cat $RECORD_LOG
   echo ""
   echo "PLAYBACK LOG"
   cat $PLAYBACK_LOG
else
  echo "No bluetooth audio device found"
  exit 1
fi
