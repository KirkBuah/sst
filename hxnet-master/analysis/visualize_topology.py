"""
Export the (mesh or Jellyfish) HammingMesh switch fabric to GraphML/GEXF with a
structure-aware layout and colors baked in, for interactive exploration in Gephi
or Cytoscape.

Graph source: SST's elaborated graph (`sst --run-mode=init --output-json`), so it
is exactly what SST builds. Scope: switch fabric only (board switches + fat-tree
switches); the compute NICs are leaves and omitted by default.

Layout: boards are placed in the global grid, each board is its own grid of
switches -> the mesh shows clean short grid edges; the Jellyfish shows the same
node grid but with random intra-board links crossing. Gephi/Cytoscape read the
node attributes x,y,size,r,g,b as visual properties, so the file opens already
laid out and colored.

Usage:
    uv run python visualize_topology.py                      # both, board 8x8 / global 4x4
    uv run python visualize_topology.py --topo jellyfish
    uv run python visualize_topology.py --board_shape 4x4 --global_shape 2x2 --preview
"""

import os
import colorsys
import shutil
import pathlib
from argparse import ArgumentParser

import networkx as nx

from check_connectivity import _canon
from count_links import dims, write_motif, dump, _routers_and_params

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
OUT_DIR = os.path.join(SCRIPT_DIR, "output", "viz")
COMMON = '--param="nic:module=merlin.reorderlinkcontrol" --hostsPerRtr=1 '


def board_palette(n_boards):
    """Distinct RGB (0-255) per board id via evenly spaced hues."""
    pal = {}
    for b in range(n_boards):
        h = (b * 0.61803398875) % 1.0           # golden-ratio hue spacing
        s, v = 0.55, 0.92
        r, g, bl = colorsys.hsv_to_rgb(h, s, v)
        pal[b] = (int(r * 255), int(g * 255), int(bl * 255))
    return pal


def model_options(board, glob, jelly, ft_nodes, motif):
    s = COMMON + ("--topo=hx --boardShape=%s --globalShape=%s --fatTreeShape=1:1,64 "
                  % (board, glob))
    if jelly:
        s += "--jellyfish "
        if ft_nodes > 0:
            s += "--ftNodes=%d " % ft_nodes
    return s + "--loadFile=%s" % motif


def build_graph(d, board, glob, gap, include_nics, scale, node_size):
    R, C = dims(board)
    spb = R * C
    GC = dims(glob)[1]
    comps, routers, P = _routers_and_params(d)

    board_of, local_of, ftset = {}, {}, set()
    for n in routers:
        p = P(n)
        if str(p.get("is_board_switch")).lower() == "true":
            gid = int(p["global_switch_id"])
            board_of[n] = gid // spb
            local_of[n] = gid % spb
        else:
            ftset.add(n)

    palette = board_palette(GC * dims(glob)[0])

    G = nx.Graph()

    def board_pos(n):
        bid, lid = board_of[n], local_of[n]
        br, bc = bid // GC, bid % GC
        lr, lc = lid // C, lid % C
        # Spread positions far wider than the node size so nodes don't overlap
        # (Gephi draws node radius in the same coordinate space as x/y).
        x = (bc * (C + gap) + lc) * scale
        y = (br * (R + gap) + lr) * scale
        return float(x), float(y)

    # board-switch nodes
    for n in board_of:
        bid = board_of[n]
        x, y = board_pos(n)
        r, g, b = palette[bid]
        G.add_node(n, role="board", board_id=bid, local_id=local_of[n],
                   x=x, y=-y, r=r, g=g, b=b, size=node_size, is_gateway=0, intra_degree=0)

    # edges (router<->router): classify + count gateways/degree
    ft_neighbors = {}   # ft switch -> list of (x,y) of connected board gateways
    for l in d["links"]:
        a, b = _canon(l["left"]), _canon(l["right"])
        if a not in routers or b not in routers:
            continue
        a_b, b_b = a in board_of, b in board_of
        if a_b and b_b and board_of[a] == board_of[b]:
            G.add_edge(a, b, link_type="intra_board")
            G.nodes[a]["intra_degree"] += 1
            G.nodes[b]["intra_degree"] += 1
        elif a_b and b in ftset:
            G.nodes[a]["is_gateway"] = 1
            ft_neighbors.setdefault(b, []).append(board_pos(a))
        elif b_b and a in ftset:
            G.nodes[b]["is_gateway"] = 1
            ft_neighbors.setdefault(a, []).append(board_pos(b))

    # fat-tree-switch nodes: place at centroid of connected gateways, nudged out
    for ftn in ftset:
        pts = ft_neighbors.get(ftn, [])
        if pts:
            cx = sum(p[0] for p in pts) / len(pts)
            cy = sum(p[1] for p in pts) / len(pts)
        else:
            cx = cy = 0.0
        G.add_node(ftn, role="fat_tree", board_id=-1, local_id=-1,
                   x=float(cx), y=float(-cy), r=20, g=20, b=20, size=node_size * 2.4,
                   is_gateway=0, intra_degree=0)
        for l in d["links"]:
            a, b = _canon(l["left"]), _canon(l["right"])
            if (a == ftn and b in board_of) or (b == ftn and a in board_of):
                G.add_edge(a, b, link_type="fat_tree")

    # enlarge gateways a bit
    for n in board_of:
        if G.nodes[n]["is_gateway"]:
            G.nodes[n]["size"] = node_size * 1.6

    if include_nics:
        for n, c in comps.items():
            if c.get("type") == "firefly.nic":
                G.add_node(n, role="nic", board_id=-1, local_id=-1,
                           x=0.0, y=0.0, r=200, g=200, b=200, size=node_size * 0.6,
                           is_gateway=0, intra_degree=0)
        for l in d["links"]:
            a, b = _canon(l["left"]), _canon(l["right"])
            if a in G and b in G and ({G.nodes[a].get("role"), G.nodes[b].get("role")} == {"nic", "board"}):
                G.add_edge(a, b, link_type="nic")

    return G


def add_gexf_viz(G):
    """Attach networkx 'viz' node attribute so GEXF carries position+color."""
    H = G.copy()
    for n, a in H.nodes(data=True):
        a["viz"] = {
            "position": {"x": float(a["x"]), "y": float(a["y"]), "z": 0.0},
            "color": {"r": int(a["r"]), "g": int(a["g"]), "b": int(a["b"])},
            "size": float(a["size"]),
        }
    return H


def preview_png(G, path, title):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(figsize=(11, 11))
    pos = {n: (a["x"], a["y"]) for n, a in G.nodes(data=True)}
    # edges by type
    for lt, col, lw, alpha in (("intra_board", "#1f77b4", 0.5, 0.6),
                               ("fat_tree", "#d62728", 0.4, 0.35)):
        segs = [(pos[u], pos[v]) for u, v, dd in G.edges(data=True) if dd.get("link_type") == lt]
        for (x0, y0), (x1, y1) in segs:
            ax.plot([x0, x1], [y0, y1], color=col, lw=lw, alpha=alpha, zorder=1)
    # nodes
    bx = [a["x"] for n, a in G.nodes(data=True) if a["role"] == "board"]
    by = [a["y"] for n, a in G.nodes(data=True) if a["role"] == "board"]
    bc = [(a["r"] / 255, a["g"] / 255, a["b"] / 255) for n, a in G.nodes(data=True) if a["role"] == "board"]
    bs = [a["size"] * 3 for n, a in G.nodes(data=True) if a["role"] == "board"]
    ax.scatter(bx, by, c=bc, s=bs, zorder=2, edgecolors="none")
    fx = [a["x"] for n, a in G.nodes(data=True) if a["role"] == "fat_tree"]
    fy = [a["y"] for n, a in G.nodes(data=True) if a["role"] == "fat_tree"]
    ax.scatter(fx, fy, c="black", s=60, marker="s", zorder=3, label="fat-tree switch")
    ax.set_title(title)
    ax.set_aspect("equal")
    ax.axis("off")
    ax.legend(loc="upper right")
    fig.tight_layout()
    fig.savefig(path, dpi=130)
    plt.close(fig)


def export_one(topo, jelly, args):
    board, glob = args.board_shape, args.global_shape
    n_nodes = dims(board)[0] * dims(board)[1] * dims(glob)[0] * dims(glob)[1]
    wd = os.path.join(OUT_DIR, "_work", topo)
    if os.path.isdir(wd):
        shutil.rmtree(wd)
    pathlib.Path(wd).mkdir(parents=True, exist_ok=True)
    motif = os.path.join(wd, "motif")
    write_motif(motif, "generateNidListHx(%sx%s)" % (board, glob))
    d = dump(model_options(board, glob, jelly, args.ft_nodes, motif), wd, args.num_threads)

    G = build_graph(d, board, glob, args.gap, args.include_nics, args.scale, args.node_size)
    base = os.path.join(OUT_DIR, "%s_%s_%s" % (topo, board, glob))
    nx.write_graphml(G, base + ".graphml")
    nx.write_gexf(add_gexf_viz(G), base + ".gexf")

    n_board = sum(1 for _, a in G.nodes(data=True) if a["role"] == "board")
    n_ft = sum(1 for _, a in G.nodes(data=True) if a["role"] == "fat_tree")
    n_intra = sum(1 for _, _, a in G.edges(data=True) if a.get("link_type") == "intra_board")
    n_fttree = sum(1 for _, _, a in G.edges(data=True) if a.get("link_type") == "fat_tree")
    print("[%s] board switches=%d  fat-tree switches=%d  intra-board links=%d  fat-tree links=%d"
          % (topo, n_board, n_ft, n_intra, n_fttree))
    print("       -> %s.graphml  /  %s.gexf" % (base, base))
    if args.preview:
        png = base + ".png"
        preview_png(G, png, "%s  (board %s, global %s, %d nodes)" % (topo, board, glob, n_nodes))
        print("       -> preview %s" % png)
    return G


def main():
    ap = ArgumentParser(description="Export HammingMesh fabric to GraphML/GEXF for Gephi")
    ap.add_argument("--board_shape", default="8x8")
    ap.add_argument("--global_shape", default="4x4")
    ap.add_argument("--topo", choices=["mesh", "jellyfish", "both"], default="both")
    ap.add_argument("--ft_nodes", type=int, default=0)
    ap.add_argument("--gap", type=int, default=None, help="spacing between boards (default ~ board/2)")
    ap.add_argument("--scale", type=float, default=20.0,
                    help="multiply node positions so spacing >> node size (default 20)")
    ap.add_argument("--node_size", type=float, default=2.5,
                    help="base node size in the GEXF/GraphML viz (default 2.5)")
    ap.add_argument("--include_nics", action="store_true")
    ap.add_argument("--preview", action="store_true", help="also render a matplotlib PNG preview")
    ap.add_argument("--num_threads", type=int, default=min(8, os.cpu_count() or 1))
    args = ap.parse_args()
    if args.gap is None:
        args.gap = max(2, dims(args.board_shape)[0] // 2)

    pathlib.Path(OUT_DIR).mkdir(parents=True, exist_ok=True)
    print("Exporting HammingMesh fabric (board %s, global %s) -> %s\n" % (
        args.board_shape, args.global_shape, OUT_DIR))
    todo = [("mesh", False), ("jellyfish", True)] if args.topo == "both" \
        else [(args.topo, args.topo == "jellyfish")]
    for topo, jelly in todo:
        export_one(topo, jelly, args)
        print()

    print("Open the .gexf (positions+colors baked in) in Gephi:")
    print("  - color is per board; fat-tree switches are dark squares; gateways are larger.")
    print("  - Filters: by 'role' (board/fat_tree) or 'board_id'; Appearance: size by 'intra_degree'.")
    print("  - Edge attribute 'link_type' separates intra_board vs fat_tree (partition/hide to compare).")


if __name__ == "__main__":
    main()
