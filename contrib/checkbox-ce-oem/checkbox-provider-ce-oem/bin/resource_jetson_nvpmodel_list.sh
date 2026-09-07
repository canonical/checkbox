#!/usr/bin/env bash

model_count=$(nvpmodel --parse --verbose | grep -c POWER_MODEL)
f=$((model_count - 1))
while [ "$f" -ge 0 ]
do
 printf "mode_id: %s\n" "$f"
 if [ "$f" -eq "$((model_count - 1))" ]
 then
  printf "previous_read_id:\n"
 else
  printf "previous_read_id: jetson-nvpmodel/get_mode_%s\n" "$x"
 fi
 printf "\n"
 x=$f
 f=$((f - 1))
done
