"""
Why does HammingMesh-with-Jellyfish underperform HammingMesh-with-mesh on AllToAll?

This runs the SAME AllToAll (AllPingPong, the motif the benchmark uses) on both
the 2D-mesh boards (--topo=hx) and the Jellyfish boards (--topo=hx --jellyfish),
with merlin's per-port router statistics turned on, and quantifies WHERE the load
goes. The slowdown hypothesis is routing-induced congestion, not topology/hops:

  H1  gateway hot-spotting : Jellyfish funnels all off-board traffic of a board
       through a SINGLE fixed edge node + uplink (hamming.cc route_packet_jellyfish),
       while the mesh spreads it across the whole perimeter. -> uplink load is far
       more skewed (higher max / coefficient of variation) for Jellyfish.
  H2  no adaptive routing  : Jellyfish uses one deterministic next-hop per dest
       (jf_routing_table), the mesh picks among minimal ports by output credits.
       -> intra-board ports have hotter, more skewed load for Jellyfish.
  H3  diagonal row/col skew: the diagonal edge-selection is stubbed to always pick
       the row tree first (hamming.cc:555-590). -> row-uplink traffic >> col-uplink
       traffic for Jellyfish; the mesh is balanced.
  H4  NOT hop count        : a random graph has small diameter, so avg switch hops
       per packet is similar/lower for Jellyfish -> rules out "longer paths".

Everything is measured from SST itself: a single `sst --run-mode=both
--output-json=graph.json --statsModule=router_stats_mod --statsFile=stats.csv`
invocation gives the exact built graph AND the per-port stats from the same run
(the Jellyfish graph is unseeded, so one invocation keeps wiring and stats
consistent). Port classes come from the graph's link names (uniform across mesh and
Jellyfish): nic.* = NIC, link.row* = row uplink, link.col* = col uplink, the board
switch is always the link's `right` endpoint; everything else on a board switch is
intra-board.

Usage:
    uv run python router_load_diag.py                       # board 8x8 / global 4x4, msg 2^16
    uv run python router_load_diag.py --board_shape 4x4 --global_shape 4x4 --msg_size 65536
    uv run python router_load_diag.py --topo jellyfish --no_plot
"""

import os
import csv
import json
import math
import shutil
import pathlib
import subprocess
from argparse import ArgumentParser

from check_connectivity import (
    EMBER_TEST_DIR, EMBER_LOAD, _canon, write_motif, model_options, num_nodes,
)
from count_links import dims, _routers_and_params

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
OUT_DIR = os.path.join(SCRIPT_DIR, "output", "router_load")

# Port classes
NIC, INTRA, ROW_UP, COL_UP, TREE = "nic", "intra_board", "row_uplink", "col_uplink", "tree"
UPLINK = (ROW_UP, COL_UP)


# ---------------------------------------------------------------------------
# Run SST (graph + per-port stats in one invocation)
# ---------------------------------------------------------------------------

def run_sst_stats(cfg, msg_size, num_threads, work_dir, timeout):
    """One `--run-mode=both` invocation -> (graph.json, stats.csv, sim_time_us)."""
    pathlib.Path(work_dir).mkdir(parents=True, exist_ok=True)
    motif = os.path.join(work_dir, "motif")
    write_motif(motif, cfg["board"], cfg["glob"], msg_size)
    graph_json = os.path.join(work_dir, "graph.json")
    stats_csv = os.path.join(work_dir, "stats.csv")
    out_path = os.path.join(work_dir, "run.out")
    err_path = os.path.join(work_dir, "run.err")

    extra = "--statsModule=router_stats_mod --statsFile=%s " % stats_csv
    algo = cfg.get("algorithm")
    if algo:
        extra += "--algorithm=%s " % algo
    opts = model_options(cfg, motif, extra=extra)
    # analysis/ on PYTHONPATH so emberLoad can import router_stats_mod.
    pp = "%s:%s" % (EMBER_TEST_DIR, SCRIPT_DIR)
    cmd = (
        'PYTHONPATH="{pp}" SST_NO_MEM=1 sst --run-mode=both --output-json={gj} '
        '--num_threads={nt} --model-options="{opts}" {ember} > {out} 2> {err}'
    ).format(pp=pp, gj=graph_json, nt=num_threads, opts=opts, ember=EMBER_LOAD,
             out=out_path, err=err_path)
    try:
        subprocess.run(cmd, shell=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        raise RuntimeError("SST timed out after %ds (deadlock?)" % timeout)

    text = open(out_path, errors="replace").read() if os.path.isfile(out_path) else ""
    if "Simulation is complete" not in text:
        raise RuntimeError("simulation did not complete (see %s / %s)" % (out_path, err_path))
    sim_us = None
    for line in text.splitlines():
        if "simulated time:" in line:
            tok = line.split("simulated time:")[1].strip().split()
            val, unit = float(tok[0]), tok[1]
            sim_us = val * {"ns": 1e-3, "us": 1.0, "ms": 1e3, "s": 1e6}.get(unit, 1.0)
    if not os.path.isfile(graph_json) or os.path.getsize(graph_json) == 0:
        raise RuntimeError("no graph.json produced")
    if not os.path.isfile(stats_csv) or os.path.getsize(stats_csv) == 0:
        raise RuntimeError("no stats.csv produced")
    return graph_json, stats_csv, sim_us


# ---------------------------------------------------------------------------
# Parse stats + classify ports
# ---------------------------------------------------------------------------

WANT_STATS = {"send_packet_count", "send_bit_count", "output_port_stalls"}


def parse_stats(stats_csv):
    """(component, port_int) -> {stat_name: Sum.u64}."""
    out = {}
    with open(stats_csv, newline="") as f:
        reader = csv.reader(f, skipinitialspace=True)
        header = next(reader)
        idx = {name.strip(): i for i, name in enumerate(header)}
        c_i, n_i, s_i = idx["ComponentName"], idx["StatisticName"], idx["StatisticSubId"]
        sum_i = next(i for name, i in idx.items() if name.startswith("Sum."))
        for row in reader:
            if len(row) <= sum_i:
                continue
            stat = row[n_i].strip()
            if stat not in WANT_STATS:
                continue
            sub = row[s_i].strip()
            if not sub.startswith("port"):
                continue
            key = (row[c_i].strip(), int(sub[4:]))
            out.setdefault(key, {})[stat] = int(row[sum_i])
    return out


def _port_int(p):
    return int(p[4:]) if isinstance(p, str) and p.startswith("port") else int(p)


def classify_ports(graph_json, spb):
    """Return (cls, board_of, is_board) where cls[(comp, port_int)] -> class string.

    Board switches: NIC / row_uplink / col_uplink captured from the link the board
    sits on the RIGHT of (nic.* / link.row* / link.col*); every other board-switch
    port is intra_board by elimination. Tree/global switch ports -> 'tree'.
    """
    d = json.load(open(graph_json))
    comps, routers, P = _routers_and_params(d)

    board_of, is_board = {}, {}
    for n in routers:
        p = P(n)
        bsw = str(p.get("is_board_switch")).lower() == "true"
        is_board[n] = bsw
        if bsw:
            board_of[n] = int(p["global_switch_id"]) // spb

    cls = {}
    for l in d["links"]:
        name = l.get("name", "")
        left, right = _canon(l["left"]), _canon(l["right"])
        rp = l.get("rightPort")
        # only links whose right endpoint is a real router port ("portN")
        if not (isinstance(rp, str) and rp.startswith("port")) or right not in routers:
            continue
        rp = _port_int(rp)
        # NIC link: the router endpoint is the board switch (always 'right').
        is_nic = name.startswith("nic.") or comps.get(left, {}).get("type") == "firefly.nic" \
            or comps.get(right, {}).get("type") == "firefly.nic"
        if is_nic and right in routers:
            cls[(right, rp)] = NIC
        elif name.startswith("link.row") and right in routers:
            cls[(right, rp)] = ROW_UP
        elif name.startswith("link.col") and right in routers:
            cls[(right, rp)] = COL_UP

    # Fill the rest from each router's full port list.
    for n in routers:
        for port in comps[n].get("ports", []):
            pi = _port_int(port)
            key = (n, pi)
            if key in cls:
                continue
            cls[key] = INTRA if is_board[n] else TREE
    return cls, board_of, is_board


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------

def _stats_of(values):
    """max, mean, cv (coefficient of variation = std/mean) of a list."""
    if not values:
        return 0.0, 0.0, 0.0
    n = len(values)
    mean = sum(values) / n
    if mean == 0:
        return max(values), 0.0, 0.0
    var = sum((v - mean) ** 2 for v in values) / n
    return max(values), mean, math.sqrt(var) / mean


def analyze(graph_json, stats_csv, spb):
    stats = parse_stats(stats_csv)
    cls, board_of, is_board = classify_ports(graph_json, spb)

    # Load is measured in BITS (send_bit_count), not packets: reorderlinkcontrol
    # groups payload into different-size packets for mesh vs Jellyfish, so packet
    # counts are not comparable while bits (the true offered load) are conserved.
    def pkts(key):
        return stats.get(key, {}).get("send_bit_count", 0)

    def stalls(key):
        return stats.get(key, {}).get("output_port_stalls", 0)

    by_class = {NIC: [], INTRA: [], ROW_UP: [], COL_UP: [], TREE: []}
    stall_by_class = {NIC: [], INTRA: [], ROW_UP: [], COL_UP: [], TREE: []}
    per_port = []   # (pkts, stalls, class, comp, port)
    for key, c in cls.items():
        p, s = pkts(key), stalls(key)
        by_class[c].append(p)
        stall_by_class[c].append(s)
        per_port.append((p, s, c, key[0], key[1]))

    delivered = sum(by_class[NIC])                 # packets handed to endpoints
    inter_switch = [p for p, _, c, _, _ in per_port if c != NIC]
    inter_switch_hops = sum(inter_switch)
    avg_hops = inter_switch_hops / delivered if delivered else 0.0

    uplinks = by_class[ROW_UP] + by_class[COL_UP]
    up_max, up_mean, up_cv = _stats_of(uplinks)
    in_max, in_mean, in_cv = _stats_of(by_class[INTRA])

    row_tot, col_tot = sum(by_class[ROW_UP]), sum(by_class[COL_UP])
    total_stalls = sum(s for _, s, _, _, _ in per_port)

    # bottleneck links
    busiest = max(per_port, key=lambda t: t[0])
    most_stalled = max(per_port, key=lambda t: t[1])

    # stall concentration: share carried by the worst 1% of ports
    stall_sorted = sorted((s for _, s, _, _, _ in per_port), reverse=True)
    k = max(1, len(stall_sorted) // 100)
    top_share = sum(stall_sorted[:k]) / total_stalls if total_stalls else 0.0

    return {
        "delivered": delivered,
        "avg_switch_hops": avg_hops,
        "uplink": {"n": len(uplinks), "max": up_max, "mean": up_mean, "cv": up_cv},
        "intra": {"n": len(by_class[INTRA]), "max": in_max, "mean": in_mean, "cv": in_cv},
        "row_uplink_pkts": row_tot, "col_uplink_pkts": col_tot,
        "row_col_ratio": (row_tot / col_tot) if col_tot else float("inf"),
        "total_stalls": total_stalls, "stall_top1pct_share": top_share,
        "busiest": busiest, "most_stalled": most_stalled,
        "by_class_pkts": {c: sum(v) for c, v in by_class.items()},
        "stall_by_class": {c: sum(v) for c, v in stall_by_class.items()},
        "_uplinks": uplinks, "_intra": by_class[INTRA], "_inter_ports": per_port,
    }


# ---------------------------------------------------------------------------
# Report + plot
# ---------------------------------------------------------------------------

def _fmt(n):
    return "{:,}".format(int(n))


def _mb(bits):
    """bits -> human Mbit/Gbit string."""
    if bits >= 1e9:
        return "%.2f Gb" % (bits / 1e9)
    return "%.2f Mb" % (bits / 1e6)


def report(label, r):
    print("\n[%s]   (load = bits sent on a port over the whole run)" % label)
    print("  delivered load (sum over NIC ports)     : %s" % _mb(r["delivered"]))
    print("  avg inter-switch hops / message          : %.2f   (H4: path length)" % r["avg_switch_hops"])
    up = r["uplink"]
    print("  board->tree UPLINKS (%d): max=%s mean=%s  CV=%.2f  max/mean=%.1fx   (H1)" % (
        up["n"], _mb(up["max"]), _mb(up["mean"]), up["cv"],
        (up["max"] / up["mean"]) if up["mean"] else 0))
    print("  ROW-uplink load=%s  COL-uplink load=%s  row/col=%.2f   (H3)" % (
        _mb(r["row_uplink_pkts"]), _mb(r["col_uplink_pkts"]), r["row_col_ratio"]))
    it = r["intra"]
    print("  INTRA-board ports (%d): max=%s mean=%s  CV=%.2f   (H2)" % (
        it["n"], _mb(it["max"]), _mb(it["mean"]), it["cv"]))
    b = r["busiest"]
    print("  busiest link : %s  on %s/port%d  [%s]" % (_mb(b[0]), b[3], b[4], b[2]))
    s = r["most_stalled"]
    print("  most-stalled : %s stall-units on %s/port%d  [%s]" % (_fmt(s[1]), s[3], s[4], s[2]))
    print("  total output-port stalls : %s   (worst 1%% of ports carry %.0f%%)" % (
        _fmt(r["total_stalls"]), 100 * r["stall_top1pct_share"]))


def compare(rm, rj):
    def ratio(a, b):
        return (a / b) if b else float("inf")
    print("\n" + "=" * 72)
    print("MESH  vs  JELLYFISH   (jellyfish / mesh)")
    print("=" * 72)
    rows = [
        ("busiest link (Mbit)", rm["busiest"][0] / 1e6, rj["busiest"][0] / 1e6),
        ("uplink max (Mbit)", rm["uplink"]["max"] / 1e6, rj["uplink"]["max"] / 1e6),
        ("uplink CV", rm["uplink"]["cv"], rj["uplink"]["cv"]),
        ("uplink max/mean", ratio(rm["uplink"]["max"], rm["uplink"]["mean"]),
                            ratio(rj["uplink"]["max"], rj["uplink"]["mean"])),
        ("row/col uplink ratio", rm["row_col_ratio"], rj["row_col_ratio"]),
        ("intra-board max (Mbit)", rm["intra"]["max"] / 1e6, rj["intra"]["max"] / 1e6),
        ("intra-board CV", rm["intra"]["cv"], rj["intra"]["cv"]),
        ("total stalls", rm["total_stalls"], rj["total_stalls"]),
        ("avg switch hops/msg", rm["avg_switch_hops"], rj["avg_switch_hops"]),
    ]
    print("  %-26s %14s %14s   %8s" % ("metric", "mesh", "jellyfish", "jf/mesh"))
    for name, m, j in rows:
        print("  %-26s %14.2f %14.2f   %7.2fx" % (name, m, j, ratio(j, m)))


def make_plot(rm, rj, path, title):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, axes = plt.subplots(1, 3, figsize=(16, 5))

    # (1) sorted inter-switch per-port load (log y): jelly head taller = hotspots
    ax = axes[0]
    for r, c, lab in ((rm, "#1f77b4", "mesh"), (rj, "#d62728", "jellyfish")):
        vals = sorted((p for p, _, cl, _, _ in r["_inter_ports"] if cl != NIC and p > 0),
                      reverse=True)
        ax.plot(range(len(vals)), vals, color=c, lw=1.6, label=lab)
    ax.set_yscale("log")
    ax.set_xlabel("links, sorted by load (busiest first)")
    ax.set_ylabel("bits sent on the link (log scale)")
    ax.set_title("How evenly is load spread across links?\n"
                 "(a tall, long head = a few links carry far more = hot-spots)")
    ax.legend()
    ax.grid(True, which="both", alpha=0.3)

    # (2) board->tree uplink load distribution (sorted)
    ax = axes[1]
    for r, c, lab in ((rm, "#1f77b4", "mesh"), (rj, "#d62728", "jellyfish")):
        vals = sorted(r["_uplinks"], reverse=True)
        ax.plot(range(len(vals)), vals, color=c, lw=1.8, label=lab)
    ax.set_xlabel("board→fat-tree uplinks, sorted by load")
    ax.set_ylabel("bits sent on the uplink")
    ax.set_title("Board→fat-tree uplink load\n"
                 "(flat = gateways share the load · spiky = funneled through one gateway)")
    ax.legend()
    ax.grid(True, alpha=0.3)

    # (3) row vs col uplink totals
    ax = axes[2]
    x = [0, 1]
    w = 0.35
    ax.bar([0 - w / 2, 1 - w / 2], [rm["row_uplink_pkts"], rm["col_uplink_pkts"]],
           w, color="#1f77b4", label="mesh")
    ax.bar([0 + w / 2, 1 + w / 2], [rj["row_uplink_pkts"], rj["col_uplink_pkts"]],
           w, color="#d62728", label="jellyfish")
    ax.set_xticks(x)
    ax.set_xticklabels(["row fat tree", "column fat tree"])
    ax.set_ylabel("total bits on board→tree uplinks")
    ax.set_title("Traffic split: row vs column fat tree\n(roughly equal is healthy)")
    ax.legend()
    ax.grid(True, axis="y", alpha=0.3)

    fig.suptitle(title, fontsize=13)
    fig.tight_layout(rect=[0, 0, 1, 0.96])
    fig.savefig(path, dpi=130)
    plt.close(fig)


def save_results_json(path, results, sim_times, board, glob, n):
    """Dump a serializable subset of each topology's results (scalars + sorted load
    vectors) so two separately-timed runs can be overlaid by plot_before_after.py."""
    out = {"board": board, "global": glob, "nodes": n, "topos": {}}
    for topo, r in results.items():
        inter = sorted((p for p, _, cl, _, _ in r["_inter_ports"] if cl != NIC and p > 0),
                       reverse=True)
        out["topos"][topo] = {
            "completion_us": sim_times.get(topo),
            "busiest_bits": r["busiest"][0],
            "uplink": r["uplink"],          # {n, max, mean, cv}
            "intra": r["intra"],            # {n, max, mean, cv}
            "avg_switch_hops": r["avg_switch_hops"],
            "delivered_bits": r["delivered"],
            "row_uplink_bits": r["row_uplink_pkts"],
            "col_uplink_bits": r["col_uplink_pkts"],
            "uplinks_sorted": sorted(r["_uplinks"], reverse=True),
            "inter_links_sorted": inter,
        }
    with open(path, "w") as f:
        json.dump(out, f)


# ---------------------------------------------------------------------------

def main():
    ap = ArgumentParser(description="Diagnose Jellyfish-vs-mesh HammingMesh routing load")
    ap.add_argument("--board_shape", default="8x8")
    ap.add_argument("--global_shape", default="4x4")
    ap.add_argument("--fat_tree_shape", default="1:1,64")
    ap.add_argument("--ft_nodes", type=int, default=0)
    ap.add_argument("--msg_size", type=int, default=2 ** 16,
                    help="AllPingPong message size in bytes (default 65536)")
    ap.add_argument("--topo", choices=["mesh", "jellyfish", "both"], default="both")
    ap.add_argument("--num_threads", type=int, default=1,
                    help="keep at 1: >1 threads splits/corrupts the per-port stats")
    ap.add_argument("--timeout", type=int, default=3600)
    ap.add_argument("--algorithm", default="min-adaptive",
                    help="merlin routing algorithm (e.g. min-adaptive, min-adaptive-nogl). "
                         "nogl disables the mesh's same-board fat-tree shortcut.")
    ap.add_argument("--tag", default="",
                    help="suffix for the output PNG: router_load_<board>_<global>_<tag>.png "
                         "(e.g. baseline / fixed) so before/after runs don't overwrite each other")
    ap.add_argument("--save_json", default="",
                    help="also dump per-topology results (scalars + sorted uplink/per-link "
                         "vectors) to this JSON path, for the before/after overlay plot")
    ap.add_argument("--no_plot", action="store_true")
    args = ap.parse_args()

    R, C = dims(args.board_shape)
    spb = R * C
    n = num_nodes(args.board_shape, args.global_shape)
    base = dict(board=args.board_shape, glob=args.global_shape,
                fat_tree_shape=args.fat_tree_shape, ft_nodes=args.ft_nodes,
                algorithm=args.algorithm)
    todo = ([("mesh", False), ("jellyfish", True)] if args.topo == "both"
            else [(args.topo, args.topo == "jellyfish")])

    print("Routing-load diagnosis: board %s, global %s (%d nodes), msg %s B" % (
        args.board_shape, args.global_shape, n, _fmt(args.msg_size)))
    pathlib.Path(OUT_DIR).mkdir(parents=True, exist_ok=True)

    results = {}
    sim_times = {}
    for topo, jelly in todo:
        cfg = dict(base, jellyfish=jelly)
        wd = os.path.join(OUT_DIR, "_work", topo)
        if os.path.isdir(wd):
            shutil.rmtree(wd)
        print("\n--- running %s ---" % topo)
        graph_json, stats_csv, sim_us = run_sst_stats(cfg, args.msg_size, args.num_threads, wd, args.timeout)
        sim_times[topo] = sim_us
        results[topo] = analyze(graph_json, stats_csv, spb)
        print("  completed: simulated time = %.3f us" % (sim_us or 0))
        report(topo, results[topo])

    if args.save_json:
        save_results_json(args.save_json, results, sim_times, args.board_shape, args.global_shape, n)
        print("\n-> saved results %s" % args.save_json)

    if "mesh" in results and "jellyfish" in results:
        mesh_us, jf_us = sim_times["mesh"], sim_times["jellyfish"]
        ratio = (jf_us / mesh_us) if mesh_us else 0
        print("\nsimulated completion time:  mesh = %.3f us   jellyfish = %.3f us   (jf/mesh = %.2fx)" % (
            mesh_us, jf_us, ratio))
        compare(results["mesh"], results["jellyfish"])
        if not args.no_plot:
            tag_sfx = ("_" + args.tag) if args.tag else ""
            tag_lbl = ("  ·  [%s]" % args.tag) if args.tag else ""
            png = os.path.join(OUT_DIR, "router_load_%s_%s%s.png"
                               % (args.board_shape, args.global_shape, tag_sfx))
            title = ("HammingMesh AllToAll load — 2D-mesh vs Jellyfish boards\n"
                     "board %s / global %s (%d nodes)  ·  completion: mesh %.0fµs vs "
                     "Jellyfish %.0fµs (%.2f× slower)%s"
                     % (args.board_shape, args.global_shape, n, mesh_us, jf_us, ratio, tag_lbl))
            make_plot(results["mesh"], results["jellyfish"], png, title)
            print("\n-> plot %s" % png)


if __name__ == "__main__":
    main()
