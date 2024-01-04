import argparse

from datetime import datetime
from timeline_utils import find_files
from sortedcontainers import SortedSet

parser = argparse.ArgumentParser()
parser.add_argument("--base-dir", dest="base_dir", default="hitlist", type=str)
parser.add_argument("--extension", type=str, default="total")
parser.add_argument("--limit", type=int, default="0")
parser.add_argument("--end", type=str, default="")
parser.add_argument("start", type=str)
args = parser.parse_args()

end = None if not args.end else datetime.strptime(args.end, "%Y-%m-%d")
dates, fps = find_files(args.base_dir, args.extension, args.start, args.limit)
print(f"Going through {len(dates)} dates")

# Enumerates all files in the directory
# Extracts the dates of the scans from the filesnames
# Analyzes the difference between each scan datapoint
# What IPs have been newly added, which have been removed, which have stayted
# and which have been readded from a previous scan
# Output is a csv with one line per IP address which we have seen at some point
# Each line holds the IP address (and other info such as AS/category)
# and a list of all dates where it has entered/left the hitlist
# The first is always the date when it was added to the hitlist, every other
# timestamp marks a change (i.e. online/offline).

ips_total = SortedSet([])
ips_previous = SortedSet([])
data = dict()
for date_ts, fp in zip(dates, fps):
    with open(fp) as f:
        try:
            next(f) # skip header
            ips = SortedSet([])

            for line in f:
                ipa, asn = line.strip().split(",")
                ipkey = f"{ipa},{asn}"
                ips.add(ipkey)
        except StopIteration:
            ips = SortedSet([])

    stayed = ips.intersection(ips_previous)
    new = ips.difference(ips_previous)
    gone = ips_previous.difference(ips)
    readded = new.intersection(ips_total)
    totally_new = new.difference(ips_total)

    for ip in totally_new:
        data[ip] = [date_ts]

    for ip in gone:
        data[ip].append(date_ts)

    for ip in readded:
        data[ip].append(date_ts)

    ips_previous = ips
    ips_total = ips_total.union(SortedSet(ips_previous))

    data_output = (len(ips_total), len(ips), len(stayed), len(readded), len(totally_new), len(gone))
    print(f"{date_ts}: {data_output}")

with open(args.start + "." + args.extension + ".ipstability", "w") as f:
    for key, val in data.items():
        f.write(f"{key},{';'.join(val)}\n")
