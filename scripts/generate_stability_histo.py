import matplotlib.pyplot as plt
import argparse
from datetime import datetime
import numpy as np
import tqdm

parser = argparse.ArgumentParser()
parser.add_argument("input")
parser.add_argument("--lines", type=int, default=0)
parser.add_argument("--outfile", type=str)
parser.add_argument("--cutoff", type=str, help="Any IP address which was added after x will not be respected")
args = parser.parse_args()

def datetime_diff(dt2, dt1):
    ts1 = datetime.strptime(dt1, "%Y-%m-%d")
    ts2 = datetime.strptime(dt2, "%Y-%m-%d")
    return (ts2 - ts1).days

def datetime_diff_cutoff(dt1):
    ts1 = datetime.strptime(dt1, "%Y-%m-%d")
    return (cutoff - ts1).days

now_ts = datetime.now().strftime("%Y-%m-%d")
cutoff = datetime.strptime(args.cutoff, "%Y-%m-%d") if args.cutoff else None

data = dict()
data_counts = dict()
data_up_avgs = dict()
data_down_avgs = dict()
counter = 0
with open(args.input) as f:
    for line in tqdm.tqdm(f, total=args.lines):
        ipa, asn, dates = line.strip().split(",")
        ipkey = f"{ipa},{asn}"
        dates = dates.split(";")
        
        if cutoff and datetime_diff_cutoff(dates[0]) < 0:
            continue
        
        datelen = len(dates)
        if not dates[-1] == now_ts:
            dates.append(now_ts)
        
        down_avg, down_sum = 0, 0
        up_avg, up_sum = 0, 0
        if len(dates) > 1:
            for i in range(1, len(dates)):
                if i % 2 == 0:
                    down_sum += datetime_diff(dates[i], dates[i - 1])
                else:
                    up_sum += datetime_diff(dates[i], dates[i - 1])

            up_avg = up_sum / (len(dates) // 2)
            if len(dates) > 2:
                down_avg = down_sum / ((len(dates) - 1) // 2)

        data[ipkey] = (datelen, up_avg, down_avg, up_sum, down_sum)

outfile = args.input + ".ipdata" if not args.outfile else args.outfile
with open(outfile, "w") as f:
    for key, val in data.items():
        f.write(f"{key},{','.join([str(el) for el in val])}\n")
