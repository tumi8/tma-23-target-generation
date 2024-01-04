#!/bin/bash

d=2018-01-01
today=$(date -I)
while [ "$d" != "$today" ]; do
  if compgen -G "$d-*" > /dev/null; then
    echo "$d"
    cat "$d-"* | sort -u > "$d-total.csv"
  fi
  d=$(date -I -d "$d + 1 day")
done