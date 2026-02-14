"""
Minimal AllToAll benchmark for a 16-node HxMesh topology.
Board shape: 2x2, Global shape: 2x2 => 2*2*2*2 = 16 nodes.

Usage:
    python3 launchAllToAll_16nodes.py
    python3 launchAllToAll_16nodes.py --small_run
    python3 launchAllToAll_16nodes.py --num_threads 4
"""

import re
import subprocess
import pathlib
import os
import sys
from argparse import ArgumentParser

sys.path.append("../")
from general_bench import (
    check_if_exist, allocate_logic, output_folder, motif_folder, ember_load_folder
)

# --- Configuration for 16-node HxMesh ---
BOARD_SHAPE = "2x2"
GLOBAL_SHAPE = "2x2"
NUM_NODES = 16  # 2*2*2*2
TOPO_NAME = "hx2_16"  # output subfolder name
NID_STRING = "[NID_LIST] generateNidList=generateNidListHx({}x{})\n".format(
    BOARD_SHAPE, GLOBAL_SHAPE
)
# Fat tree: single 64-port switch is more than enough for 2x2 global
FAT_TREE_SHAPE = "1:1,64"

large_size = [2**4, 2**6, 2**8, 2**10, 2**12, 2**16, 2**20]
small_size = [2**6, 2**16]


def create_motif_load(name):
    pathlib.Path(motif_folder).mkdir(parents=True, exist_ok=True)
    motif_content = [
        "[JOB_ID] 10\n",
        NID_STRING,
        "[MOTIF] Init\n",
        "[MOTIF] AllPingPong messageSize=11\n",
        "[MOTIF] Fini",
    ]
    with open(os.path.join(motif_folder, name), "w") as f:
        f.writelines(motif_content)


def run_simulation(args, msg_size, motif_name):
    ember_load = ember_load_folder + "emberLoad.py"
    location_motif = os.path.join(motif_folder, motif_name)

    # Ensure output dir exists
    out_dir = os.path.join(output_folder, TOPO_NAME)
    pathlib.Path(out_dir).mkdir(parents=True, exist_ok=True)
    output_result = os.path.join(out_dir, str(msg_size))

    launch_string = (
        '--num_threads={} '
        '--model-options="'
        '--param="nic:module=merlin.reorderlinkcontrol" '
        '--topo=hx '
        '--boardShape={} '
        '--globalShape={} '
        '--fatTreeShape={} '
        '--hostsPerRtr=1 '
        '--loadFile={}" '
        '{} > {}'
    ).format(
        args.num_threads,
        BOARD_SHAPE,
        GLOBAL_SHAPE,
        FAT_TREE_SHAPE,
        location_motif,
        ember_load,
        output_result,
    )

    # Ensure SST's Python can find networkConfig.py etc. in the ember/test directory
    ember_test_dir = os.path.abspath(ember_load_folder)
    allocation_policy = "SST_NO_MEM=1"
    cmd = 'PYTHONPATH="{}" {} sst {}'.format(ember_test_dir, allocation_policy, launch_string)
    print("Running: {}".format(cmd))
    process = subprocess.Popen([cmd], shell=True)
    process.wait()
    return process.returncode


def main(args):
    motif_name = "AllToAllTom_16"
    create_motif_load(motif_name)

    if args.small_run:
        sizes = small_size
    else:
        sizes = large_size

    for msg_size in sizes:
        # Update the motif file with the current message size
        location_motif = os.path.join(motif_folder, motif_name)
        with open(location_motif, "r") as f:
            lines = f.readlines()

        new_lines = []
        for line in lines:
            line = re.sub(r"messageSize=\d+", "messageSize={}".format(msg_size), line)
            new_lines.append(line)

        with open(location_motif, "w") as f:
            f.writelines(new_lines)

        print("\n=== Message size: {} ===".format(msg_size))
        run_simulation(args, msg_size, motif_name)


if __name__ == "__main__":
    parser = ArgumentParser(description="AllToAll benchmark for 16-node HxMesh (2x2 board, 2x2 global)")
    parser.add_argument("--num_threads", type=int, default=8,
                        help="Number of threads for SST (default: 8)")
    parser.add_argument("--small_run", action="store_true",
                        help="Run only 2 message sizes instead of 7")
    args = parser.parse_args()
    main(args)
