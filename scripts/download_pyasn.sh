#!/bin/bash

# downloads pyasn clone with ability to download data for specific dates
git clone --branch dates_from_file_46 https://github.com/SteffenDE/pyasn/

d=2018-01-01
while [ "$d" != 2023-01-15 ]; do
  echo "$d"
  c=$(date -d "$d" "+%Y%m%d")
  ./pyasn/pyasn-utils/pyasn_util_download.py -46 --date "$c"
  ./pyasn/pyasn-utils/pyasn_util_convert.py --single "rib.$c"* "pyasn-$d.db"
  d=$(date -I -d "$d + 1 day")
done
