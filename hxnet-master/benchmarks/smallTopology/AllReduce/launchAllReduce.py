"""
AllReduce benchmark for HxMesh topologies with configurable dimensions.

Usage:
    python3 launchAllReduce.py --board_shape 2x2 --global_shape 2x2 --small_run
    python3 launchAllReduce.py --board_shape 4x4 --global_shape 4x4 --jellyfish --small_run
    python3 launchAllReduce.py --board_shape 2x2 --global_shape 2x2 --ring_variant ring05d

Ring variants:
    ring05d   - Baseline unidirectional ring (0.5D)
    ring1d    - Bidirectional 1D ring
    ring2d    - 2D bidirectional rings along rows and columns (default)
    ring2drev - Revised 2D: scatter X, reduce Y, gather X
    ring25d   - Topology-aware Hamiltonian cycles on 2D torus (2.5D)
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

FAT_TREE_SHAPE = "1:1,64"

# Motif class names as registered in SST
RING_VARIANTS = {
    "ring05d":   "RingAllreduce05D",
    "ring1d":    "RingAllreduce1D",
    "ring2d":    "RingAllreduce2D",
    "ring2drev": "RingAllreduceRev",
    "ring25d":   "RingAllreduce25D",
}

large_sizes = [2**15, 2**19, 2**21, 2**23, 2**25, 2**27, 2**29]
small_sizes = [2**15, 2**19, 2**21, 2**23]


def parse_shape(shape_str):
    return [int(x) for x in shape_str.split('x')]


def compute_num_nodes(board_shape, global_shape, hosts_per_rtr=1):
    bd = parse_shape(board_shape)
    gl = parse_shape(global_shape)
    return bd[0] * bd[1] * gl[0] * gl[1] * hosts_per_rtr


def make_topo_name(board_shape, global_shape, jellyfish=False, ft_nodes=0):
    bd = parse_shape(board_shape)
    num_nodes = compute_num_nodes(board_shape, global_shape)
    name = "hx%d_%d" % (bd[0], num_nodes)
    if jellyfish:
        name += "_jellyfish"
        if ft_nodes > 0:
            name += "_ft%d" % ft_nodes
    return name


def create_motif_load(name, num_nodes, board_shape, global_shape, ring_variant):
    pathlib.Path(motif_folder).mkdir(parents=True, exist_ok=True)
    nid_string = "[NID_LIST] generateNidList=generateNidListHx({}x{})\n".format(
        board_shape, global_shape
    )
    motif_class = RING_VARIANTS[ring_variant]
    motif_content = [
        "[JOB_ID] 10\n",
        nid_string,
        "[MOTIF] Init\n",
        "[MOTIF] %s count=512 aggregation_cost_ns=0 blocking=true\n" % motif_class,
        "[MOTIF] Fini",
    ]
    with open(os.path.join(motif_folder, name), "w") as f:
        f.writelines(motif_content)


def run_simulation(args, msg_size, motif_name):
    ember_load = ember_load_folder + "emberLoad.py"
    location_motif = os.path.join(motif_folder, motif_name)

    topo_name = make_topo_name(args.board_shape, args.global_shape, args.jellyfish, args.ft_nodes)

    out_dir = os.path.join(output_folder, topo_name)
    pathlib.Path(out_dir).mkdir(parents=True, exist_ok=True)
    output_result = os.path.join(out_dir, str(msg_size))

    jellyfish_flag = "--jellyfish " if args.jellyfish else ""
    ft_nodes_flag = "--ftNodes={} ".format(args.ft_nodes) \
        if (args.jellyfish and args.ft_nodes > 0) else ""

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
        '{}'
        '--loadFile={}" '
        '{} > {}'
    ).format(
        args.num_threads,
        args.board_shape,
        args.global_shape,
        FAT_TREE_SHAPE,
        jellyfish_flag,
        ft_nodes_flag,
        location_motif,
        ember_load,
        output_result,
    )

    ember_test_dir = os.path.abspath(ember_load_folder)
    allocation_policy = "SST_NO_MEM=1"
    cmd = 'PYTHONPATH="{}" {} sst {}'.format(ember_test_dir, allocation_policy, launch_string)
    print("Running: {}".format(cmd))
    process = subprocess.Popen([cmd], shell=True)
    process.wait()
    return process.returncode


def main(args):
    num_nodes = compute_num_nodes(args.board_shape, args.global_shape)
    motif_name = "AllReduceRing_%d" % num_nodes
    create_motif_load(motif_name, num_nodes, args.board_shape, args.global_shape, args.ring_variant)

    if args.small_run:
        sizes = small_sizes
    else:
        sizes = large_sizes

    for msg_size in sizes:
        location_motif = os.path.join(motif_folder, motif_name)
        with open(location_motif, "r") as f:
            lines = f.readlines()

        new_lines = []
        for line in lines:
            line = re.sub(r"count=\d+", "count={}".format(msg_size), line)
            new_lines.append(line)

        with open(location_motif, "w") as f:
            f.writelines(new_lines)

        print("\n=== Count: {} ===".format(msg_size))
        run_simulation(args, msg_size, motif_name)


if __name__ == "__main__":
    parser = ArgumentParser(description="AllReduce benchmark for HxMesh with configurable dimensions")
    parser.add_argument("--board_shape", type=str, default="2x2",
                        help="Board shape as AxB (default: 2x2)")
    parser.add_argument("--global_shape", type=str, default="2x2",
                        help="Global shape as AxB (default: 2x2)")
    parser.add_argument("--num_threads", type=int, default=8,
                        help="Number of threads for SST (default: 8)")
    parser.add_argument("--small_run", action="store_true",
                        help="Run only 4 sizes instead of 7")
    parser.add_argument("--jellyfish", action="store_true",
                        help="Use Jellyfish random graph as local board topology")
    parser.add_argument("--ft_nodes", type=int, default=0,
                        help="Number of random fat tree gateways per direction per board "
                             "(Jellyfish only; 0 = border nodes, default)")
    parser.add_argument("--ring_variant", type=str, default="ring2d",
                        choices=list(RING_VARIANTS.keys()),
                        help="Ring allreduce variant (default: ring2d)")
    args = parser.parse_args()

    num_nodes = compute_num_nodes(args.board_shape, args.global_shape)
    print("Board shape: %s, Global shape: %s => %d nodes" % (args.board_shape, args.global_shape, num_nodes))
    print("Ring variant: %s (%s)" % (args.ring_variant, RING_VARIANTS[args.ring_variant]))
    if args.jellyfish and args.ft_nodes > 0:
        print("Jellyfish FT gateways per direction: %d" % args.ft_nodes)
    main(args)
