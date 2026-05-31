"""
Random Permutation benchmark for HxMesh topologies with configurable dimensions.

Usage:
    python3 launchRandomPerm.py --board_shape 4x4 --global_shape 8x8
    python3 launchRandomPerm.py --board_shape 4x4 --global_shape 8x8 --jellyfish
"""

import re
import subprocess
import pathlib
import os
import sys
from argparse import ArgumentParser

sys.path.append("../")
from general_bench import (
    check_if_exist, allocate_logic, output_folder, motif_folder, ember_load_folder,
    run_cluster,
)

FAT_TREE_SHAPE = "1:1,64"

# Single "size" entry — RandomPerm uses pre-generated CSV pairs, not variable msg sizes
sizes = [512]


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


def generate_partners(num_nodes):
    """Generate random permutation CSV files for the given node count."""
    import random
    import csv

    path = pathlib.Path("input_generic")
    path.mkdir(parents=True, exist_ok=True)

    num_iterations_per_node = 1
    min_msg = 2**26
    max_msg = 2**26

    sending_to_list = [[] for _ in range(num_nodes)]
    receiving_from_list = [[] for _ in range(num_nodes)]
    nodes_list = list(range(num_nodes))

    for _ in range(num_iterations_per_node):
        random.shuffle(nodes_list)
        for num_rank in range(num_nodes // 2):
            size = random.randint(min_msg, max_msg)
            sleep = 0

            sending_from = nodes_list[num_rank]
            sending_to = nodes_list[num_rank + (num_nodes // 2)]

            sending_to_list[sending_from].append((sending_to, size, sleep))
            receiving_from_list[sending_to].append((sending_from, size, sleep))

            sending_to_list[sending_to].append((sending_from, size, sleep))
            receiving_from_list[sending_from].append((sending_to, size, sleep))

    for rank in range(num_nodes):
        with open(str(path / ("send_%d.csv" % rank)), 'w', newline='') as f:
            writer = csv.writer(f)
            for entry in sending_to_list[rank]:
                writer.writerow(entry)

        with open(str(path / ("read_%d.csv" % rank)), 'w', newline='') as f:
            writer = csv.writer(f)
            for entry in receiving_from_list[rank]:
                writer.writerow(entry)

    print("Generated random permutation CSV files for %d nodes in input_generic/" % num_nodes)


def create_motif_load(name, board_shape, global_shape):
    pathlib.Path(motif_folder).mkdir(parents=True, exist_ok=True)
    nid_string = "[NID_LIST] generateNidList=generateNidListHx({}x{})\n".format(
        board_shape, global_shape
    )
    motif_content = [
        "[JOB_ID] 10\n",
        nid_string,
        "[MOTIF] Init\n",
        "[MOTIF] RandomPerm is_dragonfly=0\n",
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

    if args.env in ("cluster", "slurm", "ault", "slimfly"):
        run_cluster(args, launch_string, msg_size, "RandomPerm", topo_name)
    else:
        ember_test_dir = os.path.abspath(ember_load_folder)
        allocation_policy = "SST_NO_MEM=1"
        cmd = 'PYTHONPATH="{}" {} sst {}'.format(ember_test_dir, allocation_policy, launch_string)
        print("Running: {}".format(cmd))
        process = subprocess.Popen([cmd], shell=True)
        process.wait()
        return process.returncode


def main(args):
    num_nodes = compute_num_nodes(args.board_shape, args.global_shape)

    # Generate random permutation partner CSVs
    generate_partners(num_nodes)

    motif_name = "Permutation_%d" % num_nodes
    create_motif_load(motif_name, args.board_shape, args.global_shape)

    for msg_size in sizes:
        print("\n=== Random Permutation (size entry: %d) ===" % msg_size)
        run_simulation(args, msg_size, motif_name)


if __name__ == "__main__":
    parser = ArgumentParser(description="Random Permutation benchmark for HxMesh with configurable dimensions")
    parser.add_argument("--board_shape", type=str, default="4x4",
                        help="Board shape as AxB (default: 4x4)")
    parser.add_argument("--global_shape", type=str, default="8x8",
                        help="Global shape as AxB (default: 8x8)")
    parser.add_argument("--num_threads", type=int, default=8,
                        help="Number of threads for SST (default: 8)")
    parser.add_argument("--jellyfish", action="store_true",
                        help="Use Jellyfish random graph as local board topology")
    parser.add_argument("--ft_nodes", type=int, default=0,
                        help="Number of random fat tree gateways per direction per board "
                             "(Jellyfish only; 0 = border nodes, default)")
    parser.add_argument("--env", type=str, help="Local or Cluster", default="",
                        choices=["cluster", "daint", "ault", "local", "slimfly", ""])
    parser.add_argument("--nodes", type=int, help="Number of nodes for cluster", default=8)
    parser.add_argument("--cpus_per_task", type=str, help="CPUs per task for cluster", default="8")
    parser.add_argument("--mem", type=str, help="Memory per node for cluster", default="16G")
    parser.add_argument("--hostfile", type=str, help="Hostfile name for Slimfly", default="hostfile")
    args = parser.parse_args()

    num_nodes = compute_num_nodes(args.board_shape, args.global_shape)
    print("Board shape: %s, Global shape: %s => %d nodes" % (args.board_shape, args.global_shape, num_nodes))
    if args.jellyfish and args.ft_nodes > 0:
        print("Jellyfish FT gateways per direction: %d" % args.ft_nodes)
    main(args)
