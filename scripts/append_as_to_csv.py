import argparse
import pyasn
import os
import re
import glob
import lzma
from datetime import date, timedelta

parser = argparse.ArgumentParser()
parser.add_argument("--input")
parser.add_argument("--ip-field", dest="ipfield", type=int, default=0)
parser.add_argument("--asndb-directory", dest="asndb_root", type=str, default="pyasn")
parser.add_argument("-o", "--output")
args = parser.parse_args()

timestamp = re.search("\d{4}\-\d{2}\-\d{2}", args.input).group(0)
asndb_root = args.asndb_root
asndb_file = f"{asndb_root}/pyasn-{timestamp}.db"

if not os.path.isfile(asndb_file):
    ts_parsed = date.fromisoformat(timestamp)
    ts_curr = ts_parsed
    while not os.path.isfile(asndb_file):
        if ts_curr.year < 2018:
            print("No pyasn file found for date", timestamp)
            exit()
        ts_curr = ts_curr - timedelta(days=1)
        asndb_file = f"{asndb_root}/pyasn-{ts_curr}.db"

print(f"Processing file {args.input}, using db {asndb_file}")
asndb = pyasn.pyasn(asndb_file)

outfile = ".".join(os.path.basename(args.input).split(".")[:-1])

if args.output:
    outfile = os.path.join(args.output, outfile)

with lzma.open(args.input) as f, open(outfile, "w") as fw:
    next(f)
    for line in f:
        ip = line.decode().strip().split(",")[args.ipfield]
        asn, _ = asndb.lookup(ip)
        fw.write(f"{ip},{asn}\n")
