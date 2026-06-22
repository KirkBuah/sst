"""
Summary figure of the Jellyfish-board HammingMesh routing investigation, for the
email to the professor. No SST runs -- all numbers are the measured results recorded
in README.md / output/router_load/*.log.

  Panel A: AllToAll completion time, Jellyfish / mesh ratio (1.0 = mesh), per approach,
           at 256 nodes (board 4x4 / global 4x4) and 1024 nodes (board 4x4 / global 8x8).
  Panel B: where the bottleneck link sits at 256 nodes -- board->tree uplink max vs
           intra-board max (Mb) -- showing the uplink funnel getting fixed while the
           intra-board hotspot takes over.

Usage:  uv run python plot_summary.py
"""

import os
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                   "output", "router_load", "summary_attempts.png")

# --- Panel A: jf/mesh completion-time ratio (1.0 = mesh) -------------------
# 256 nodes: baseline, gateway-balanced, gateway+multipath
# 1024 nodes: baseline, (gateway-balanced not measured), gateway+multipath
approaches = ["Jellyfish\nbaseline", "gateway\nbalanced", "gateway +\nmultipath"]
ratio_256 = [2.25, 3.47, 2.19]
ratio_1024 = [2.38, None, 2.63]   # gateway-balanced not run at 1024

# --- Panel B: bottleneck link load at 256 nodes (Mb) -----------------------
labels_b = ["mesh", "Jellyfish\nbaseline", "gateway\nbalanced", "gateway +\nmultipath"]
uplink_max = [60.6, 151.0, 50.5, 50.5]
intra_max = [44.6, 86.0, 235.0, 147.0]

BLUE, RED, GREY = "#1f77b4", "#d62728", "#7f7f7f"


def main():
    fig, (axA, axB) = plt.subplots(1, 2, figsize=(15, 5.5))

    # Panel A
    x = np.arange(len(approaches))
    w = 0.38
    b256 = [r if r is not None else 0 for r in ratio_256]
    b1024 = [r if r is not None else 0 for r in ratio_1024]
    barsA1 = axA.bar(x - w / 2, b256, w, color=BLUE, label="256 nodi (global 4x4)")
    barsA2 = axA.bar(x + w / 2, b1024, w, color=RED, label="1024 nodi (global 8x8)")
    axA.axhline(1.0, color="black", ls="--", lw=1)
    axA.text(len(approaches) - 0.5, 1.04, "mesh = 1.0", ha="right", fontsize=9)
    for bars, vals in ((barsA1, ratio_256), (barsA2, ratio_1024)):
        for rect, v in zip(bars, vals):
            if v is None:
                axA.text(rect.get_x() + rect.get_width() / 2, 0.06, "n/d",
                         ha="center", va="bottom", fontsize=8, color=GREY, rotation=90)
            else:
                axA.text(rect.get_x() + rect.get_width() / 2, v + 0.04,
                         "%.2fx" % v, ha="center", va="bottom", fontsize=9)
    axA.set_xticks(x)
    axA.set_xticklabels(approaches)
    axA.set_ylabel("tempo di completamento  (Jellyfish / mesh)")
    axA.set_title("AllToAll: Jellyfish vs mesh\n(piu' basso e' meglio; 1.0 = pari al mesh)")
    axA.set_ylim(0, 3.9)
    axA.legend(loc="upper right")
    axA.grid(True, axis="y", alpha=0.3)

    # Panel B
    xb = np.arange(len(labels_b))
    barsB1 = axB.bar(xb - w / 2, uplink_max, w, color=BLUE, label="uplink board->fat-tree (max)")
    barsB2 = axB.bar(xb + w / 2, intra_max, w, color=RED, label="link intra-board (max)")
    for bars, vals in ((barsB1, uplink_max), (barsB2, intra_max)):
        for rect, v in zip(bars, vals):
            axB.text(rect.get_x() + rect.get_width() / 2, v + 3,
                     "%.0f" % v, ha="center", va="bottom", fontsize=8)
    axB.set_xticks(xb)
    axB.set_xticklabels(labels_b)
    axB.set_ylabel("carico sul link piu' carico  (Mb)")
    axB.set_title("Dove si sposta il collo di bottiglia (256 nodi)\nfunnel sugli uplink -> hotspot intra-board")
    axB.set_ylim(0, 260)
    axB.legend(loc="upper left")
    axB.grid(True, axis="y", alpha=0.3)

    fig.suptitle("HammingMesh con board Jellyfish: tentativi di fix del routing e risultati",
                 fontsize=13)
    fig.tight_layout(rect=[0, 0, 1, 0.95])
    fig.savefig(OUT, dpi=130)
    print("-> %s" % OUT)


if __name__ == "__main__":
    main()
