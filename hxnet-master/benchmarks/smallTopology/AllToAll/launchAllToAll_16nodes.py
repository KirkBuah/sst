"""
AllToAll benchmark for HxMesh topologies with configurable dimensions.

Usage:
    python3 launchAllToAll_16nodes.py --board_shape 2x2 --global_shape 2x2
    python3 launchAllToAll_16nodes.py --board_shape 4x4 --global_shape 8x8 --small_run
    python3 launchAllToAll_16nodes.py --board_shape 2x2 --global_shape 2x2 --jellyfish
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

# Fat tree: single 64-port switch is more than enough for small global shapes
FAT_TREE_SHAPE = "1:1,64"

large_size = [2**4, 2**6, 2**8, 2**10, 2**12, 2**16, 2**20]
small_size = [2**6, 2**16]


def parse_shape(shape_str):
    """Parse a shape string like '2x2' into a list of ints [2, 2]."""
    return [int(x) for x in shape_str.split('x')]


def compute_num_nodes(board_shape, global_shape, hosts_per_rtr=1):
    """Compute total number of nodes from board and global shapes."""
    bd = parse_shape(board_shape)
    gl = parse_shape(global_shape)
    return bd[0] * bd[1] * gl[0] * gl[1] * hosts_per_rtr


def make_topo_name(board_shape, global_shape, jellyfish=False):
    """Generate output subfolder name from dimensions."""
    bd = parse_shape(board_shape)
    num_nodes = compute_num_nodes(board_shape, global_shape)
    name = "hx%d_%d" % (bd[0], num_nodes)
    if jellyfish:
        name += "_jellyfish"
    return name


def create_motif_load(name, board_shape, global_shape):
    pathlib.Path(motif_folder).mkdir(parents=True, exist_ok=True)
    nid_string = "[NID_LIST] generateNidList=generateNidListHx({}x{})\n".format(
        board_shape, global_shape
    )
    motif_content = [
        "[JOB_ID] 10\n",
        nid_string,
        "[MOTIF] Init\n",
        "[MOTIF] AllPingPong messageSize=11\n",
        "[MOTIF] Fini",
    ]
    with open(os.path.join(motif_folder, name), "w") as f:
        f.writelines(motif_content)


def run_simulation(args, msg_size, motif_name):
    ember_load = ember_load_folder + "emberLoad.py"
    location_motif = os.path.join(motif_folder, motif_name)

    topo_name = make_topo_name(args.board_shape, args.global_shape, args.jellyfish)

    # Ensure output dir exists
    out_dir = os.path.join(output_folder, topo_name)
    pathlib.Path(out_dir).mkdir(parents=True, exist_ok=True)
    output_result = os.path.join(out_dir, str(msg_size))

    jellyfish_flag = "--jellyfish " if args.jellyfish else ""

    launch_string = (
        '--num_threads={} '
        '--model-options="'
        '--param="nic:module=merlin.reorderlinkcontrol" '
        '--topo=hx '
        '--boardShape={} '
        '--globalShape={} '
        '--fatTreeShape={} '
        '--hostsPerRtr=1 '
        '{}'
        '--loadFile={}" '
        '{} > {}'
    ).format(
        args.num_threads,
        args.board_shape,
        args.global_shape,
        FAT_TREE_SHAPE,
        jellyfish_flag,
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
    num_nodes = compute_num_nodes(args.board_shape, args.global_shape)
    motif_name = "AllToAllTom_%d" % num_nodes
    create_motif_load(motif_name, args.board_shape, args.global_shape)

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
    parser = ArgumentParser(description="AllToAll benchmark for HxMesh with configurable dimensions")
    parser.add_argument("--board_shape", type=str, default="2x2",
                        help="Board shape as AxB (default: 2x2)")
    parser.add_argument("--global_shape", type=str, default="2x2",
                        help="Global shape as AxB (default: 2x2)")
    parser.add_argument("--num_threads", type=int, default=8,
                        help="Number of threads for SST (default: 8)")
    parser.add_argument("--small_run", action="store_true",
                        help="Run only 2 message sizes instead of 7")
    parser.add_argument("--jellyfish", action="store_true",
                        help="Use Jellyfish random graph as local board topology instead of 2D mesh")
    args = parser.parse_args()

    num_nodes = compute_num_nodes(args.board_shape, args.global_shape)
    print("Board shape: %s, Global shape: %s => %d nodes" % (args.board_shape, args.global_shape, num_nodes))
    main(args)
