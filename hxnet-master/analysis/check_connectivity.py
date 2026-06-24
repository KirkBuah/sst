"""
Connectivity & routing-reachability check for a (Jellyfish or mesh) HammingMesh.

Both checks operate on what SST actually builds (no Python reconstruction of the
topology or routing):

  Part A - physical connectivity (BFS):
      `sst --run-mode=init --output-json` dumps the elaborated component+link
      graph WITHOUT running a simulation. We BFS it and report whether every
      switch and endpoint is in a single connected component.

  Part B - routing reachability:
      Run a real AllToAll (AllPingPong) at a tiny message size and verify SST's
      router actually delivered between every pair: the run must complete and
      every NIC must receive the same (full) byte total. A short/ missing NIC =>
      some sender could not reach it; a hang/timeout => routing deadlock.

The Jellyfish graph is generated with an UNSEEDED RNG in pymerlin.py, so each
build is a different random instance; --builds R repeats to check it is *always*
connected/routable.

Usage:
    uv run python check_connectivity.py --board_shape 2x2 --global_shape 2x2 --jellyfish
    uv run python check_connectivity.py --board_shape 4x4 --global_shape 4x4 --jellyfish --ft_nodes 1 --builds 5
    uv run python check_connectivity.py --board_shape 4x4 --global_shape 4x4 --suite --builds 3
"""

import os
import re
import sys
import json
import shutil
import pathlib
import subprocess
from collections import defaultdict, Counter
from argparse import ArgumentParser

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
EMBER_TEST_DIR = os.path.abspath(os.path.join(
    SCRIPT_DIR, "..", "sst-elements-library-11.1.0",
    "src", "sst", "elements", "ember", "test"))
EMBER_LOAD = os.path.join(EMBER_TEST_DIR, "emberLoad.py")
WORK_DIR = os.path.join(SCRIPT_DIR, "output", "connectivity")


def num_nodes(board, glob):
    b = [int(x) for x in board.split("x")]
    g = [int(x) for x in glob.split("x")]
    return b[0] * b[1] * g[0] * g[1]


def write_motif(path, board, glob, msg_size):
    nid = "generateNidListHx({}x{})".format(board, glob)
    with open(path, "w") as f:
        f.write("[JOB_ID] 10\n")
        f.write("[NID_LIST] generateNidList=%s\n" % nid)
        f.write("[MOTIF] Init\n")
        f.write("[MOTIF] AllPingPong messageSize=%d\n" % msg_size)
        f.write("[MOTIF] Fini")


def model_options(cfg, motif_path, extra=""):
    opts = (
        '--param="nic:module=merlin.reorderlinkcontrol" '
        '--topo=hx '
        '--boardShape={board} '
        '--globalShape={glob} '
        '--fatTreeShape={ft} '
        '--hostsPerRtr=1 '
    ).format(board=cfg["board"], glob=cfg["glob"], ft=cfg["fat_tree_shape"])
    if cfg["jellyfish"]:
        opts += "--jellyfish "
        if cfg["ft_nodes"] > 0:
            opts += "--ftNodes=%d " % cfg["ft_nodes"]
    opts += extra
    opts += "--loadFile=%s" % motif_path
    return opts


def run_sst(model_opts, num_threads, out_path, err_path, extra_sst_args="", timeout=900):
    """Run sst (stdout->out_path, stderr->err_path). Returns (returncode, timed_out)."""
    cmd = (
        'PYTHONPATH="{pp}" SST_NO_MEM=1 sst {extra} --num_threads={nt} '
        '--model-options="{opts}" {ember} > {out} 2> {err}'
    ).format(pp=EMBER_TEST_DIR, extra=extra_sst_args, nt=num_threads,
             opts=model_opts, ember=EMBER_LOAD, out=out_path, err=err_path)
    try:
        p = subprocess.run(cmd, shell=True, timeout=timeout)
        return p.returncode, False
    except subprocess.TimeoutExpired:
        return None, True


def _classify_crash(rc, err_path):
    """Return a short crash label from return code + stderr, or None."""
    txt = ""
    if err_path and os.path.isfile(err_path):
        txt = open(err_path, errors="replace").read()
    low = txt.lower()
    if rc in (139, -11) or "segmentation" in low or "signal: segmentation" in low:
        return "SEGFAULT in SST routing"
    if "fatal" in low or "correct port" in low:
        first = next((ln for ln in txt.splitlines() if "FATAL" in ln or "correct port" in ln), "")
        return "SST FATAL: %s" % first.strip()[:120]
    if rc not in (0, None):
        return "SST exited rc=%s" % rc
    return None


# ---------------------------------------------------------------------------
# Part A: physical connectivity from the SST-dumped graph
# ---------------------------------------------------------------------------

def _canon(ref):
    # link endpoints may be "comp:sub[..]:.." -> the component is the part before ':'
    return ref.split(":")[0]


def check_physical(cfg, build_dir, num_threads):
    """Dump the SST graph (no sim) and BFS it. Returns a result dict."""
    motif = os.path.join(build_dir, "motif")
    write_motif(motif, cfg["board"], cfg["glob"], 8)
    graph_json = os.path.join(build_dir, "graph.json")
    opts = model_options(cfg, motif)
    # --run-mode=init builds + dumps the graph, then SST tears down (a known
    # firefly-Nic teardown crash may follow AFTER the JSON is written), so we
    # check the file, not the return code.
    run_sst(opts, num_threads, os.path.join(build_dir, "init.log"),
            os.path.join(build_dir, "init.err"),
            extra_sst_args="--run-mode=init --output-json=%s" % graph_json,
            timeout=600)

    if not os.path.isfile(graph_json) or os.path.getsize(graph_json) == 0:
        return {"ok": False, "error": "no graph.json produced"}
    try:
        d = json.load(open(graph_json))
    except ValueError as e:
        return {"ok": False, "error": "bad json: %s" % e}

    ctype = {c["name"]: c.get("type", "") for c in d["components"]}
    adj = defaultdict(set)
    nodes = set(ctype)
    for l in d["links"]:
        a, b = _canon(l["left"]), _canon(l["right"])
        adj[a].add(b)
        adj[b].add(a)
        nodes.add(a)
        nodes.add(b)

    # connected components (BFS)
    seen = set()
    comps = []
    for start in nodes:
        if start in seen:
            continue
        stack = [start]
        comp = set()
        while stack:
            n = stack.pop()
            if n in seen:
                continue
            seen.add(n)
            comp.add(n)
            stack.extend(adj[n] - seen)
        comps.append(comp)

    endpoints = [n for n in nodes if ctype.get(n) == "ember.EmberEngine"]
    routers = [n for n in nodes if ctype.get(n) == "merlin.hr_router"]
    main = max(comps, key=len) if comps else set()
    in_main = sum(e in main for e in endpoints)

    isolated = []
    if len(comps) > 1:
        for comp in comps:
            if comp is main:
                continue
            eps = [n for n in comp if ctype.get(n) == "ember.EmberEngine"]
            rtrs = [n for n in comp if ctype.get(n) == "merlin.hr_router"]
            isolated.append({"size": len(comp), "endpoints": sorted(eps),
                             "routers": sorted(rtrs)})

    return {
        "ok": True,
        "connected": len(comps) == 1,
        "n_components": len(comps),
        "n_routers": len(routers),
        "n_endpoints": len(endpoints),
        "endpoints_in_main": in_main,
        "isolated": isolated,
    }


# ---------------------------------------------------------------------------
# Part B: routing reachability from a real AllToAll run
# ---------------------------------------------------------------------------

NIC_RE = re.compile(r"Nic (\d+) received (\d+) bytes")


def check_routing(cfg, build_dir, num_threads, msg_size, n_nodes, timeout):
    motif = os.path.join(build_dir, "motif_run")
    write_motif(motif, cfg["board"], cfg["glob"], msg_size)
    out = os.path.join(build_dir, "alltoall.out")
    err = os.path.join(build_dir, "alltoall.err")
    opts = model_options(cfg, motif)
    rc, timed_out = run_sst(opts, num_threads, out, err, timeout=timeout)

    if timed_out:
        return {"ok": True, "routable": False,
                "reason": "TIMEOUT after %ds (likely routing deadlock)" % timeout,
                "received": 0, "expected": n_nodes}

    text = ""
    if os.path.isfile(out):
        text = open(out, errors="replace").read()
    complete = "Simulation is complete" in text
    received = {int(m.group(1)): int(m.group(2)) for m in NIC_RE.finditer(text)}

    if not received:
        crash = _classify_crash(rc, err)
        reason = crash if crash else "no NIC delivery (complete=%s, rc=%s)" % (complete, rc)
        return {"ok": True, "routable": False,
                "reason": reason, "received": 0, "expected": n_nodes}

    # In all-to-all every node receives the same total from its N-1 peers.
    full = Counter(received.values()).most_common(1)[0][0]
    got_full = [nid for nid, b in received.items() if b == full]
    short = sorted(nid for nid, b in received.items() if b < full)
    missing = sorted(set(range(n_nodes)) - set(received))
    routable = complete and len(got_full) == n_nodes and not short and not missing

    reason = "ok" if routable else \
        "complete=%s nics=%d/%d short=%s missing=%s" % (
            complete, len(received), n_nodes, short[:8], missing[:8])
    return {"ok": True, "routable": routable, "reason": reason,
            "received": len(got_full), "expected": n_nodes,
            "full_bytes": full, "short": short, "missing": missing,
            "complete": complete}


# ---------------------------------------------------------------------------

def run_config(cfg, builds, num_threads, msg_size, timeout):
    n = num_nodes(cfg["board"], cfg["glob"])
    label = cfg["label"]
    print("\n" + "=" * 70)
    print("CONFIG: %s  (board %s, global %s, %d nodes)" % (
        label, cfg["board"], cfg["glob"], n))
    print("=" * 70)

    conn_ok = 0
    route_ok = 0
    for b in range(builds):
        build_dir = os.path.join(WORK_DIR, cfg["dirname"], "build%d" % b)
        if os.path.isdir(build_dir):
            shutil.rmtree(build_dir)
        pathlib.Path(build_dir).mkdir(parents=True, exist_ok=True)

        pa = check_physical(cfg, build_dir, num_threads)
        if not pa["ok"]:
            print("  build %d: Part A FAILED to produce graph: %s" % (b, pa["error"]))
            continue
        connected = pa["connected"]
        conn_ok += connected
        a_msg = "connected: %s (%d component%s, %d/%d endpoints in main)" % (
            "YES" if connected else "NO", pa["n_components"],
            "" if pa["n_components"] == 1 else "s",
            pa["endpoints_in_main"], pa["n_endpoints"])

        pb = check_routing(cfg, build_dir, num_threads, msg_size, n, timeout)
        routable = pb["routable"]
        route_ok += routable
        b_msg = "routable: %s (%d/%d nics got all data; %s)" % (
            "YES" if routable else "NO", pb["received"], pb["expected"], pb["reason"])

        print("  build %d: %s" % (b, a_msg))
        print("           %s" % b_msg)
        if not connected and pa.get("isolated"):
            for iso in pa["isolated"]:
                print("           isolated component: %d nodes, endpoints=%s" % (
                    iso["size"], iso["endpoints"][:12]))

    print("  -> SUMMARY %s: connected %d/%d, routable %d/%d" % (
        label, conn_ok, builds, route_ok, builds))
    return conn_ok, route_ok


def main():
    ap = ArgumentParser(description="HammingMesh connectivity + routing reachability check")
    ap.add_argument("--board_shape", default="4x4")
    ap.add_argument("--global_shape", default="4x4")
    ap.add_argument("--fat_tree_shape", default="1:1,64")
    ap.add_argument("--jellyfish", action="store_true")
    ap.add_argument("--ft_nodes", type=int, default=0)
    ap.add_argument("--builds", type=int, default=3,
                    help="random builds per config (jellyfish RNG is unseeded)")
    ap.add_argument("--msg_size", type=int, default=8,
                    help="AllToAll message size for the routing check (bytes)")
    ap.add_argument("--num_threads", type=int, default=min(8, os.cpu_count() or 1))
    ap.add_argument("--timeout", type=int, default=900,
                    help="per-AllToAll-run timeout in seconds (deadlock guard)")
    ap.add_argument("--suite", action="store_true",
                    help="run mesh control + jellyfish ft0/ft1/ft2 for the given shapes")
    args = ap.parse_args()

    base = dict(board=args.board_shape, glob=args.global_shape,
                fat_tree_shape=args.fat_tree_shape)

    if args.suite:
        configs = [
            dict(base, jellyfish=False, ft_nodes=0, label="MESH (control)", dirname="mesh"),
            dict(base, jellyfish=True, ft_nodes=0, label="JELLYFISH ft0 (border)", dirname="jelly_ft0"),
            dict(base, jellyfish=True, ft_nodes=1, label="JELLYFISH ft1", dirname="jelly_ft1"),
            dict(base, jellyfish=True, ft_nodes=2, label="JELLYFISH ft2", dirname="jelly_ft2"),
        ]
    else:
        if args.jellyfish:
            lbl = "JELLYFISH ft%d" % args.ft_nodes
            dn = "jelly_ft%d" % args.ft_nodes
        else:
            lbl, dn = "MESH", "mesh"
        configs = [dict(base, jellyfish=args.jellyfish, ft_nodes=args.ft_nodes,
                        label=lbl, dirname=dn)]

    pathlib.Path(WORK_DIR).mkdir(parents=True, exist_ok=True)
    results = []
    for cfg in configs:
        c, r = run_config(cfg, args.builds, args.num_threads, args.msg_size, args.timeout)
        results.append((cfg["label"], c, r))

    print("\n" + "#" * 70)
    print("OVERALL (board %s, global %s, %d builds each)" % (
        args.board_shape, args.global_shape, args.builds))
    for label, c, r in results:
        print("  %-26s connected %d/%d   routable %d/%d" % (label, c, args.builds, r, args.builds))


if __name__ == "__main__":
    main()
