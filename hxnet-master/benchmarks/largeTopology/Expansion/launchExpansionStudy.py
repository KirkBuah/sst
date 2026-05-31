"""
Expansion efficiency study: Jellyfish vs 2D Mesh.

Runs three experiments using existing benchmark launchers:

  Experiment 1 — Throughput vs Node Count (AllToAll)
    board_shape=4x4, global_shape varies 2x2→16x16
    Topologies: mesh, jellyfish (default), jellyfish ft_nodes=1

  Experiment 2 — FT Gateway Density Tradeoff (AllToAll + RandomPerm)
    board_shape=4x4, global_shape=8x8 (1024 nodes), ft_nodes in {0, 1, 2}
    Jellyfish only

  Experiment 3 — Fixed Link Budget Scaling (AllToAll)
    Same as Exp 1 but jellyfish ft_nodes=1 only — most directly mirrors
    the Jellyfish paper's "same links, more servers" claim

Usage:
    python3 launchExpansionStudy.py
    python3 launchExpansionStudy.py --small_run
    python3 launchExpansionStudy.py --exp 1        # only experiment 1
    python3 launchExpansionStudy.py --exp 2        # only experiment 2
"""

import subprocess
import sys
import os
from argparse import ArgumentParser

# Paths to existing benchmark launchers (relative to this script's location)
SCRIPT_DIR   = os.path.dirname(os.path.abspath(__file__))
ALLTOALL_PY  = os.path.join(SCRIPT_DIR, "../AllToAll/launchAllToAll_large.py")
RANDPERM_PY  = os.path.join(SCRIPT_DIR, "../RandomPermutation/launchRandomPerm.py")

# Experiment 1 + 3: scale global_shape while board is fixed 4x4
SCALING_CONFIGS = [
    ("4x4", "2x2"),
    ("4x4", "4x4"),
    ("4x4", "8x8"),
    ("4x4", "16x16"),
]

# Experiment 2: fixed topology, sweep ft_nodes
FIXED_BOARD  = "4x4"
FIXED_GLOBAL = "8x8"
FT_NODES_SWEEP = [0, 1, 2]


def run(launcher, extra_args, num_threads, small_run, label):
    cmd = [sys.executable, launcher,
           "--num_threads", str(num_threads)]
    cmd += extra_args
    if small_run:
        cmd += ["--small_run"]
    print("\n" + "="*60)
    print("Running: %s" % label)
    print("  cmd: %s" % " ".join(cmd))
    print("="*60)
    result = subprocess.run(cmd, cwd=os.path.dirname(launcher))
    if result.returncode != 0:
        print("WARNING: launcher returned non-zero exit code %d" % result.returncode)


def exp1_scaling(num_threads, small_run):
    """AllToAll across node counts, all three topologies."""
    print("\n\n### Experiment 1: Throughput vs Node Count (AllToAll) ###")
    for board, glob in SCALING_CONFIGS:
        # Mesh
        run(ALLTOALL_PY,
            ["--board_shape", board, "--global_shape", glob],
            num_threads, small_run,
            "Mesh  board=%s global=%s" % (board, glob))
        # Jellyfish default (all border nodes are gateways)
        run(ALLTOALL_PY,
            ["--board_shape", board, "--global_shape", glob, "--jellyfish"],
            num_threads, small_run,
            "JF-default  board=%s global=%s" % (board, glob))
        # Jellyfish ft_nodes=1 (minimal gateways)
        run(ALLTOALL_PY,
            ["--board_shape", board, "--global_shape", glob,
             "--jellyfish", "--ft_nodes", "1"],
            num_threads, small_run,
            "JF-ft1  board=%s global=%s" % (board, glob))
        # Jellyfish ft_nodes=2
        run(ALLTOALL_PY,
            ["--board_shape", board, "--global_shape", glob,
             "--jellyfish", "--ft_nodes", "2"],
            num_threads, small_run,
            "JF-ft2  board=%s global=%s" % (board, glob))


def exp2_ft_density(num_threads, small_run):
    """AllToAll + RandomPerm at fixed topology, sweep ft_nodes."""
    print("\n\n### Experiment 2: FT Gateway Density Tradeoff ###")
    for ft in FT_NODES_SWEEP:
        base_args = ["--board_shape", FIXED_BOARD,
                     "--global_shape", FIXED_GLOBAL,
                     "--jellyfish"]
        if ft > 0:
            base_args += ["--ft_nodes", str(ft)]

        label_suffix = "ft_nodes=%d  board=%s global=%s" % (ft, FIXED_BOARD, FIXED_GLOBAL)

        run(ALLTOALL_PY, base_args, num_threads, small_run,
            "AllToAll  " + label_suffix)
        run(RANDPERM_PY, base_args, num_threads, small_run,
            "RandomPerm  " + label_suffix)


def main():
    parser = ArgumentParser(description="Jellyfish expansion efficiency study")
    parser.add_argument("--num_threads", type=int, default=8,
                        help="SST thread count passed to each launcher (default: 8)")
    parser.add_argument("--small_run", action="store_true",
                        help="Pass --small_run to each launcher (fewer message sizes)")
    parser.add_argument("--exp", type=int, choices=[1, 2], default=0,
                        help="Run only one experiment (1 or 2). Default: run all")
    args = parser.parse_args()

    if args.exp == 1:
        exp1_scaling(args.num_threads, args.small_run)
    elif args.exp == 2:
        exp2_ft_density(args.num_threads, args.small_run)
    else:
        exp1_scaling(args.num_threads, args.small_run)
        exp2_ft_density(args.num_threads, args.small_run)

    print("\n\nAll simulations finished. Run plotExpansion.py to generate plots.")


if __name__ == "__main__":
    main()
