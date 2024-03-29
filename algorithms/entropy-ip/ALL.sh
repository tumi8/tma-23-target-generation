#!/bin/bash
#
# This code runs all parts of Entropy/IP in one shot.
#
# Copyright (c) 2015-2016 Akamai Technologies, Inc.
# See file "LICENSE" for licensing information.
# Author: Pawel Foremski
#

function ips()
{
	if [ "${IPS##*.}" = "gz" ]; then
		cat $IPS | zcat
	else
		cat $IPS
	fi
}

if [ $# -ne 2 ]; then
	echo "usage: ALL.sh ips target"
	echo
	echo "Entropy/IP: do all steps and prepare a web report on IPv6 addrs"
	echo
	echo "  ips         IPv6 addresses in hex ip format"
	echo "  target      target directory for the report"
	echo
	echo "Copyright (c) 2015-2016 Akamai Technologies, Inc."
	echo "See file LICENSE for licensing information."
	echo "Author: Pawel Foremski"
	exit 1
fi >&2

IPS="$1"
WORKDIR="$2"
DIR="$2"/out

set -o pipefail
set -o errexit
set -o nounset

mkdir -p "$DIR"
[ -d "$DIR" ] || exit 1

echo "1. segments"
ips | "$WORKDIR"/a1-segments.py /dev/stdin \
	>"$DIR"/segments || exit 2

echo -e "\n2. segment mining"
ips | "$WORKDIR"/a2-mining.py /dev/stdin "$DIR"/segments \
	>"$DIR"/analysis || exit 3

echo -e "\n3. bayes model"
ips | "$WORKDIR"/a3-encode.py /dev/stdin "$DIR"/analysis \
	| "$WORKDIR"/a4-bayes-prepare.sh /dev/stdin "$WORKDIR"\
	>"$DIR"/bnfinput || exit 4
"$WORKDIR"/a5-bayes.sh "$DIR"/bnfinput \
	>"$DIR"/cpd || exit 5

echo -e "\n4. web report"
"$WORKDIR"/b1-webreport.sh "$DIR" "$DIR"/segments "$DIR"/analysis "$DIR"/cpd "$WORKDIR" \
	|| exit 6

exit 0
