#!/bin/bash

# Author: Amjad Ouled-Ameur <ouledameur.amjad@baylibre.com>

CLK_TABLE=
CLK_SUMMARY=
NR_MISSING_CLKS=

if [ "$1" = "-h" ] || [ "$1" = "--help" ]; then
	printf "verify-ccf -t clock-table.h -s clk_summary\n\n"
	printf "options:\n"
	printf ""
	printf "	-t, --table	Clock table from the source code\n"
	printf "	-s, --summary	Output of \"/sys/kernel/debug/clk/clk_summary\"\n"
	exit
fi

while [[ $# -gt 0 ]]; do
	key="$1"

	case $key in
		-t|--table)
			CLK_TABLE="$2"
			shift # past argument
			shift # past value
			;;
		-s|--summary)
			CLK_SUMMARY="$2"
			shift
			shift
			;;
		*) # unknown option
			shift # past argument
			;;
	esac
done

# Extract clocks names from clock table header
grep -oP '(?<=#define CLK_).*' "${CLK_TABLE}" | awk '{print tolower($1)}' > clk-table-parsed.txt

# Remove some prefixes and suffixes to match clock summary 
sed -i '/_nr_clk/d' clk-table-parsed.txt # number of clocks
sed -i 's/_self$/f/g' clk-table-parsed.txt
sed -i 's/^apmixed_//g' clk-table-parsed.txt
sed -i 's/^top_//g' clk-table-parsed.txt

# Sort clock table alphabetically
sort -o clk-table-parsed.txt clk-table-parsed.txt

# Extract clock names from clk_summary
awk '{print $1}' "${CLK_SUMMARY}" > clk-summary-parsed.txt

# Remove some prefixes to match clock table
sed -i 's/^top_//g' clk-summary-parsed.txt

# Sort clock names of clk_summary
sort -o clk-summary-parsed.txt clk-summary-parsed.txt

# Diff
diff clk-table-parsed.txt clk-summary-parsed.txt | grep -v "^[0-9c0-9]" > missing-clocks-raw.txt

# Get only missing clocks in clk_summary
grep -oP '(?<=\< ).*' missing-clocks-raw.txt > missing-clocks-lcase.txt

# Transform to uppercase for convenience
dd if=missing-clocks-lcase.txt of=missing-clocks.txt conv=ucase 1>/dev/null 2>&1

NR_MISSING_CLKS=$(wc -l < missing-clocks.txt)

if [ "${NR_MISSING_CLKS}" -ne "0" ]; then
	printf "[-] Missing clocks: \n"
	cat missing-clocks.txt

	printf "\n[-] Count missing clocks: "${NR_MISSING_CLKS}"\n"
else
	printf "[-] Success, all clocks are mapped !\n"
fi

rm missing-clocks-raw.txt missing-clocks-lcase.txt clk-summary-parsed.txt clk-table-parsed.txt
