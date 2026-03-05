"""
plotExpansion.py  —  Post-processing and visualisation for the expansion study.

Reads simulation output from the AllToAll and RandomPermutation benchmark
directories and produces three plots:

  Plot 1 — AllToAll throughput vs node count
      Topologies: mesh, jellyfish (default border gateways), jellyfish ft_nodes=1
      X-axis: total node count  |  Y-axis: Gb/s at the largest message size

  Plot 2 — AllToAll + RandomPerm throughput vs ft_nodes
      Fixed: board_shape=2x2, global_shape=2x2 (16 nodes)
      X-axis: ft_nodes value (0, 1, 2)  |  Y-axis: Gb/s

  Plot 3 — Theoretical link counts (inline from analyzeLinks.py logic)
      X-axis: board size a  |  Y-axis: links per node

Output: expansion_plots.png  (3-row figure)

Run from any directory; paths are resolved relative to this script.
"""

import os
import re
import math
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import numpy as np
from pathlib import Path

# ── Directory layout ─────────────────────────────────────────────────────────
SCRIPT_DIR   = Path(os.path.dirname(os.path.abspath(__file__)))
ALLTOALL_OUT = SCRIPT_DIR / "../AllToAll/output"
RANDPERM_OUT = SCRIPT_DIR / "../RandomPermutation/output"


# ── Parsing helpers ───────────────────────────────────────────────────────────

def parse_alltoall_file(filepath):
    """Return (msg_size_bytes, throughput_gbps) or None if unparseable."""
    num_nodes = 1
    size_ata   = None
    min_bw     = None

    with open(filepath) as f:
        lines = f.readlines()

    for line in lines:
        m = re.search(r"EMBER: numNodes=(\d+)", line)
        if m:
            num_nodes = int(m.group(1))

        m = re.search(r"EMBER: Motif='AllPingPong messageSize=(\d+)'", line)
        if m:
            size_ata = int(m.group(1)) * (num_nodes - 1)

        m = re.search(r"STATS \d+ \d+ EMBER \d+ (\d+) \d+ \d+", line)
        if m and size_ata is not None:
            t = int(m.group(1))
            if t > 0:
                bw = size_ata / t          # bytes / ns = GB/s
                if min_bw is None or bw < min_bw:
                    min_bw = bw

    if min_bw is None or size_ata is None:
        return None
    return size_ata, min_bw * 8   # Gb/s


def parse_randperm_file(filepath):
    """Return throughput_gbps or None."""
    bws = []
    with open(filepath) as f:
        for line in f:
            m = re.search(r"STATS \d+ \d+ EMBER \d+ (\d+) \d+ (\d+)", line)
            if m:
                t   = int(m.group(1))
                sz  = int(m.group(2))
                if t > 0:
                    bws.append(sz / t * 8)  # Gb/s
    return sum(bws) / len(bws) if bws else None


def read_output_dir(out_dir, parse_fn):
    """
    Walk out_dir/<topo_name>/<size_file> and return
      { topo_name: [(x, y), ...] }   sorted by x.
    """
    results = {}
    out_path = Path(out_dir)
    if not out_path.exists():
        return results

    for topo_dir in sorted(out_path.iterdir()):
        if not topo_dir.is_dir():
            continue
        name   = topo_dir.name
        points = []
        for f in sorted(topo_dir.iterdir(), key=lambda p: int(p.name)):
            parsed = parse_fn(f)
            if parsed is not None:
                if isinstance(parsed, tuple):
                    points.append(parsed)          # (x, y)
                else:
                    points.append((int(f.name), parsed))
        if points:
            results[name] = sorted(points, key=lambda p: p[0])
    return results


# ── Topo-name → display label ─────────────────────────────────────────────────

def label_of(name):
    """Human-readable label from output directory name."""
    if "_jellyfish_ft" in name:
        ft = re.search(r"_ft(\d+)", name)
        n  = ft.group(1) if ft else "?"
        return "Jellyfish ft_nodes=%s" % n
    if "_jellyfish" in name:
        return "Jellyfish (border gateways)"
    # plain mesh
    nodes = re.search(r"hx\d+_(\d+)$", name)
    n = nodes.group(1) if nodes else name
    return "Mesh (%s nodes)" % n


def node_count_of(name):
    """Extract total node count from topo_name like hx2_16 → 16."""
    m = re.search(r"hx\d+_(\d+)", name)
    return int(m.group(1)) if m else 0


def ft_nodes_of(name):
    """Extract ft_nodes value from topo_name (0 if not present)."""
    m = re.search(r"_ft(\d+)", name)
    return int(m.group(1)) if m else 0


# ── Colour palette ────────────────────────────────────────────────────────────
C_MESH    = '#e55a0a'
C_JF_DEF  = '#2196F3'
C_JF_FT1  = '#4CAF50'
C_JF_FT2  = '#9C27B0'


def color_of(name):
    if "_jellyfish_ft" in name:
        n = ft_nodes_of(name)
        return C_JF_FT1 if n == 1 else C_JF_FT2
    if "_jellyfish" in name:
        return C_JF_DEF
    return C_MESH


# ── Theoretical link count (mirrors analyzeLinks.py) ─────────────────────────

BOARD_SIZES      = [2, 3, 4, 5, 6, 8, 10]
PORTS_PER_SWITCH = 5
NIC_PORTS        = 1


def theory_data():
    rows = []
    for a in BOARD_SIZES:
        N = a * a
        mesh_intra = 2 * a * (a - 1)
        mesh_ft    = 4 * a
        jf_def_ft  = 4 * a
        jf_def_intra = (4 * N - jf_def_ft) // 2
        jf_ft1_ft    = 2
        jf_ft1_intra = (4 * N - jf_ft1_ft) // 2
        rows.append({
            'a': a, 'N': N,
            'mesh_intra_pn':   mesh_intra / N,
            'jf_def_intra_pn': jf_def_intra / N,
            'jf_ft1_intra_pn': jf_ft1_intra / N,
            'mesh_ft_pn':   mesh_ft / N,
            'jf_def_ft_pn': jf_def_ft / N,
            'jf_ft1_ft_pn': jf_ft1_ft / N,
            'mesh_exp':   2 * a,
            'jf_def_exp': 2,
            'jf_ft1_exp': 2,
        })
    return rows


# ── Plot 1: AllToAll throughput vs node count ─────────────────────────────────

def plot_scaling(ax, alltoall_data):
    """
    For each topology name in alltoall_data, take the throughput at the
    largest message size and plot it vs node count.
    """
    # Group by topology variant across different node counts
    # Key: variant string ('mesh', 'jellyfish', 'jellyfish_ft1', ...)
    def variant(name):
        if "_jellyfish_ft" in name:
            return "jellyfish_ft%d" % ft_nodes_of(name)
        if "_jellyfish" in name:
            return "jellyfish"
        return "mesh"

    grouped = {}   # variant → [(node_count, max_bw)]
    for name, points in alltoall_data.items():
        if not points:
            continue
        # largest msg size = last point after sorting by x
        _, bw = max(points, key=lambda p: p[0])
        v = variant(name)
        nc = node_count_of(name)
        grouped.setdefault(v, []).append((nc, bw))

    style = {
        'mesh':         dict(color=C_MESH,   marker='o', ls='-',  label='Mesh'),
        'jellyfish':    dict(color=C_JF_DEF,  marker='s', ls='--', label='Jellyfish (border gateways)'),
        'jellyfish_ft1': dict(color=C_JF_FT1, marker='^', ls=':',  label='Jellyfish ft_nodes=1'),
        'jellyfish_ft2': dict(color=C_JF_FT2, marker='D', ls='-.',  label='Jellyfish ft_nodes=2'),
    }

    for var, pts in sorted(grouped.items()):
        pts.sort()
        xs = [p[0] for p in pts]
        ys = [p[1] for p in pts]
        kw = style.get(var, dict(color='grey', marker='x', ls='-', label=var))
        ax.plot(xs, ys, ms=7, linewidth=2, **kw)

    ax.set_xlabel("Node count")
    ax.set_ylabel("Throughput (Gb/s)")
    ax.set_title("AllToAll — scaling (largest msg)")
    ax.legend(fontsize=8)
    ax.grid(True, alpha=0.3)


# ── Plot 2: throughput vs ft_nodes at fixed 16-node topology ─────────────────

def plot_ft_sweep(ax, alltoall_data, randperm_data):
    """
    Extract results for board=2x2, global=2x2 (16 nodes) jellyfish configs.
    Plot throughput (at max msg size) vs ft_nodes.
    """
    def is_16node_jf(name):
        return node_count_of(name) == 16 and "_jellyfish" in name

    def max_bw(points):
        if not points:
            return None
        _, bw = max(points, key=lambda p: p[0])
        return bw

    ata_pts  = {ft_nodes_of(n): max_bw(p)
                for n, p in alltoall_data.items() if is_16node_jf(n)}
    rp_pts   = {}
    for n, p in randperm_data.items():
        if is_16node_jf(n):
            bw = sum(y for _, y in p) / len(p) if p else None
            rp_pts[ft_nodes_of(n)] = bw

    ft_vals = sorted(set(list(ata_pts.keys()) + list(rp_pts.keys())))

    if not ft_vals:
        ax.text(0.5, 0.5, "No data", transform=ax.transAxes, ha='center')
        ax.set_title("FT Gateway Tradeoff (no data yet)")
        return

    if ata_pts:
        xs = ft_vals
        ys = [ata_pts.get(f) for f in xs]
        mask = [y is not None for y in ys]
        ax.plot([xs[i] for i in range(len(xs)) if mask[i]],
                [ys[i] for i in range(len(ys)) if mask[i]],
                'o-', color=C_JF_DEF, ms=7, linewidth=2, label='AllToAll')

    if rp_pts:
        xs = ft_vals
        ys = [rp_pts.get(f) for f in xs]
        mask = [y is not None for y in ys]
        ax.plot([xs[i] for i in range(len(xs)) if mask[i]],
                [ys[i] for i in range(len(ys)) if mask[i]],
                's--', color=C_MESH, ms=7, linewidth=2, label='RandomPerm')

    ax.set_xlabel("ft_nodes (gateways per FT direction)")
    ax.set_ylabel("Throughput (Gb/s)")
    ax.set_title("Jellyfish FT Gateway Tradeoff\n(board=2×2, global=2×2, 16 nodes)")
    ax.xaxis.set_major_locator(mticker.MaxNLocator(integer=True))
    ax.legend(fontsize=8)
    ax.grid(True, alpha=0.3)


# ── Plot 3: theoretical link counts ─────────────────────────────────────────

def plot_theory(axes, rows):
    nodes = [r['N'] for r in rows]
    ms = 7

    ax = axes[0]
    ax.plot(nodes, [r['mesh_intra_pn']   for r in rows], 'o-',  color=C_MESH,   ms=ms, label='Mesh')
    ax.plot(nodes, [r['jf_def_intra_pn'] for r in rows], 's--', color=C_JF_DEF, ms=ms, label='Jellyfish (border)')
    ax.plot(nodes, [r['jf_ft1_intra_pn'] for r in rows], '^:',  color=C_JF_FT1, ms=ms, label='Jellyfish ft_nodes=1')
    ax.set_xlabel("Board size (nodes)")
    ax.set_ylabel("Intra-board links / node")
    ax.set_title("Intra-board Connectivity")
    ax.legend(fontsize=8)
    ax.grid(True, alpha=0.3)

    ax = axes[1]
    ax.plot(nodes, [r['mesh_ft_pn']   for r in rows], 'o-',  color=C_MESH,   ms=ms, label='Mesh')
    ax.plot(nodes, [r['jf_def_ft_pn'] for r in rows], 's--', color=C_JF_DEF, ms=ms, label='Jellyfish (border)')
    ax.plot(nodes, [r['jf_ft1_ft_pn'] for r in rows], '^:',  color=C_JF_FT1, ms=ms, label='Jellyfish ft_nodes=1')
    ax.set_xlabel("Board size (nodes)")
    ax.set_ylabel("FT gateway links / node")
    ax.set_title("Fat-tree Uplink Density")
    ax.legend(fontsize=8)
    ax.grid(True, alpha=0.3)

    ax = axes[2]
    x  = np.arange(len(BOARD_SIZES))
    w  = 0.25
    ax.bar(x - w, [r['mesh_exp']    for r in rows], w, color=C_MESH,   label='Mesh')
    ax.bar(x,     [r['jf_def_exp']  for r in rows], w, color=C_JF_DEF, label='Jellyfish (border)')
    ax.bar(x + w, [r['jf_ft1_exp']  for r in rows], w, color=C_JF_FT1, label='Jellyfish ft_nodes=1')
    ax.set_xticks(x)
    ax.set_xticklabels(["%d×%d\n(%d)" % (a, a, a*a) for a in BOARD_SIZES], fontsize=8)
    ax.set_xlabel("Board config (nodes)")
    ax.set_ylabel("Links rewired per new switch")
    ax.set_title("Expansion Cost")
    ax.legend(fontsize=8)
    ax.grid(True, alpha=0.3, axis='y')


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    alltoall_data = read_output_dir(ALLTOALL_OUT, parse_alltoall_file)
    randperm_data = read_output_dir(RANDPERM_OUT, parse_randperm_file)

    if not alltoall_data:
        print("No AllToAll output found in %s" % ALLTOALL_OUT)
        print("Run launchExpansionStudy.py first, then re-run this script.")
    if not randperm_data:
        print("No RandomPerm output found in %s" % RANDPERM_OUT)

    rows = theory_data()

    fig = plt.figure(figsize=(16, 14))
    fig.suptitle("Jellyfish Expansion Study: Mesh vs Jellyfish", fontsize=14, fontweight='bold')

    # Row 1: simulation scaling (left) + ft_nodes sweep (right)
    ax1 = fig.add_subplot(3, 2, 1)
    ax2 = fig.add_subplot(3, 2, 2)
    # Row 2+3: theoretical (3 panels spanning bottom two rows)
    ax3 = fig.add_subplot(3, 3, 4)
    ax4 = fig.add_subplot(3, 3, 5)
    ax5 = fig.add_subplot(3, 3, 6)

    plot_scaling(ax1, alltoall_data)
    plot_ft_sweep(ax2, alltoall_data, randperm_data)
    plot_theory([ax3, ax4, ax5], rows)

    plt.tight_layout()
    out = SCRIPT_DIR / "expansion_plots.png"
    plt.savefig(out, dpi=150, bbox_inches='tight')
    print("Saved to %s" % out)


if __name__ == "__main__":
    main()
