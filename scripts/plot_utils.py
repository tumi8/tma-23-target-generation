import matplotlib.pyplot as plt
import numpy as np
from cycler import cycler

CATS_ORDER = [
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
    "Others"
]

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

# use it before plotting
def rc_setting(fontsize=9):
    # Direct input
    linestyle_cycler = (cycler("color", plt.cm.viridis(np.linspace(0, 1, 5))) + cycler('linestyle', ['-', '--', ':', '-.', '-']))

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
