#!/bin/bash

BASE_URL="https://oem-share.canonical.com/partners"
DCD_FILE="/run/mnt/ubuntu-seed/.disk/info"

convert_to_url() {
  local dcd_string="$1"
  # Examples:
  # canonical-oem-carlsbad:element-v2-uc24:20241205.15:v2-uc24-x01
  # canonical-oem-shiner:x8high-som-pdk:20241209-10:
  # canonical-oem-denver::20241201-124:

  if [[ "$dcd_string" =~ ^canonical-oem-([a-zA-Z0-9]+):([a-zA-Z0-9-]*):([0-9.-]+)(:(.*))?$ ]]; then
    # Rule 1: Input string must start with "canonical-oem-" Mandatory
    # Rule 2: Project Name (alphabets and numbers) - Mandatory
    # Rule 3: Series (alphabets, numbers, and dash "-") - Optional
    # Rule 4: Build ID (Numbers, dot ".", and dash "-") - Mandatory
    # Rule 5: Additional Information (No limitation) - Optional
    local project_name="${BASH_REMATCH[1]}"
    local series="${BASH_REMATCH[2]}"  # optional
    local build_id="${BASH_REMATCH[3]}"
    local additional_info="${BASH_REMATCH[4]}"  # optional
    local image_name=""

    if [ -n "$series" ]; then
      image_name="${project_name}-${series}-${build_id}.tar.xz"
      echo "$BASE_URL/${project_name}/share/${series}/${build_id}/${image_name}"
    else
      image_name="${project_name}-${build_id}.tar.xz"
      echo "$BASE_URL/${project_name}/share/${build_id}/${image_name}"
    fi
  else
    echo "Invalid DCD format: $dcd_string" >&2
    exit 1
  fi
}

if [ -f "$DCD_FILE" ]; then
  dcd_string=$(cat "$DCD_FILE")
  url=$(convert_to_url "$dcd_string") || exit 1
  echo "$url"
  exit 0
else
  echo "DCD file not found: $DCD_FILE" >&2
  exit 1
fi