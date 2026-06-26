"""
Aggregate the per-packet gateway-exit logs written by the merlin hamming topology
when SST is run with the env var HX_GW_LOG set.

Each board switch writes <prefix>_<router_id>.csv with one row per packet that exits
the local board to the fat tree:

    timestamp_ns,gateway_gid,board,local,dim,ft_port,src,dest,dest_board,vn,variant

This script concatenates those files and, per variant (jf / jf-wrap / mesh), reports
how evenly traffic is spread across gateways -- the whole point of the imbalance
diagnosis. A spiky distribution (few gateways carrying most packets) is the funnel;
a flat one is balanced.

Usage:
    # one run, prefix points at the files written by HX_GW_LOG=output/gwlog/jf
    uv run python parse_gateway_log.py output/gwlog/jf
    # compare two runs in one figure
    uv run python parse_gateway_log.py output/gwlog/jf output/gwlog/mesh
    # explicit glob(s) also work
    uv run python parse_gateway_log.py 'output/gwlog/jf_*.csv'
"""

import sys
import glob
from argparse import ArgumentParser

import numpy as np
import pandas as pd
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

COLS = [
    "timestamp_ns", "gateway_gid", "board", "local", "dim", "ft_port",
    "src", "dest", "dest_board", "vn", "variant",
]


def load(prefix):
    """Load every CSV matching a prefix. Accepts either a path prefix (we append
    `_*.csv`) or an explicit glob/filename."""
    if any(ch in prefix for ch in "*?[") or prefix.endswith(".csv"):
        patterns = [prefix]
    else:
        patterns = [prefix + "_*.csv", prefix + ".csv"]
    files = sorted({f for p in patterns for f in glob.glob(p)})
    if not files:
        print("No files matched %r" % prefix, file=sys.stderr)
        return None
    frames = []
    for f in files:
        try:
            frames.append(pd.read_csv(f))
        except pd.errors.EmptyDataError:
            continue
    if not frames:
        return None
    df = pd.concat(frames, ignore_index=True)
    # Tag the source prefix so multiple inputs can be told apart in the figure.
    df["source"] = prefix
    print("%s: %d rows from %d files" % (prefix, len(df), len(files)))
    return df


def gini(counts):
    """Gini coefficient of a list of per-gateway counts (0 = perfectly even,
    ->1 = all load on one gateway)."""
    x = np.sort(np.asarray(counts, dtype=float))
    n = len(x)
    if n == 0 or x.sum() == 0:
        return float("nan")
    return float((2 * np.arange(1, n + 1) - n - 1).dot(x) / (n * x.sum()))


def summarize(df):
    """Per (source, variant) imbalance metrics over gateway packet counts."""
    rows = []
    for (source, variant), g in df.groupby(["source", "variant"]):
        counts = g.groupby("gateway_gid").size().values
        total = counts.sum()
        mean = counts.mean()
        std = counts.std()
        rows.append({
            "source": source,
            "variant": variant,
            "packets": int(total),
            "gateways_used": int(len(counts)),
            "max_share_%": round(100.0 * counts.max() / total, 1),
            "cov": round(std / mean, 3) if mean else float("nan"),  # coeff. of variation
            "gini": round(gini(counts), 3),
        })
    return pd.DataFrame(rows)


def main():
    ap = ArgumentParser(description=__doc__)
    ap.add_argument("prefixes", nargs="+", help="path prefix(es) or glob(s) for *_<id>.csv files")
    ap.add_argument("--out", default="gateway_log", help="output basename for the PNG/CSV")
    ap.add_argument("--bins", type=int, default=40, help="time bins for the timeline panel")
    args = ap.parse_args()

    frames = [d for d in (load(p) for p in args.prefixes) if d is not None]
    if not frames:
        print("Nothing to plot.", file=sys.stderr)
        sys.exit(1)
    df = pd.concat(frames, ignore_index=True)
    df = df[df["variant"].notna()]

    summary = summarize(df)
    print("\n=== Gateway-usage imbalance ===")
    print(summary.to_string(index=False))
    summary.to_csv(args.out + "_summary.csv", index=False)

    groups = list(df.groupby(["source", "variant"]))
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(13, 5))

    # Left: per-gateway packet counts, sorted high->low (the funnel vs flat picture).
    for (source, variant), g in groups:
        counts = np.sort(g.groupby("gateway_gid").size().values)[::-1]
        ax1.plot(range(len(counts)), counts, marker="o", ms=3,
                 label="%s/%s (n=%d)" % (source.split("/")[-1], variant, len(counts)))
    ax1.set_xlabel("Gateway rank (busiest -> idlest)")
    ax1.set_ylabel("Packets exited via gateway")
    ax1.set_title("Per-gateway egress load (sorted)")
    ax1.legend(fontsize=8)

    # Right: egress packets over time per variant (temporal imbalance / bursts).
    tmin, tmax = df["timestamp_ns"].min(), df["timestamp_ns"].max()
    edges = np.linspace(tmin, tmax, args.bins + 1)
    centers = 0.5 * (edges[:-1] + edges[1:])
    for (source, variant), g in groups:
        hist, _ = np.histogram(g["timestamp_ns"], bins=edges)
        ax2.plot(centers, hist, label="%s/%s" % (source.split("/")[-1], variant))
    ax2.set_xlabel("Simulation time (ns)")
    ax2.set_ylabel("Packets exiting to fat tree")
    ax2.set_title("Egress over time")
    ax2.legend(fontsize=8)

    fig.tight_layout()
    fig.savefig(args.out + ".png", dpi=120)
    print("\nWrote %s.png and %s_summary.csv" % (args.out, args.out))


if __name__ == "__main__":
    main()
