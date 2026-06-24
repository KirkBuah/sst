"""
Count links: 2D-mesh board vs Jellyfish board, in two contexts.

Both contexts take the link set from SST's elaborated graph
(`sst --run-mode=init --output-json`), so they are faithful to the current
pymerlin.py wiring (no reconstruction).

  standalone : the isolated single-board topologies (no fat tree) from step 1
               --topo=mesh vs --topo=jellyfish. Count = all router<->router links.
               (Jellyfish is a canonical 4-regular random graph => 2N links;
                2D mesh => R(C-1)+C(R-1).)

  full       : intra-board links per board inside the full HammingMesh
               --topo=hx vs --topo=hx --jellyfish. Jellyfish boards reserve the
               same perimeter ports for fat-tree uplinks the mesh uses, so the
               intra-board counts come out equal.

Usage:
    uv run python count_links.py                              # both, board 8x8 (global 4x4)
    uv run python count_links.py --context standalone --board_shape 8x8
    uv run python count_links.py --context full --board_shape 8x8 --global_shape 4x4
"""

import os
import json
import shutil
import pathlib
from collections import defaultdict, Counter
from argparse import ArgumentParser

from check_connectivity import run_sst, _canon, EMBER_TEST_DIR, EMBER_LOAD

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
WORK_DIR = os.path.join(SCRIPT_DIR, "output", "link_counts")


def dims(shape):
    return [int(x) for x in shape.split("x")]


def mesh_intra_links(board):
    r, c = dims(board)
    return r * (c - 1) + c * (r - 1)


def write_motif(path, nid_expr, msg_size=8):
    with open(path, "w") as f:
        f.write("[JOB_ID] 10\n")
        f.write("[NID_LIST] generateNidList=%s\n" % nid_expr)
        f.write("[MOTIF] Init\n")
        f.write("[MOTIF] AllPingPong messageSize=%d\n" % msg_size)
        f.write("[MOTIF] Fini")


def dump(model_opts, build_dir, num_threads):
    graph_json = os.path.join(build_dir, "graph.json")
    run_sst(model_opts, num_threads,
            os.path.join(build_dir, "init.log"),
            os.path.join(build_dir, "init.err"),
            extra_sst_args="--run-mode=init --output-json=%s" % graph_json,
            timeout=900)
    if not os.path.isfile(graph_json) or os.path.getsize(graph_json) == 0:
        raise RuntimeError("no graph.json produced (see %s)" % build_dir)
    return json.load(open(graph_json))


def _routers_and_params(d):
    comps = {c["name"]: c for c in d["components"]}
    routers = {n: c for n, c in comps.items() if c.get("type") == "merlin.hr_router"}

    def P(n):
        s = comps[n].get("subcomponents", [])
        return s[0].get("params", {}) if s else {}
    return comps, routers, P


# --- standalone single board: count every router<->router link ---------------

def count_standalone(label, model_opts, board, build_dir, num_threads):
    d = dump(model_opts, build_dir, num_threads)
    _, routers, _ = _routers_and_params(d)
    degree = defaultdict(int)
    n_links = 0
    for l in d["links"]:
        a, b = _canon(l["left"]), _canon(l["right"])
        if a in routers and b in routers:
            n_links += 1
            degree[a] += 1
            degree[b] += 1
    n = len(routers)
    degs = Counter(degree[r] for r in routers)
    print("  %-10s : %d routers, %d links  (degrees: %s)" % (
        label, n, n_links, dict(sorted(degs.items()))))
    return n_links, n


# --- full HammingMesh: intra-board links per board ---------------------------

def count_full(label, model_opts, board, build_dir, num_threads):
    spb = dims(board)[0] * dims(board)[1]
    d = dump(model_opts, build_dir, num_threads)
    _, routers, P = _routers_and_params(d)
    board_of = {}
    for n in routers:
        p = P(n)
        if str(p.get("is_board_switch")).lower() == "true":
            board_of[n] = int(p["global_switch_id"]) // spb
    per_board = Counter()
    for l in d["links"]:
        a, b = _canon(l["left"]), _canon(l["right"])
        if a in board_of and b in board_of and board_of[a] == board_of[b]:
            per_board[board_of[a]] += 1
    nboards = len(set(board_of.values()))
    vals = [per_board[b] for b in sorted(per_board)]
    uniform = len(set(vals)) == 1
    print("  %-10s : %d boards, intra-board links/board = %s%s  (total %d)" % (
        label, nboards, vals[0] if uniform else vals,
        " (uniform)" if uniform else " (NON-UNIFORM)", sum(vals)))
    return (vals[0] if uniform else None), sum(vals), nboards


def relation(mesh_v, jelly_v):
    if mesh_v == jelly_v:
        return "EQUAL (mesh == jellyfish)"
    return "mesh %s jellyfish" % (">" if mesh_v > jelly_v else "<")


def main():
    ap = ArgumentParser(description="Count links: 2D mesh board vs Jellyfish board")
    ap.add_argument("--board_shape", default="8x8")
    ap.add_argument("--global_shape", default="4x4", help="full-HammingMesh only")
    ap.add_argument("--ft_nodes", type=int, default=0)
    ap.add_argument("--builds", type=int, default=1)
    ap.add_argument("--num_threads", type=int, default=min(8, os.cpu_count() or 1))
    ap.add_argument("--context", choices=["standalone", "full", "both"], default="both")
    args = ap.parse_args()

    board = args.board_shape
    r, c = dims(board)
    n_board = r * c
    nid_range = "generateNidListRange(0,%d)" % n_board
    nid_hx = "generateNidListHx(%sx%s)" % (board, args.global_shape)
    common = '--param="nic:module=merlin.reorderlinkcontrol" --hostsPerRtr=1 '

    pathlib.Path(WORK_DIR).mkdir(parents=True, exist_ok=True)

    def opts_standalone(topo, motif):
        return common + "--topo=%s --shape=%s --loadFile=%s" % (topo, board, motif)

    def opts_full(jelly, motif):
        s = common + ("--topo=hx --boardShape=%s --globalShape=%s --fatTreeShape=1:1,64 "
                      % (board, args.global_shape))
        if jelly:
            s += "--jellyfish "
            if args.ft_nodes > 0:
                s += "--ftNodes=%d " % args.ft_nodes
        return s + "--loadFile=%s" % motif

    print("Link count: 2D mesh board vs Jellyfish board (board %s)\n" % board)

    for b in range(args.builds):
        if args.builds > 1:
            print("--- build %d ---" % b)
        bd = os.path.join(WORK_DIR, "build%d" % b)
        if os.path.isdir(bd):
            shutil.rmtree(bd)

        if args.context in ("standalone", "both"):
            print("[Standalone single board, no fat tree]")
            mdir = os.path.join(bd, "std_mesh"); pathlib.Path(mdir).mkdir(parents=True)
            jdir = os.path.join(bd, "std_jelly"); pathlib.Path(jdir).mkdir(parents=True)
            mm = os.path.join(mdir, "motif"); write_motif(mm, nid_range)
            jm = os.path.join(jdir, "motif"); write_motif(jm, nid_range)
            m_links, _ = count_standalone("mesh", opts_standalone("mesh", mm), board, mdir, args.num_threads)
            j_links, _ = count_standalone("jellyfish", opts_standalone("jellyfish", jm), board, jdir, args.num_threads)
            print("    analytic mesh = R(C-1)+C(R-1) = %d ; relation: %s\n" % (
                mesh_intra_links(board), relation(m_links, j_links)))

        if args.context in ("full", "both"):
            print("[Full HammingMesh, intra-board links per board]  (global %s, ft%d)" % (
                args.global_shape, args.ft_nodes))
            mdir = os.path.join(bd, "hx_mesh"); pathlib.Path(mdir).mkdir(parents=True)
            jdir = os.path.join(bd, "hx_jelly"); pathlib.Path(jdir).mkdir(parents=True)
            mm = os.path.join(mdir, "motif"); write_motif(mm, nid_hx)
            jm = os.path.join(jdir, "motif"); write_motif(jm, nid_hx)
            m_pb, m_tot, _ = count_full("mesh", opts_full(False, mm), board, mdir, args.num_threads)
            j_pb, j_tot, _ = count_full("jellyfish", opts_full(True, jm), board, jdir, args.num_threads)
            rel = relation(m_pb, j_pb) if (m_pb is not None and j_pb is not None) else "n/a (non-uniform)"
            print("    analytic mesh/board = %d ; per-board relation: %s\n" % (
                mesh_intra_links(board), rel))


if __name__ == "__main__":
    main()
