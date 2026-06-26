"""
Generate and visualize a textbook Jellyfish topology: a random d-regular graph.

Unlike the SST-elaborated fabric (where gateway/fat-tree links make node degrees
vary), a Jellyfish is a uniform-random regular graph -- every switch uses the
same number of ports. This renders an example 8x8 (64-node) Jellyfish where each
node has exactly 4 ports, laid out on the board grid so the random links cross.

Usage:
    uv run python jellyfish_regular.py                      # 64 nodes, degree 4
    uv run python jellyfish_regular.py --nodes 64 --degree 4 --seed 1
"""

import os
import random
from argparse import ArgumentParser

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import networkx as nx  # noqa: E402

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
OUT_DIR = os.path.join(SCRIPT_DIR, "output", "viz")

NODE_COLOR = (8 / 255, 41 / 255, 69 / 255)  # steel blue, same as the full viz
EDGE_COLOR = "#1f77b4"


def grid_dims(n):
    """Nearest near-square grid (rows, cols) that holds n nodes; cols >= rows."""
    cols = int(round(n**0.5))
    while cols > 1 and n % cols:
        cols -= 1
    return n // cols, cols


def main():
    ap = ArgumentParser(description="Visualize a random d-regular Jellyfish topology")
    ap.add_argument("--nodes", type=int, default=64)
    ap.add_argument("--degree", type=int, default=4, help="ports per node")
    ap.add_argument(
        "--seed", type=int, default=0, help="RNG seed (reproducible wiring)"
    )
    ap.add_argument(
        "--jitter",
        type=float,
        default=0.18,
        help="random per-node offset (fraction of grid spacing) so links don't overlap",
    )
    ap.add_argument("--node_size", type=float, default=45.0)
    ap.add_argument("--out", default=None, help="output PNG path")
    args = ap.parse_args()

    if (args.nodes * args.degree) % 2:
        ap.error("nodes * degree must be even for a regular graph")

    # Random d-regular graph: every node has exactly `degree` ports.
    G = nx.random_regular_graph(args.degree, args.nodes, seed=args.seed)

    rows, cols = grid_dims(args.nodes)
    # Jitter each node off its grid slot in a random direction so that links
    # which would otherwise run collinearly (same row/col) no longer overlap.
    jrng = random.Random(args.seed)
    pos = {
        i: (
            i % cols + jrng.uniform(-args.jitter, args.jitter),
            -(i // cols) + jrng.uniform(-args.jitter, args.jitter),
        )
        for i in G.nodes
    }

    fig, ax = plt.subplots(figsize=(9, 9))
    for u, v in G.edges:
        (x0, y0), (x1, y1) = pos[u], pos[v]
        ax.plot([x0, x1], [y0, y1], color=EDGE_COLOR, lw=0.6, alpha=0.6, zorder=1)
    xs = [pos[i][0] for i in G.nodes]
    ys = [pos[i][1] for i in G.nodes]
    ax.scatter(xs, ys, c=[NODE_COLOR], s=args.node_size, zorder=2, edgecolors="none")

    degrees = {d for _, d in G.degree}
    ax.set_title(
        "Jellyfish  (%dx%d, %d nodes, degree %d%s)"
        % (
            rows,
            cols,
            args.nodes,
            args.degree,
            "" if degrees == {args.degree} else " (irregular!)",
        )
    )
    ax.set_aspect("equal")
    ax.axis("off")
    fig.tight_layout()

    out = args.out or os.path.join(
        OUT_DIR, "jellyfish_regular_%dx%d.png" % (rows, cols)
    )
    os.makedirs(os.path.dirname(out), exist_ok=True)
    fig.savefig(out, dpi=130)
    plt.close(fig)
    print(
        "nodes=%d  edges=%d  degrees=%s"
        % (G.number_of_nodes(), G.number_of_edges(), sorted(degrees))
    )
    print("-> %s" % out)


if __name__ == "__main__":
    main()
