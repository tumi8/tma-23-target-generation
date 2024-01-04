import argparse
import numpy as np
import matplotlib.pyplot as plt
from hitlist_utils import load_peeringdb, lookup_peeringdb
from plot_utils import rc_setting, set_size, CATS_ORDER_SHORT

parser = argparse.ArgumentParser()
parser.add_argument("input")
parser.add_argument("cats")
parser.add_argument("--lines", type=int, default=0)
args = parser.parse_args()

height, width = set_size("doublecolumn")
plt.rcParams.update(rc_setting(fontsize=8))
plt.rcParams["figure.figsize"] = (height, width)

peeringdb = load_peeringdb(args.cats)

change_data = dict()
up_sum_data = dict()
down_sum_data = dict()
with open(args.input) as f:
    for line in f:
        ipa, asn, changes, up_avg, down_avg, up_sum, down_sum = line.strip().split(",")

        ascat = lookup_peeringdb(asn, peeringdb, shorten=True)

        if not ascat in change_data:
            change_data[ascat] = []
            up_sum_data[ascat] = []
            down_sum_data[ascat] = []

        change_data[ascat].append(int(changes))
        up_sum_data[ascat].append(int(up_sum))
        down_sum_data[ascat].append(int(down_sum))

fig, axes = plt.subplots(1, 3)
for ax, data in zip(axes, [change_data, up_sum_data, down_sum_data]):
    xticks = np.arange(1, len(data) + 1)
    bp = ax.boxplot([data[cat] for cat in CATS_ORDER_SHORT], showfliers=False)
    print([(cat, bp['medians'][i].get_ydata()) for i, cat in enumerate(CATS_ORDER_SHORT)])
    ax.set_xticks(xticks)
    ax.set_xticklabels(CATS_ORDER_SHORT, rotation=45)

axes[1].set_yticklabels([int(el) for el in axes[1].get_yticks()], rotation=90, ha="center", va="center")
axes[2].set_yticklabels([int(el) for el in axes[2].get_yticks()], rotation=90, ha="center", va="center")

axes[0].set_title("State Changes")
axes[1].set_title("Uptime (days)")
axes[2].set_title("Downtime (days)")

fig.tight_layout()
plt.savefig("ipstability.pdf", bbox_inches="tight")