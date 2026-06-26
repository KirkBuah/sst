"""
Before/after overlay of the Jellyfish-board HammingMesh routing fix, from the JSON
dumps written by `router_load_diag.py --save_json`. No SST runs.

  Left panel : board->fat-tree uplink load, sorted high->low, for Jellyfish BASELINE
               (single-gateway funnel, spiky) vs Jellyfish FIXED (balanced gateways,
               flat), with the 2D-mesh as a dashed reference. The single clearest
               "the funnel disappeared" picture.
  Right panel: where the busiest link sits, baseline vs fixed -- uplink max, intra-
               board max, and the overall busiest link (Mb) -- showing the uplink
               hotspot collapsing while the bottleneck moves onto the intra-board
               fabric. Completion-vs-mesh ratio + uplink skew annotated.

Usage:
    uv run python plot_before_after.py --board_shape 4x4 --global_shape 4x4
    uv run python plot_before_after.py --board_shape 4x4 --global_shape 8x8
"""

import os
import json
from argparse import ArgumentParser

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
OUT_DIR = os.path.join(SCRIPT_DIR, "output", "router_load")

RED, GREEN, BLUE = "#d62728", "#2ca02c", "#1f77b4"


def _load(board, glob, tag):
    path = os.path.join(OUT_DIR, "data_%s_%s_%s.json" % (board, glob, tag))
    with open(path) as f:
        return json.load(f)


def _mb(bits):
    return (bits or 0) / 1e6


def main():
    ap = ArgumentParser(description="Before/after overlay of the Jellyfish routing fix")
    ap.add_argument("--board_shape", default="4x4")
    ap.add_argument("--global_shape", default="4x4")
    args = ap.parse_args()
    board, glob = args.board_shape, args.global_shape

    base = _load(board, glob, "baseline")
    fix = _load(board, glob, "fixed")
    n = base.get("nodes", "?")

    jb, jf = base["topos"]["jellyfish"], fix["topos"]["jellyfish"]
    mesh = base["topos"]["mesh"]

    # completion vs mesh
    def ratio(t):
        return t["topos"]["jellyfish"]["completion_us"] / t["topos"]["mesh"]["completion_us"]
    r_base, r_fix = ratio(base), ratio(fix)

    fig, (axL, axR) = plt.subplots(1, 2, figsize=(15, 5.5))

    # --- Left: uplink load distribution (Mb), sorted ----------------------
    series = (
        ([_mb(b) for b in mesh["uplinks_sorted"]], BLUE, "--", "2D-mesh (reference)"),
        ([_mb(b) for b in jb["uplinks_sorted"]], RED, "-", "Jellyfish baseline (funneled)"),
        ([_mb(b) for b in jf["uplinks_sorted"]], GREEN, "-", "Jellyfish fixed (balanced)"),
    )
    for vals, c, ls, lab in series:
        axL.plot(range(len(vals)), vals, color=c, ls=ls, lw=1.9, label=lab)
    axL.set_xlabel("board→fat-tree uplinks, sorted by load (busiest first)")
    axL.set_ylabel("load on the uplink  (Mb)")
    axL.set_title("Board→fat-tree uplink load\n"
                  "baseline spikes at one gateway · fixed is flat, like the mesh")
    axL.legend()
    axL.grid(True, alpha=0.3)

    # --- Right: where the busiest link sits, baseline vs fixed (Mb) -------
    groups = ["uplink\nmax", "intra-board\nmax", "busiest\nlink (any)"]
    base_vals = [_mb(jb["uplink"]["max"]), _mb(jb["intra"]["max"]), _mb(jb["busiest_bits"])]
    fix_vals = [_mb(jf["uplink"]["max"]), _mb(jf["intra"]["max"]), _mb(jf["busiest_bits"])]
    x = np.arange(len(groups))
    w = 0.38
    b1 = axR.bar(x - w / 2, base_vals, w, color=RED, label="baseline")
    b2 = axR.bar(x + w / 2, fix_vals, w, color=GREEN, label="fixed")
    for bars in (b1, b2):
        for rect in bars:
            axR.text(rect.get_x() + rect.get_width() / 2, rect.get_height(),
                     "%.0f" % rect.get_height(), ha="center", va="bottom", fontsize=8)
    axR.set_xticks(x)
    axR.set_xticklabels(groups)
    axR.set_ylabel("load on the busiest link of that class  (Mb)")
    axR.set_title("Where the bottleneck sits (Jellyfish)\n"
                  "completion vs mesh:  baseline %.2f×  →  fixed %.2f×" % (r_base, r_fix))
    axR.legend(loc="upper left")
    axR.grid(True, axis="y", alpha=0.3)
    ymax = max(base_vals + fix_vals)
    axR.set_ylim(0, ymax * 1.28)
    # annotate the uplink-skew collapse
    txt = ("uplink max/mean:  %.1f×  →  %.1f×\nuplink CV:  %.2f  →  %.2f" % (
        jb["uplink"]["max"] / jb["uplink"]["mean"], jf["uplink"]["max"] / jf["uplink"]["mean"],
        jb["uplink"]["cv"], jf["uplink"]["cv"]))
    axR.text(0.97, 0.97, txt, transform=axR.transAxes, ha="right", va="top", fontsize=9,
             bbox=dict(boxstyle="round", fc="#f5f5f5", ec="#999999"))

    fig.suptitle("HammingMesh Jellyfish routing — before vs after the fix\n"
                 "board %s / global %s (%s nodes)  ·  fix = balanced gateways + adaptive "
                 "intra-board multipath" % (board, glob, n), fontsize=13)
    fig.tight_layout(rect=[0, 0, 1, 0.93])
    out = os.path.join(OUT_DIR, "before_after_%s_%s.png" % (board, glob))
    fig.savefig(out, dpi=130)
    print("-> %s" % out)
    print("   completion vs mesh:  baseline %.2fx  ->  fixed %.2fx" % (r_base, r_fix))


if __name__ == "__main__":
    main()
