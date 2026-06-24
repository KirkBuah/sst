"""
Standalone single-board AllToAll benchmark: 2D mesh vs Jellyfish.

Runs an AllToAll (AllPingPong) on each LOCAL board fabric in complete isolation
-- a single board, no fat tree, no global structure -- with the SAME node count:

  * mesh      : native merlin 2D mesh   (--topo=mesh,      DOR routing)
  * jellyfish : standalone 4-regular    (--topo=jellyfish, shortest-path routing)

Both go through the same ember harness with identical link/router parameters, so
the only difference is the intra-board fabric. See README.md.

Usage:
    uv run python launch_local_topos.py --shape 8x8
    uv run python launch_local_topos.py --shape 4x4 --small_run
    uv run python launch_local_topos.py --shape 8x8 --topos mesh

Outputs:  output/<topo>_<nodes>/<msg_size>   logs/<...>.log
Then:     uv run python parse_mesh_vs_jellyfish.py
"""

import os
import re
import sys
import pathlib
import subprocess
from datetime import datetime
from argparse import ArgumentParser

# Absolute path to the ember test dir (avoids the CWD-relative path issues that
# bit the earlier driver). emberLoad.py + networkConfig.py live here.
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
EMBER_TEST_DIR = os.path.abspath(os.path.join(
    SCRIPT_DIR, "..", "..", "..", "..",
    "sst-elements-library-11.1.0", "src", "sst", "elements", "ember", "test"))
EMBER_LOAD = os.path.join(EMBER_TEST_DIR, "emberLoad.py")

OUTPUT_FOLDER = os.path.join(SCRIPT_DIR, "output")
MOTIF_FOLDER = os.path.join(SCRIPT_DIR, "loads")
LOG_FOLDER = os.path.join(SCRIPT_DIR, "logs")

LARGE_SIZES = [2**6, 2**8, 2**12, 2**16, 2**18, 2**20]
SMALL_SIZES = [2**8, 2**16]


def parse_shape(shape_str):
    return [int(x) for x in shape_str.split("x")]


def num_nodes(shape_str):
    n = 1
    for d in parse_shape(shape_str):
        n *= d
    return n


def write_motif(path, n_nodes, msg_size):
    lines = [
        "[JOB_ID] 10\n",
        "[NID_LIST] generateNidList=generateNidListRange(0,{})\n".format(n_nodes),
        "[MOTIF] Init\n",
        "[MOTIF] AllPingPong messageSize={}\n".format(msg_size),
        "[MOTIF] Fini",
    ]
    with open(path, "w") as f:
        f.writelines(lines)


def run_one(topo, shape, msg_size, n_nodes, num_threads, logf):
    out_dir = os.path.join(OUTPUT_FOLDER, "{}_{}".format(topo, n_nodes))
    pathlib.Path(out_dir).mkdir(parents=True, exist_ok=True)
    out_file = os.path.join(out_dir, str(msg_size))

    motif_path = os.path.join(MOTIF_FOLDER, "AllToAll_{}_{}".format(topo, n_nodes))
    write_motif(motif_path, n_nodes, msg_size)

    model_options = (
        '--param="nic:module=merlin.reorderlinkcontrol" '
        '--topo={topo} '
        '--shape={shape} '
        '--hostsPerRtr=1 '
        '--loadFile={motif}'
    ).format(topo=topo, shape=shape, motif=motif_path)

    cmd = (
        'PYTHONPATH="{pp}" SST_NO_MEM=1 sst '
        '--num_threads={nt} '
        '--model-options="{opts}" '
        '{ember} > {out}'
    ).format(pp=EMBER_TEST_DIR, nt=num_threads, opts=model_options,
             ember=EMBER_LOAD, out=out_file)

    logf.write("\n=== {} | shape={} | msg={} ===\n".format(topo, shape, msg_size))
    logf.write(cmd + "\n")
    logf.flush()
    print("Running: {} shape={} msg={}".format(topo, shape, msg_size))

    proc = subprocess.run(cmd, shell=True, stderr=subprocess.STDOUT,
                          stdout=logf)
    logf.flush()

    # The build/sim can fail while sst still returns 0 in some paths, so verify
    # the output actually completed.
    ok = False
    aborted = False
    try:
        with open(out_file) as f:
            text = f.read()
        ok = ("Simulation is complete" in text) and ("STATS " in text)
        aborted = "FATAL" in text or "correct port" in text or "Traceback" in text
    except IOError:
        pass

    status = "OK" if ok else ("ABORTED" if (aborted or proc.returncode != 0) else "NO-DATA")
    print("  -> {} ({})".format(status, out_file))
    logf.write("  -> {} (rc={})\n".format(status, proc.returncode))
    return ok


def main():
    parser = ArgumentParser(description="Standalone single-board mesh vs jellyfish AllToAll")
    parser.add_argument("--shape", type=str, default="8x8",
                        help="Board shape NxM, applied to both fabrics (default 8x8)")
    parser.add_argument("--topos", type=str, default="mesh,jellyfish",
                        help="Comma-separated topos to run (default: mesh,jellyfish)")
    parser.add_argument("--small_run", action="store_true",
                        help="Use 2 message sizes instead of the full sweep")
    parser.add_argument("--num_threads", type=int, default=os.cpu_count(),
                        help="SST threads (default: all cores)")
    args = parser.parse_args()

    topos = [t.strip() for t in args.topos.split(",") if t.strip()]
    n_nodes = num_nodes(args.shape)
    sizes = SMALL_SIZES if args.small_run else LARGE_SIZES

    for d in (OUTPUT_FOLDER, MOTIF_FOLDER, LOG_FOLDER):
        pathlib.Path(d).mkdir(parents=True, exist_ok=True)

    log_path = os.path.join(
        LOG_FOLDER, "run_{}.log".format(datetime.now().strftime("%Y-%m-%d_%H-%M-%S")))

    print("Shape {} => {} nodes per fabric. Topos: {}. Sizes: {}".format(
        args.shape, n_nodes, topos, sizes))
    print("Log: {}".format(log_path))

    all_ok = True
    with open(log_path, "w") as logf:
        logf.write("Standalone single-board AllToAll: {}\n".format(topos))
        logf.write("Shape {} => {} nodes, threads={}, sizes={}\n".format(
            args.shape, n_nodes, args.num_threads, sizes))
        for topo in topos:
            for msg_size in sizes:
                ok = run_one(topo, args.shape, msg_size, n_nodes,
                             args.num_threads, logf)
                all_ok = all_ok and ok

    print("\nDone. {}".format(
        "All runs completed." if all_ok else "Some runs FAILED -- check the log above."))
    print("Now run:  uv run python parse_mesh_vs_jellyfish.py")
    sys.exit(0 if all_ok else 1)


if __name__ == "__main__":
    main()
