#!/usr/bin/env bash

# Fail visibly: the core nvpmodel plan requires the nvpmodel snap.
if [ ! -d /snap/nvpmodel ]; then
    echo "nvpmodel snap not installed" >&2
    exit 1
fi
model_count=$(sudo snap run nvpmodel.nvpmodel --parse --verbose | grep -c POWER_MODEL)
f=$((model_count - 1))
while [ "$f" -ge 0 ]
do
 printf "mode_id: %s\n" "$f"
 if [ "$f" -eq "$((model_count - 1))" ]
 then
  printf "previous_read_id:\n"
 else
  printf "previous_read_id: jetson-core-nvpmodel/get_mode_%s\n" "$x"
 fi
 printf "\n"
 x=$f
 f=$((f - 1))
done
