#!/bin/bash
BASE_URL="https://oem-share.canonical.com/partners"

# dcd_string="DCD: canonical-oem-somerville-noble-oem-24.04a-proposed-20240719-45"
dcd_string=$(ubuntu-report show | grep -w "DCD")
image_name=$(echo "$dcd_string" | cut -d':' -f2 | sed 's/^ "//;s/"$//' | sed 's/^canonical-//')

component_count=$(echo "$image_name" | awk -F'-' '{print NF}')
case $component_count in
    6)
        # expected: "somerville-noble-hwe-20240709-33.iso"
        IFS='-' read -r _ project series kernel_type build_date build_number <<< "$image_name"
        url="$BASE_URL/$project/share/releases/$series/$kernel_type/$build_date-$build_number/"
        ;;
    7)
        # expected: "somerville-noble-oem-24.04a-20240709-33.iso"
	IFS='-' read -r _ project series kernel_type kernel_version build_date build_number <<< "$image_name"
        url="$BASE_URL/$project/share/releases/$series/$kernel_type-$kernel_version/$build_date-$build_number/"
        ;;
    8)
        # expected: "somerville-noble-oem-24.04a-proposed-20240709-33.iso"
        IFS='-' read -r _ project series kernel_type kernel_version kernel_suffix build_date build_number <<< "$image_name"
        url="$BASE_URL/$project/share/releases/$series/$kernel_type-$kernel_version-$kernel_suffix/$build_date-$build_number/"
        ;;
    *)
        echo "Unexpected format: $image_name"
        exit 1
        ;;
esac

echo "$url"
 
