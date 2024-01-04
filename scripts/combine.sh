#!/bin/bash

for f in 2023-03-17-1310.csv.*; do ext=$(echo $f | cut -d . -f 3); cat 2023-03-17-1310.csv.$ext 2023-03-23-1238.csv.$ext > 2023-03-23-combined.csv.$ext; done
cat 2023-03-17.txt.expl.sortu.shuf.wl.bl.dpd.nondense.iponly 2023-03-23.txt.expl.sortu.shuf.wl.bl.dpd.nondense.iponly | sort -u > 2023-03-23-combined.txt.expl.sortu.shuf.wl.bl.dpd.nondense.iponly