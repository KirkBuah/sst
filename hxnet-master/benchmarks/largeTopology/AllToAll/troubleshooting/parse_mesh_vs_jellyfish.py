"""
Parse + compare AllToAll throughput for the standalone single-board runs produced
by launch_local_topos.py.

Reads ./output/<topo>_<nodes>/<msg_size>, where <topo> is "mesh" or "jellyfish".
For every node count N present as BOTH mesh_<N> and jellyfish_<N>, prints a
per-message-size comparison table (mesh Gb/s, jellyfish Gb/s, jelly/mesh ratio)
and saves plots/mesh_vs_jellyfish_<N>nodes.{png,pdf}.

Throughput is computed exactly as in ../parseAndPlotAllToAll.py:
    per run:  messageSize * (numNodes - 1) / max_latency_ns   (bottleneck node)
    then * 8 -> Gb/s

Run:  uv run python parse_mesh_vs_jellyfish.py
"""

import os
import re
import warnings
from collections import defaultdict
from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # file-only, no interactive display
import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns

warnings.filterwarnings("ignore")

OUTPUT_FOLDER = "output"
SAVE_FOLDER = "plots"


def bytes_to_label(b):
    if b >= 1024 * 1024:
        return "{}MB".format(b // (1024 * 1024))
    if b >= 1024:
        return "{}KB".format(b // 1024)
    return "{}B".format(b)


def parse_run(path):
    """Return bottleneck throughput (Gb/s) for one output file, or None."""
    size_all_to_all = -1
    num_nodes = 1
    min_bw = float("inf")
    with open(path) as fp:
        for line in fp:
            m = re.search(r"EMBER: numNodes=(\d+)", line)
            if m:
                num_nodes = int(m.group(1))
            m = re.search(r"EMBER: Motif='AllPingPong messageSize=(\d+)'", line)
            if m:
                size_all_to_all = int(m.group(1)) * (num_nodes - 1)
            m = re.search(r"STATS (\d+) (\d+) EMBER (\d+) (\d+) (\d+) (\d+)", line)
            if m and size_all_to_all > 0:
                tmp_time = int(m.group(5))
                if tmp_time > 0 and size_all_to_all / tmp_time < min_bw:
                    min_bw = size_all_to_all / tmp_time
    if min_bw == float("inf"):
        return None
    return min_bw * 8  # bytes/ns -> *8 -> Gb/s


def collect():
    """Return {nodes: {fabric: {msg_size: gbps}}} for fabric in {mesh, jellyfish}."""
    results = defaultdict(lambda: defaultdict(dict))
    if not os.path.isdir(OUTPUT_FOLDER):
        return results
    for entry in sorted(os.listdir(OUTPUT_FOLDER)):
        d = os.path.join(OUTPUT_FOLDER, entry)
        if not os.path.isdir(d):
            continue
        m = re.match(r"(mesh|jellyfish)_(\d+)$", entry)
        if not m:
            continue
        fabric, nodes = m.group(1), int(m.group(2))
        for fname in os.listdir(d):
            try:
                msg_size = int(os.path.splitext(fname)[0])
            except ValueError:
                continue
            gbps = parse_run(os.path.join(d, fname))
            if gbps is not None:
                results[nodes][fabric][msg_size] = gbps
    return results


def print_table(nodes, mesh, jelly):
    print("\n=== AllToAll throughput: mesh vs jellyfish local board (%d nodes) ===" % nodes)
    sizes = sorted(set(mesh) | set(jelly))
    header = "{:>12} {:>16} {:>16} {:>14}".format(
        "msg size", "mesh (Gb/s)", "jellyfish (Gb/s)", "jelly/mesh")
    print(header)
    print("-" * len(header))
    for s in sizes:
        m, j = mesh.get(s), jelly.get(s)
        ratio = "{:.3f}".format(j / m) if (m and j) else "-"
        print("{:>12} {:>16} {:>16} {:>14}".format(
            bytes_to_label(s),
            "{:.3f}".format(m) if m is not None else "-",
            "{:.3f}".format(j) if j is not None else "-",
            ratio))


def plot(nodes, mesh, jelly):
    sns.set_theme(style="darkgrid")
    fig, ax = plt.subplots()
    for label, data in (("mesh", mesh), ("jellyfish", jelly)):
        if not data:
            continue
        xs = sorted(data)
        sns.lineplot(x=xs, y=[data[x] for x in xs], label=label, marker="o", ax=ax)
    ax.set_xscale("log", base=2)
    ax.set_xlabel("Message size (bytes)")
    ax.set_ylabel("Throughput (Gb/s)")
    ax.set_title("AllToAll local board: mesh vs jellyfish (%d nodes)" % nodes)
    ax.legend()
    fig.tight_layout()
    Path(SAVE_FOLDER).mkdir(parents=True, exist_ok=True)
    base = os.path.join(SAVE_FOLDER, "mesh_vs_jellyfish_%dnodes" % nodes)
    fig.savefig(base + ".png")
    fig.savefig(base + ".pdf")
    plt.close(fig)
    print("Saved plot: %s.png / .pdf" % base)


def main():
    results = collect()
    if not results:
        print("No parsable output under %s/. Run launch_local_topos.py first." % OUTPUT_FOLDER)
        return
    any_pair = False
    for nodes in sorted(results):
        mesh = results[nodes].get("mesh", {})
        jelly = results[nodes].get("jellyfish", {})
        if not mesh and not jelly:
            continue
        print_table(nodes, mesh, jelly)
        plot(nodes, mesh, jelly)
        if mesh and jelly:
            any_pair = True
    if not any_pair:
        print("\nNote: no node count had BOTH mesh and jellyfish results to compare.")


if __name__ == "__main__":
    main()
