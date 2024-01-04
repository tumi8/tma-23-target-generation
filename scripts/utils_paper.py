import subprocess
import tqdm
import json
import pyasn
import itertools
import functools
import numpy as np
import matplotlib.pyplot as plt
from cycler import cycler

# Spelling unification of PeeringDB categories
def clean_peeringdb(cat):
    try:
        return {
            "Cable/DSL/ISP": "ISP",
            "Educational/Research": "Educational"
        }[cat]
    except KeyError:
        return cat

# short spelling of PeeringDB categories
def shorten_peeringdb(cat):
    try:
        return {
            "Educational": "EDU",
            "Content": "CDN",
            "Non-Profit": "ORG",
            "Unknown": "UNK"
        }[cat]
    except KeyError:
        return cat

# load a peeringdb json file
def load_peeringdb(fn):
    with open(fn) as f:
        peering_data = json.loads(f.read())["net"]["data"]
    return dict([(el["asn"], el["info_type"]) for el in peering_data])

# returns the cleaned or shortened network category for an AS number according to the peeringdb object
def lookup_peeringdb(asn, db, filter=True, shorten=False):
    if not isinstance(asn, int):
        try:
            asn = int(asn)
        except (ValueError, TypeError):
            ascat = "Unknown"
    
    try:
        ascat = db[asn]
    except KeyError:
        ascat = "Unknown"

    if not ascat:
        ascat = "Unknown"
    
    if filter and (not ascat in ['NSP', 'Educational/Research', 'Cable/DSL/ISP', 'Content', 'Non-Profit']):
        ascat = "Others"
    
    if shorten:
        return shorten_peeringdb(clean_peeringdb(ascat))
    return clean_peeringdb(ascat)

wc = lambda x: int(subprocess.check_output(["wc", "-l", x]).decode().strip().split(" ")[0])

# Analyze a file of addresses for the distribution of contained network categories
# Returns two dictionaries:
#  - one contains the amount of addresses for each network category
#  - one returns the set of contained ASes for each network category
def categ(fn, asndb, peeringdb, total=0, dofilter=False):
    total = 0
    cat_distr = dict()
    cat_distr_ases = dict()
    with open(fn) as f:
        try:
            next(f)
        except StopIteration:
            return 0, cat_distr
        
        for line in tqdm.tqdm(f, total=total):
            total += 1
            ip = line.strip().split(",")[0]
            asn, pfx = asndb.lookup(ip)

            ascat = lookup_peeringdb(asn, peeringdb, filter=dofilter)

            if not ascat in cat_distr:
                cat_distr[ascat] = 0
                cat_distr_ases[ascat] = set()

            cat_distr[ascat] += 1
            cat_distr_ases[ascat].add(asn)
    
    for cat in cat_distr_ases:
        cat_distr_ases[cat] = len(cat_distr_ases[cat])
            
    return cat_distr_ases, cat_distr


###
# Static values
###


CATS = [
    "Content",
    "NSP",
    "Educational",
    "Non-Profit",
    "ISP",
    "Full"
]

CATS_ORDER = [
    "Content",
    "ISP",
    "NSP",
    "Educational",
    "Non-Profit",
    "Full"
]

CATS_NO_FULL = [
    "Content",
    "NSP",
    "Educational",
    "Non-Profit",
    "ISP",
    "Others"
]

PROTOS = [
    "total",
    "icmp",
    "tcp80",
    "tcp443",
    "udp53",
    "udp443"
]

PROTOS_NO_TOTAL = [
    "icmp",
    "tcp80",
    "tcp443",
    "udp53",
    "udp443"
]

ALGOS = [
    '6Forest',
    '6GAN',
    '6GCVAE',
    '6Graph',
    '6Hit',
    '6Scan',
    '6Tree',
    '6VecLM',
    'DET',
    'Entropy'
]

CATS_NO_FULL_ORDER = [
    "Content",
    "ISP",
    "NSP",
    "Educational",
    "Non-Profit",
    "Others"
]

CATS_ORDER_SHORT = [
    "CDN",
    "ISP",
    "NSP",
    "EDU",
    "ORG",
    "Full"
]

CATS_NO_FULL_ORDER_SHORT = [
    "CDN",
    "ISP",
    "NSP",
    "EDU",
    "ORG",
    "Others"
]


###
# Different formatting helper functions
###


percentage = lambda x: f"{x:.2f}\%" if x > 0 else "0\%"
percentage_small = lambda x: f"{x:.0f}\%" if x > 0 else "0\%"
percentage_small_plt = lambda x, pos: f"{x:.0f}\%" if x > 0 else "0\%"
percentage_latex = lambda x: f"\\sperc{{{x:.2f}}}" if x > 0 else "\\sperc{{0}}"
linestyle_cycler = (cycler("color", plt.cm.viridis(np.linspace(0,1,5))) + cycler('linestyle',['-','--',':','-.', '-']))

from matplotlib.colors import LogNorm
from matplotlib.ticker import FuncFormatter

def unit(x, prec=2):
    x = int(x)
    if x > 1000000000:
        return "{:.{prec}f}B".format(x / 1000000000, prec=prec)
    elif x > 1000000:
        return "{:.{prec}f}M".format(x / 1000000, prec=prec)
    elif x > 1000:
        return "{:.{prec}f}k".format(x / 1000, prec=prec)
    else:
        return str(x)
    
def unit_latex(x, prec=2):
    x = int(x)
    if x > 1000000:
        return "\\sm{{{:.{prec}f}}}".format(x / 1000000, prec=prec)
    elif x > 1000:
        return "\\sk{{{:.{prec}f}}}".format(x / 1000, prec=prec)
    else:
        return num_latex(x, 0)
    
def num_latex(x, prec=2):
    return "\\num{{{:.{prec}f}}}".format(x, prec=prec)

def num_latex_adaptive(x):
    if x < 1000:
        return num_latex(x, 2)
    else:
        return num_latex(x, 0)


###
# LaTeX/Matplotlib formatting tricks
###
    

def set_size(width, fraction=1, subplots=(1, 1)):
    """Set figure dimensions to avoid scaling in LaTeX.

    Parameters
    ----------
    width: float or string
            Document width in points, or string of predined document type
    fraction: float, optional
            Fraction of the width which you wish the figure to occupy
    subplots: array-like, optional
            The number of rows and columns of subplots.
    Returns
    -------
    fig_dim: tuple
            Dimensions of figure in inches
    """
    if width == 'thesis':
        width_pt = 426.79135
    elif width == 'beamer':
        width_pt = 307.28987
    elif width == "singlecolumn":
        width_pt = 516.0
    elif width == "doublecolumn":
        width_pt = 252.0
    else:
        width_pt = width

    # Width of figure (in pts)
    fig_width_pt = width_pt * fraction
    # Convert from pt to inches
    inches_per_pt = 1 / 72.27

    # Golden ratio to set aesthetic figure height
    # https://disq.us/p/2940ij3
    golden_ratio = (5**.5 - 1) / 2

    # Figure width in inches
    fig_width_in = fig_width_pt * inches_per_pt
    # Figure height in inches
    fig_height_in = fig_width_in * golden_ratio * (subplots[0] / subplots[1])

    return (fig_width_in, fig_height_in)
    
def rc_setting(fontsize=9):
    # Options
    return {
        # Use LaTeX to write all text
        "text.usetex": True,
        "font.family": "serif",
        # Use 10pt font in plots, to match 10pt font in document
        "axes.labelsize": fontsize,
        "font.size": fontsize,
        # Make the legend/label fonts a little smaller
        "legend.fontsize": fontsize,
        "xtick.labelsize": fontsize,
        "ytick.labelsize": fontsize,
        "axes.prop_cycle": linestyle_cycler
    }
    

# Plots a cumulativ AD distribution for a list of AS info annotated IP address files    
def plot_as_distr(files, names, tex=False, savefile=None, size=None):
    # Formatting
    if tex:
        plt.rcParams.update(rc_setting(fontsize=8))
        # Uncomment for paper scaling
        #plt.rcParams["legend.fontsize"] = 7
        plt.rcParams["legend.fontsize"] = 10
        plt.rcParams["figure.figsize"] = set_size("doublecolumn") if not size else size
        
    linestyle_cycler = (
        cycler("color", plt.cm.viridis(np.linspace(0, 1, 11))) + 
        cycler('linestyle', (['-', '--', ':', '-.'] * 10)[:len(files)])
    )
    plt.rcParams["axes.prop_cycle"] = linestyle_cycler
    
    # Read the AS ranking files (CSV with ASN,frequency per AS contained in data)
    data = []
    for fn in files:
        data_new = []
        data_cumul = 0

        with open(fn) as f:
            for line in f:
                val = int(line.strip().split(",")[1])
                data_cumul += val
                data_new.append(data_cumul)

        data_new_cumul = [el / data_cumul * 100 for el in data_new]
        if data_new_cumul:
            data.append([data_new_cumul[0]] + data_new_cumul)

    for el, lab in zip(data, names):
        plt.plot(list(range(len(el))), el, marker="", markevery=[-1], label=lab)

    plt.legend(loc="center left", bbox_to_anchor=(1, 0.45))
    plt.xscale("log")
    plt.ylim(bottom=0)
    plt.xlim(xmin=1)
    plt.yticks([i * 20 for i in range(1, 6)], labels=[f"{i * 20}\%" for i in range(1, 6)])
    plt.ylabel("Addrs in top X ASes")

    if savefile:
        plt.tight_layout()
        plt.savefig(savefile, bbox_inches="tight")
    else:
        plt.show()

        
# Plots a text-annotated heatmap from a two-dimensional array
def plot_heatmap(
    data, labelsx, labelsy, labelx, labely, labelc,
    formatter=percentage, formatter_colorbar=unit, tex=False, descr="",
    cmax=0, size="doublecolumn", frac=0.038, fontsize=9, logscale=False, savefile=None
):
    # Formatting
    plt.rcParams.update(plt.rcParamsDefault)
    plt.rcParams.update(rc_setting(fontsize=fontsize))
    
    if tex:
        height, width = set_size(size)
        plt.rcParams["figure.figsize"] = (height, width)
        
    figure = plt.figure()
    labels_mat = [[formatter(el_inner) for el_inner in el] for el in data]
    namesx = labelsx
    namesy = labelsy

    # Compute maximum values for color range
    max_val = max([max(el) for el in data])
    cmin = 0.1 if logscale else 0
    color_thres = max_val * 0.7
    
    if logscale:
        mat = plt.matshow(data, cmap=plt.cm.Blues, fignum=1, norm=LogNorm(vmin=0.1, vmax=100))
    else:
        mat = plt.matshow(data, cmap=plt.cm.Blues, fignum=1)
    
    # Formatting
    plt.yticks(ticks=range(len(namesy)), labels=namesy)
    plt.xticks(ticks=range(len(namesx)), labels=namesx, rotation=45, ha="left")
    
    if labelc:
        plt.colorbar(mat, fraction=frac, pad=0.04, format=FuncFormatter(formatter_colorbar), label=labelc)
    else:
        plt.colorbar(mat, fraction=frac, pad=0.04, format=FuncFormatter(formatter_colorbar))
    if formatter == percentage or formatter == percentage_small:
        plt.clim(cmin, 100)
    
    if cmax:
        plt.clim(cmin, cmax)

    # Annotate matrix fields with text
    for i in range(len(labels_mat)):
        for j in range(len(labels_mat[i])):
            label = labels_mat[i][j]
            plt.text(j, i, label, va='center', ha='center', color="white" if data[i][j] > color_thres else "black")

    # More formatting
    if descr:
        plt.title(descr)
    
    if labelx:
        plt.xlabel(labelx)
    if labely:
        plt.ylabel(labely)
    
    if savefile:
        plt.tight_layout()
        plt.savefig(savefile, bbox_inches="tight")
    else:
        plt.show()


# Helper function for stacking
def add_arrays(x, y):
    return [xi + yi for xi, yi in zip(x, y)]


# Plots a horizontally stacked bar chart from a two-dimensional array
def plot_stacked_chart(data, labels, legend, labelx, labely, descr, savefile=None, tex=False):
    if tex:
        plt.rcParams.update(rc_setting(fontsize=10))
        # Uncomment for scaling seen in paper
        #plt.rcParams.update(rc_setting(fontsize=8))
        #plt.rcParams["figure.figsize"] = set_size("doublecolumn")
    
    plt.rcParams["axes.prop_cycle"] = linestyle_cycler
    
    # Stacking
    for i, el in enumerate(data):
        if i == 0:
            bar = plt.barh(labels, el, 0.9, label=legend[i])
        else:
            bar = plt.barh(
                labels, el, 0.9, label=legend[i],
                left=functools.reduce(lambda x, y: add_arrays(x, y), data[:i])
            )
    
        plt.bar_label(
            bar,
            labels=[f"{x:.0f}\%" if x > 10 else '' for x in el],
            label_type='center',
            color='white' if i < len(data) - 1 else 'black'
        )
    
    if labelx:
        plt.xlabel(labelx)
    if labely:
        plt.ylabel(labely)
    
    plt.xticks([0, 25, 50, 75, 100], labels=["0\%", "25\%", "50\%", "75\%", "100\%"])
    plt.legend(loc="center left", bbox_to_anchor=(1, 0.5))
    
    if descr:
        plt.title(descr)
    
    if savefile:
        plt.tight_layout()
        plt.savefig(savefile, bbox_inches="tight")
    else:
        plt.show()