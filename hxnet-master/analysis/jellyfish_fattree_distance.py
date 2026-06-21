"""
Worst-case node-to-fat-tree distance within Jellyfish local boards.

For each Jellyfish board, every board switch has a shortest in-board hop distance
to its nearest fat-tree GATEWAY (a board switch that holds a fat-tree uplink;
gateway distance = 0). This computes, per board, the maximum of that over its
nodes, and then the MAXIMUM across all boards:

    max over boards, max over nodes, min over gateways  hops(node, gateway)

i.e. the single node that sits deepest inside its board, farthest from any uplink.
(Distance is hops to the nearest gateway node; the fat-tree switch itself is +1.)

The graph is taken from what SST actually elaborates
(`sst --run-mode=init --output-json`), so it is faithful to the current
pymerlin.py wiring (no reconstruction). `--run-mode=init` builds the graph without
running a simulation, so this also works for ft1/ft2 (which crash only at run time).

Usage:
    uv run python jellyfish_fattree_distance.py                       # 8x8 board / 4x4 global, ft0
    uv run python jellyfish_fattree_distance.py --ft_nodes 1 --builds 5
    uv run python jellyfish_fattree_distance.py --graph some_graph.json
"""

import os
import sys
import json
import shutil
import pathlib
from collections import deque, Counter
from argparse import ArgumentParser

# Reuse the (validated) graph-dump + helpers from the step-2 connectivity tool.
from check_connectivity import (
    write_motif, model_options, run_sst, _canon, EMBER_TEST_DIR,
)

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
WORK_DIR = os.path.join(SCRIPT_DIR, "output", "fattree_distance")


def _is_true(v):
    return str(v).lower() in ("true", "1", "yes")


def dump_graph(cfg, build_dir, num_threads):
    """Run `sst --run-mode=init --output-json` and return the graph.json path."""
    motif = os.path.join(build_dir, "motif")
    write_motif(motif, cfg["board"], cfg["glob"], 8)
    graph_json = os.path.join(build_dir, "graph.json")
    opts = model_options(cfg, motif)
    run_sst(opts, num_threads,
            os.path.join(build_dir, "init.log"),
            os.path.join(build_dir, "init.err"),
            extra_sst_args="--run-mode=init --output-json=%s" % graph_json,
            timeout=900)
    if not os.path.isfile(graph_json) or os.path.getsize(graph_json) == 0:
        raise RuntimeError("no graph.json produced (see %s)" % build_dir)
    return graph_json


def analyze_graph(graph_json, switch_per_board):
    """Parse the SST graph and compute per-board worst node->gateway distances.

    Returns dict with per-board results and the overall maximum.
    """
    d = json.load(open(graph_json))
    comps = {c["name"]: c for c in d["components"]}

    def params(name):
        sub = comps[name].get("subcomponents", [])
        return sub[0].get("params", {}) if sub else {}

    # Classify routers.
    routers = {n: c for n, c in comps.items() if c.get("type") == "merlin.hr_router"}
    board_switch = {}   # name -> board_id
    ft_switch = set()
    for n in routers:
        p = params(n)
        if _is_true(p.get("is_board_switch")):
            gid = int(p["global_switch_id"])
            board_switch[n] = gid // switch_per_board
        else:
            ft_switch.add(n)

    # Router-router edges only (ignore nic/loopback/ember links).
    intra = {}          # board_id -> {node: set(neighbors)}  (board-switch <-> same-board board-switch)
    gateways = {}       # board_id -> set(board switches with a fat-tree uplink)
    for bid in set(board_switch.values()):
        intra[bid] = {}
        gateways[bid] = set()
    for n, bid in board_switch.items():
        intra[bid].setdefault(n, set())

    for l in d["links"]:
        a, b = _canon(l["left"]), _canon(l["right"])
        if a not in routers or b not in routers:
            continue
        a_board = a in board_switch
        b_board = b in board_switch
        if a_board and b_board and board_switch[a] == board_switch[b]:
            bid = board_switch[a]
            intra[bid][a].add(b)
            intra[bid][b].add(a)
        elif a_board and b in ft_switch:
            gateways[board_switch[a]].add(a)
        elif b_board and a in ft_switch:
            gateways[board_switch[b]].add(b)

    # Per board: multi-source BFS from gateways over the intra-board subgraph.
    per_board = []   # (board_id, board_max, n_gateways, n_nodes, unreachable_count, argmax_node)
    for bid in sorted(intra):
        adj = intra[bid]
        gws = gateways[bid]
        dist = {g: 0 for g in gws}
        q = deque(gws)
        while q:
            u = q.popleft()
            for v in adj.get(u, ()):  # noqa
                if v not in dist:
                    dist[v] = dist[u] + 1
                    q.append(v)
        unreachable = [n for n in adj if n not in dist]
        reach = {n: dist[n] for n in adj if n in dist}
        if reach:
            argmax = max(reach, key=reach.get)
            board_max = reach[argmax]
        else:
            argmax, board_max = None, -1
        per_board.append({
            "board": bid, "board_max": board_max, "n_gateways": len(gws),
            "n_nodes": len(adj), "unreachable": len(unreachable), "argmax": argmax,
        })

    finite = [b for b in per_board if b["board_max"] >= 0]
    overall = max(finite, key=lambda b: b["board_max"]) if finite else None
    return {"per_board": per_board, "overall": overall,
            "n_boards": len(per_board),
            "any_unreachable": any(b["unreachable"] for b in per_board)}


def report_build(res, build_idx):
    maxima = [b["board_max"] for b in res["per_board"]]
    hist = Counter(maxima)
    ov = res["overall"]
    print("  build %d: overall max-min distance = %d  (board %s, node %s; %d gateways, %d/%d nodes)" % (
        build_idx, ov["board_max"], ov["board"], ov["argmax"],
        ov["n_gateways"], ov["n_nodes"] - ov["unreachable"], ov["n_nodes"]))
    dist_str = ", ".join("%d:%d" % (k, hist[k]) for k in sorted(hist))
    print("           per-board max distribution {dist:#boards}: %s" % dist_str)
    if res["any_unreachable"]:
        bad = [b for b in res["per_board"] if b["unreachable"]]
        print("           WARNING: %d board(s) have nodes unreachable from any gateway: %s" % (
            len(bad), [(b["board"], b["unreachable"]) for b in bad][:8]))
    return ov["board_max"]


def main():
    ap = ArgumentParser(description="Max-min node->fat-tree distance in Jellyfish boards")
    ap.add_argument("--board_shape", default="8x8")
    ap.add_argument("--global_shape", default="4x4")
    ap.add_argument("--fat_tree_shape", default="1:1,64")
    ap.add_argument("--ft_nodes", type=int, default=0)
    ap.add_argument("--builds", type=int, default=5)
    ap.add_argument("--num_threads", type=int, default=min(8, os.cpu_count() or 1))
    ap.add_argument("--graph", default=None,
                    help="analyze an existing graph.json instead of dumping")
    args = ap.parse_args()

    b = [int(x) for x in args.board_shape.split("x")]
    switch_per_board = b[0] * b[1]
    cfg = dict(board=args.board_shape, glob=args.global_shape,
               fat_tree_shape=args.fat_tree_shape, jellyfish=True,
               ft_nodes=args.ft_nodes)

    print("Jellyfish node->fat-tree distance: board %s, global %s, ft_nodes=%d" % (
        args.board_shape, args.global_shape, args.ft_nodes))
    print("(distance = in-board hops to nearest gateway node; gateway = 0; "
          "fat-tree switch itself is +1)\n")

    if args.graph:
        res = analyze_graph(args.graph, switch_per_board)
        report_build(res, 0)
        return

    pathlib.Path(WORK_DIR).mkdir(parents=True, exist_ok=True)
    worst = -1
    vals = []
    for i in range(args.builds):
        build_dir = os.path.join(WORK_DIR, "ft%d" % args.ft_nodes, "build%d" % i)
        if os.path.isdir(build_dir):
            shutil.rmtree(build_dir)
        pathlib.Path(build_dir).mkdir(parents=True, exist_ok=True)
        try:
            gj = dump_graph(cfg, build_dir, args.num_threads)
        except RuntimeError as e:
            print("  build %d: FAILED to dump graph: %s" % (i, e))
            continue
        res = analyze_graph(gj, switch_per_board)
        v = report_build(res, i)
        vals.append(v)
        worst = max(worst, v)

    if vals:
        print("\n==> ANSWER (board %s, global %s, ft%d): max-min node->fat-tree "
              "distance = %d hops to nearest gateway (worst of %d builds; mean %.2f)" % (
                  args.board_shape, args.global_shape, args.ft_nodes, worst,
                  len(vals), sum(vals) / len(vals)))


if __name__ == "__main__":
    main()
