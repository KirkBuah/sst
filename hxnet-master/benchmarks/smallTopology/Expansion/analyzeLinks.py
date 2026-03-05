"""
Theoretical link analysis: Jellyfish vs 2D Mesh expansion efficiency.

Computes and plots:
  - Intra-board links per node as board size grows
  - Fat-tree gateway links per board
  - "Expansion cost": new links needed to add one more switch to the board

Run: python3 analyzeLinks.py
Produces: expansion_link_analysis.png

Key formulas (board of size a×a, N = a² nodes):

  2D Mesh:
    intra_links  = 2·a·(a-1)      (horizontal + vertical, no wrap)
    ft_links     = 4·a             (all border nodes, 2 per side × 2 directions)
    expansion    ≈ 2·(a+1)         (need a new row or column to keep grid structure)

  Jellyfish (default, border gateways, same port budget as mesh):
    ft_links     = 4·a             (same as mesh)
    intra_links  = total_ports - ft_links - N (N = NIC ports)
                 where total_ports = 5·N (each switch has 5 ports)
    expansion    = r               (rewire r existing links; r = inter-switch degree
                                    of new switch.  For border mesh default: r ≈ 3)

  Jellyfish (ft_nodes=1, only 1 row-FT gateway + 1 col-FT gateway per board):
    ft_links     = 2               (just 2 gateway nodes)
    intra_links  = total_ports - ft_links - N
    expansion    = 2               (Jellyfish paper: add switch, rewire 2 links)
"""

import math
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import numpy as np

# ── Board sizes to study ─────────────────────────────────────────────────────
BOARD_SIZES = [2, 3, 4, 5, 6, 8, 10]   # a in a×a

PORTS_PER_SWITCH = 5    # N(0), E(1), S(2), W(3), NIC(4)
NIC_PORTS = 1


def analyze(a):
    N = a * a

    # ── 2D Mesh ──────────────────────────────────────────────────────────────
    mesh_intra   = 2 * a * (a - 1)
    mesh_ft      = 4 * a
    mesh_total   = mesh_intra + mesh_ft  # intra + ft (NIC links excluded)
    mesh_intra_per_node = mesh_intra / N
    mesh_ft_per_node    = mesh_ft / N
    # Adding a new switch to a 2D mesh means adding a full new row/column:
    # cheapest is to insert at the edge (a new border row), requiring a new
    # links into the existing grid + 1 FT gateway connection + possible reuse.
    # Lower bound: a new row of a switches each needing 1 N-S link into grid = a
    # links, plus fat tree connections for the whole row = a more links.
    mesh_expansion = 2 * a   # roughly: a grid links + a ft links per new row/node

    # ── Jellyfish (default, same border gateways as mesh) ────────────────────
    # Same port budget as mesh: every switch has 5 ports.
    # ft_links identical; remaining ports used for Jellyfish (random).
    jf_default_ft      = 4 * a   # same as mesh
    jf_default_intra   = (PORTS_PER_SWITCH - NIC_PORTS) * N // 2 - jf_default_ft
    # Actual intra = (total inter-router ports) / 2
    # total inter-router ports per board = (5-1)*N = 4N, minus ft_links reserved
    jf_default_intra   = (4 * N - jf_default_ft) // 2
    jf_default_intra_per_node = jf_default_intra / N
    jf_default_ft_per_node    = jf_default_ft / N
    # Expansion: add 1 switch with r free ports → rewire r/2 existing links
    # For border default, a corner switch has 2 free inter-router ports → 1 rewire
    # We use r=2 as the Jellyfish paper's typical case
    jf_default_expansion = 2   # rewire 2 existing intra-board links

    # ── Jellyfish (ft_nodes=1: 1 row-FT gateway + 1 col-FT gateway) ─────────
    # Only 2 nodes reserve 1 port each for FT (port 3 and port 0 respectively)
    jf_ft1_ft    = 2
    jf_ft1_intra = (4 * N - jf_ft1_ft) // 2
    jf_ft1_intra_per_node = jf_ft1_intra / N
    jf_ft1_ft_per_node    = jf_ft1_ft / N
    jf_ft1_expansion = 2   # same Jellyfish rewiring rule

    return {
        'a': a, 'N': N,
        'mesh_intra': mesh_intra,  'mesh_ft': mesh_ft,
        'mesh_intra_per_node': mesh_intra_per_node,
        'mesh_ft_per_node': mesh_ft_per_node,
        'mesh_expansion': mesh_expansion,
        'jf_default_intra': jf_default_intra,  'jf_default_ft': jf_default_ft,
        'jf_default_intra_per_node': jf_default_intra_per_node,
        'jf_default_ft_per_node': jf_default_ft_per_node,
        'jf_default_expansion': jf_default_expansion,
        'jf_ft1_intra': jf_ft1_intra,  'jf_ft1_ft': jf_ft1_ft,
        'jf_ft1_intra_per_node': jf_ft1_intra_per_node,
        'jf_ft1_ft_per_node': jf_ft1_ft_per_node,
        'jf_ft1_expansion': jf_ft1_expansion,
    }


def main():
    results = [analyze(a) for a in BOARD_SIZES]
    nodes   = [r['N'] for r in results]

    # ── Print table ──────────────────────────────────────────────────────────
    print(f"{'Board':>6} {'Nodes':>6} | "
          f"{'Mesh':>18} | "
          f"{'JF default':>18} | "
          f"{'JF ft_nodes=1':>18}")
    print(f"{'a×a':>6} {'N':>6} | "
          f"{'intra':>6} {'ft':>5} {'exp':>5} | "
          f"{'intra':>6} {'ft':>5} {'exp':>5} | "
          f"{'intra':>6} {'ft':>5} {'exp':>5}")
    print("-" * 78)
    for r in results:
        print(f"{r['a']:>4}x{r['a']:<2} {r['N']:>6} | "
              f"{r['mesh_intra']:>6} {r['mesh_ft']:>5} {r['mesh_expansion']:>5} | "
              f"{r['jf_default_intra']:>6} {r['jf_default_ft']:>5} {r['jf_default_expansion']:>5} | "
              f"{r['jf_ft1_intra']:>6} {r['jf_ft1_ft']:>5} {r['jf_ft1_expansion']:>5}")

    # ── Plot ─────────────────────────────────────────────────────────────────
    fig, axes = plt.subplots(1, 3, figsize=(15, 5))
    fig.suptitle("Theoretical Link Analysis: 2D Mesh vs Jellyfish", fontsize=13, fontweight='bold')

    colors = {'mesh': '#e55a0a', 'jf_def': '#2196F3', 'jf_ft1': '#4CAF50'}
    ms = 7  # marker size

    # ── Panel 1: Intra-board links per node ──────────────────────────────────
    ax = axes[0]
    ax.plot(nodes, [r['mesh_intra_per_node'] for r in results],
            'o-', color=colors['mesh'], ms=ms, label='Mesh')
    ax.plot(nodes, [r['jf_default_intra_per_node'] for r in results],
            's--', color=colors['jf_def'], ms=ms, label='Jellyfish (border gateways)')
    ax.plot(nodes, [r['jf_ft1_intra_per_node'] for r in results],
            '^:', color=colors['jf_ft1'], ms=ms, label='Jellyfish (ft_nodes=1)')
    ax.set_xlabel("Board size (nodes)")
    ax.set_ylabel("Intra-board links per node")
    ax.set_title("Intra-board Connectivity")
    ax.legend(fontsize=8)
    ax.grid(True, alpha=0.3)
    ax.xaxis.set_major_formatter(mticker.ScalarFormatter())

    # ── Panel 2: Fat-tree gateway links per node ──────────────────────────────
    ax = axes[1]
    ax.plot(nodes, [r['mesh_ft_per_node'] for r in results],
            'o-', color=colors['mesh'], ms=ms, label='Mesh')
    ax.plot(nodes, [r['jf_default_ft_per_node'] for r in results],
            's--', color=colors['jf_def'], ms=ms, label='Jellyfish (border gateways)')
    ax.plot(nodes, [r['jf_ft1_ft_per_node'] for r in results],
            '^:', color=colors['jf_ft1'], ms=ms, label='Jellyfish (ft_nodes=1)')
    ax.set_xlabel("Board size (nodes)")
    ax.set_ylabel("Fat-tree gateway links per node")
    ax.set_title("Fat-tree Uplink Density")
    ax.legend(fontsize=8)
    ax.grid(True, alpha=0.3)

    # ── Panel 3: Expansion cost ───────────────────────────────────────────────
    ax = axes[2]
    mesh_exp  = [r['mesh_expansion'] for r in results]
    jf_def_exp = [r['jf_default_expansion'] for r in results]
    jf_ft1_exp = [r['jf_ft1_expansion'] for r in results]

    x = np.arange(len(BOARD_SIZES))
    w = 0.25
    ax.bar(x - w,  mesh_exp,   w, color=colors['mesh'],    label='Mesh')
    ax.bar(x,      jf_def_exp, w, color=colors['jf_def'],  label='Jellyfish (border gateways)')
    ax.bar(x + w,  jf_ft1_exp, w, color=colors['jf_ft1'],  label='Jellyfish (ft_nodes=1)')
    ax.set_xticks(x)
    ax.set_xticklabels(["%d×%d\n(%d)" % (a, a, a*a) for a in BOARD_SIZES], fontsize=8)
    ax.set_xlabel("Board configuration (nodes)")
    ax.set_ylabel("Links rewired / added to expand by 1 switch")
    ax.set_title("Expansion Cost per New Switch")
    ax.legend(fontsize=8)
    ax.grid(True, alpha=0.3, axis='y')

    plt.tight_layout()
    out = "expansion_link_analysis.png"
    plt.savefig(out, dpi=150, bbox_inches='tight')
    print(f"\nPlot saved to {out}")


if __name__ == "__main__":
    main()
