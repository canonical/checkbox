#!/bin/bash

if journalctl -b 0 -u thermald -g "Unsupported condition [0-9]+ \(UKNKNOWN\)" 1> /dev/null; then
 	echo "This error occurs because OOB values appear when parsing the GDDV"
 	echo ""
 	echo "Thermald constructs conditions by parsing GDDV blob from"
 	echo "/sys/devices/platform/INT*/data_vault, and check if the parsed"
 	echo "values make sense. In particular, If the type of adaptive_condition"
       	echo "appears to be an out-of-bound value, error message of the following"
       	echo "format will show up in journal:"
 	echo ""
  	echo "	Unsupported condition %d (UKNKNOWN)"
 	echo ""
 	echo "This test job catches those erroneously parsed enum values."
 	echo ""
 	echo "See the following part of thermald source code for detail:"
 	echo "  1. cthd_gddv::verify_condition in src/thd_engine_adaptive.cpp"
 	echo "  2. enum adaptive_condition and struct condition in src/thd_gddv.h"
 	exit 1
fi
