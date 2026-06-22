"""
Minimum number of connections (degree) a node has within a Jellyfish board.

Faithful: degrees are taken from SST's elaborated graph
(`sst --run-mode=init --output-json`), like the other analysis tools.

Two notions of "connections within Jellyfish" are reported:
  * intra-board jellyfish degree -- links to OTHER switches of the same board
    (the Jellyfish random graph only); headline answer.
  * total degree -- intra-board links + fat-tree uplinks (all ports used).

Two contexts:
  * standalone : the isolated single-board Jellyfish (--topo=jellyfish, no fat
                 tree) => 4-regular, so intra == total.
  * full       : a Jellyfish board inside the full HammingMesh (--topo=hx
                 --jellyfish); perimeter nodes spend ports on fat-tree uplinks.

Usage:
    uv run python jellyfish_min_degree.py                          # both, board 8x8 / global 4x4
    uv run python jellyfish_min_degree.py --context full --board_shape 8x8 --global_shape 4x4
"""

import os
import shutil
import pathlib
from collections import Counter
from argparse import ArgumentParser

from check_connectivity import _canon
from count_links import dims, write_motif, dump, _routers_and_params

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
WORK_DIR = os.path.join(SCRIPT_DIR, "output", "min_degree")
COMMON = '--param="nic:module=merlin.reorderlinkcontrol" --hostsPerRtr=1 '


def degree_stats(d, spb):
    """Return (intra_hist, total_hist, n_board, example_min_node)."""
    comps, routers, P = _routers_and_params(d)
    board_of = {}
    ft = set()
    for n in routers:
        if str(P(n).get("is_board_switch")).lower() == "true":
            board_of[n] = int(P(n)["global_switch_id"]) // spb
        else:
            ft.add(n)

    intra = Counter({n: 0 for n in board_of})
    uplink = Counter({n: 0 for n in board_of})
    for l in d["links"]:
        a, b = _canon(l["left"]), _canon(l["right"])
        if a in board_of and b in board_of and board_of[a] == board_of[b]:
            intra[a] += 1
            intra[b] += 1
        elif a in board_of and b in ft:
            uplink[a] += 1
        elif b in board_of and a in ft:
            uplink[b] += 1

    intra_hist = Counter(intra[n] for n in board_of)
    total_hist = Counter(intra[n] + uplink[n] for n in board_of)
    min_intra = min(intra_hist)
    example = next((n for n in board_of if intra[n] == min_intra), None)
    return intra_hist, total_hist, len(board_of), example


def report(label, d, spb):
    ih, th, n, example = degree_stats(d, spb)
    n_at_min = ih[min(ih)]
    print("  %s" % label)
    print("    intra-board jellyfish degree: %s" % dict(sorted(ih.items())))
    print("      -> MIN = %d connections  (%d of %d nodes; e.g. %s)" % (
        min(ih), n_at_min, n, example))
    print("    total degree (intra + fat-tree uplinks): %s -> MIN = %d" % (
        dict(sorted(th.items())), min(th)))
    return min(ih), min(th)


def opts_standalone(board, motif):
    return COMMON + "--topo=jellyfish --shape=%s --loadFile=%s" % (board, motif)


def opts_full(board, glob, ft_nodes, motif):
    s = COMMON + ("--topo=hx --boardShape=%s --globalShape=%s --fatTreeShape=1:1,64 --jellyfish "
                  % (board, glob))
    if ft_nodes > 0:
        s += "--ftNodes=%d " % ft_nodes
    return s + "--loadFile=%s" % motif


def main():
    ap = ArgumentParser(description="Minimum node degree within a Jellyfish board")
    ap.add_argument("--board_shape", default="8x8")
    ap.add_argument("--global_shape", default="4x4", help="full context only")
    ap.add_argument("--ft_nodes", type=int, default=0)
    ap.add_argument("--builds", type=int, default=1)
    ap.add_argument("--num_threads", type=int, default=min(8, os.cpu_count() or 1))
    ap.add_argument("--context", choices=["standalone", "full", "both"], default="both")
    args = ap.parse_args()

    board = args.board_shape
    r, c = dims(board)
    spb = r * c
    nid_range = "generateNidListRange(0,%d)" % spb
    nid_hx = "generateNidListHx(%sx%s)" % (board, args.global_shape)

    print("Minimum connections of a node within Jellyfish (board %s)\n" % board)
    pathlib.Path(WORK_DIR).mkdir(parents=True, exist_ok=True)

    for b in range(args.builds):
        if args.builds > 1:
            print("--- build %d ---" % b)
        bd = os.path.join(WORK_DIR, "build%d" % b)
        if os.path.isdir(bd):
            shutil.rmtree(bd)

        if args.context in ("standalone", "both"):
            sdir = os.path.join(bd, "standalone")
            pathlib.Path(sdir).mkdir(parents=True)
            sm = os.path.join(sdir, "motif")
            write_motif(sm, nid_range)
            d = dump(opts_standalone(board, sm), sdir, args.num_threads)
            print("[Standalone Jellyfish board, no fat tree]")
            report("jellyfish (single board, %d nodes)" % spb, d, spb)
            print()

        if args.context in ("full", "both"):
            fdir = os.path.join(bd, "full")
            pathlib.Path(fdir).mkdir(parents=True)
            fm = os.path.join(fdir, "motif")
            write_motif(fm, nid_hx)
            d = dump(opts_full(board, args.global_shape, args.ft_nodes, fm), fdir, args.num_threads)
            print("[Full HammingMesh Jellyfish boards]  (global %s, ft%d)" % (
                args.global_shape, args.ft_nodes))
            report("jellyfish board (%d switches/board)" % spb, d, spb)
            print()


if __name__ == "__main__":
    main()
