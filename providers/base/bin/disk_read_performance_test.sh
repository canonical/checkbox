#!/bin/bash
#
# Verify that disk storage performs at or above baseline performance
#

#Default to a lower bound of 15 MB/s
DEFAULT_BUF_READ=${DISK_READ_PERF:-15}
DEFAULT_NVME_READ=${DISK_NVME_READ_PERF:-200}
DEFAULT_MDADM_READ=${DISK_MDADM_READ_PERF:-80}
DEFAULT_SSD_READ=${DISK_SSD_READ_PERF:-200}

# Minimum size threshold in bytes (2MB)
MIN_SIZE_THRESHOLD=$((2 * 1024 * 1024))

for disk in "$@"; do

  echo "Beginning $0 test for $disk"
  echo "---------------------------------------------------"

  # Get the size of the device in bytes
  disk_size=$(blockdev --getsize64 /dev/"$disk")

  if [ "$disk_size" -lt "$MIN_SIZE_THRESHOLD" ]; then
    echo "INFO: $disk is smaller than 2MB ($disk_size bytes). Skipping test."
    continue
  fi

  disk_type=$(udevadm info --name /dev/"$disk" --query property | grep "ID_BUS" | awk '{gsub(/ID_BUS=/," ")}{printf $1}')
  dev_path=$(udevadm info --name /dev/"$disk" --query property | grep "DEVPATH" | awk '{gsub(/DEVPATH=/," ")}{printf $1}')
  # /sys/block/$disk/queue/rotational was added with Linux 2.6.29. If file is
  # not present, test below will fail & disk will be considered an HDD, not
  # an SSD.
  rotational=$(cat /sys/block/"$disk"/queue/rotational)
  if [[ $dev_path =~ dm ]]; then
    disk_type="devmapper"
  fi
  if [[ $dev_path =~ md ]]; then
    disk_type="mdadm"
  fi
  if [[ $dev_path =~ nvme ]]; then
    disk_type="nvme"
  fi
  if [[ $dev_path =~ mmc ]]; then
    disk_type="mmc"
  fi
  if [[ $dev_path =~ pmem ]]; then
    disk_type="nvdimm"
  fi
  if [[ $dev_path =~ mtd ]]; then
    disk_type="mtd"
  fi
  if [[ ($disk_type == "scsi" || $disk_type == "ata") && $rotational == 0 ]]; then
    disk_type="ssd"
  fi
  if [ -z "$disk_type" ]; then
  echo "ERROR: disk type not recognized"
    exit 1
  fi
  echo "INFO: $disk type is $disk_type"

  case $disk_type in
    "usb" ) 
            #Custom metrics are guesstimates for now...
            MIN_BUF_READ=7
            
            # Increase MIN_BUF_READ if a USB3 device is plugged in a USB3 hub port
            if  [[ $dev_path =~ ((.*usb[0-9]+).*\/)[0-9]-[0-9\.:-]+/.* ]]; then
                device_version=$(cat '/sys/'"${BASH_REMATCH[1]}"'/version')
                hub_port_version=$(cat '/sys/'"${BASH_REMATCH[2]}"'/version')
                if [ "$(echo "$device_version >= 3.00"|bc -l)" -eq 1 ] && [ "$(echo "$hub_port_version >= 3.00"|bc -l)" -eq 1 ]; then
                    MIN_BUF_READ=80
                fi
            fi
            ;;
    "devmapper" ) MIN_BUF_READ=$DEFAULT_BUF_READ;;
    "ide" ) MIN_BUF_READ=40;;
    "mmc" ) MIN_BUF_READ=$DEFAULT_BUF_READ;;
    "mtd" ) MIN_BUF_READ=1;;
    "nvme" ) MIN_BUF_READ=$DEFAULT_NVME_READ;;
    "nvdimm" ) MIN_BUF_READ=500;;
    "mdadm" ) MIN_BUF_READ=$DEFAULT_MDADM_READ;;
    "ata" ) MIN_BUF_READ=80;;
    "scsi" ) MIN_BUF_READ=100;;
    "ssd" ) MIN_BUF_READ=$DEFAULT_SSD_READ;;
    *     ) MIN_BUF_READ=$DEFAULT_BUF_READ;;
  esac
  echo "INFO: $disk_type: Using $MIN_BUF_READ MB/sec as the minimum throughput speed"

  max_speed=0
  echo ""
  echo "Beginning hdparm timing runs"
  echo "---------------------------------------------------"

  for iteration in $(seq 1 10); do
    speed=$(hdparm -t /dev/"$disk" 2>/dev/null | grep "Timing buffered disk reads" | awk -F"=" '{print $2}' | awk '{print $1}')
    echo "INFO: Iteration $iteration: Detected speed is $speed MB/sec"

    if [ -z "$speed" ]; then
      echo "WARNING: Device $disk is too small! Aborting test."
      exit 1
    fi

    speed=${speed/.*}
    if [ "$speed" -gt $max_speed ]; then
      max_speed=$speed
    fi
  done
  echo "INFO: Maximum detected speed is $max_speed MB/sec"
  echo "---------------------------------------------------"
  echo ""
  result=0
  if [ "$max_speed" -ge "$MIN_BUF_READ" ]; then
    echo "PASS: $disk Max Speed of $max_speed MB/sec is faster than Minimum Buffer Read Speed of $MIN_BUF_READ MB/sec"
  else
    echo "FAIL: $disk Max Speed of $max_speed MB/sec is slower than Minimum Buffer Read Speed of $MIN_BUF_READ MB/sec"
    result=1
  fi
done

if [ $result -gt 0 ]; then
  echo "WARNING: One or more disks failed testing!"
  exit 1
else
  echo "All devices passed testing!"
  exit 0
fi
