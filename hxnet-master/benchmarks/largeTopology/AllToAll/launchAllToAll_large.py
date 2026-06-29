"""
AllToAll benchmark for HxMesh topologies with configurable dimensions.

Usage:
    python3 launchAllToAll_large.py --board_shape 4x4 --global_shape 8x8
    python3 launchAllToAll_large.py --board_shape 4x4 --global_shape 8x8 --small_run
    python3 launchAllToAll_large.py --board_shape 4x4 --global_shape 8x8 --jellyfish
"""

import re
import subprocess
import pathlib
import os
import sys
from argparse import ArgumentParser

sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from general_bench import (
    check_if_exist, allocate_logic, output_folder, motif_folder, ember_load_folder,
    run_cluster,
)

# Fat tree: single 64-port switch is more than enough for small global shapes
FAT_TREE_SHAPE = "1:1,64"

large_size = [2**6, 2**8, 2**12, 2**16, 2**18, 2**20]
small_size = [2**8, 2**16]


def parse_shape(shape_str):
    """Parse a shape string like '4x4' into a list of ints [4, 4]."""
    return [int(x) for x in shape_str.split('x')]


def compute_num_nodes(board_shape, global_shape, hosts_per_rtr=1):
    """Compute total number of nodes from board and global shapes."""
    bd = parse_shape(board_shape)
    gl = parse_shape(global_shape)
    return bd[0] * bd[1] * gl[0] * gl[1] * hosts_per_rtr


def make_topo_name(board_shape, global_shape, jellyfish=False, ft_nodes=0):
    """Generate output subfolder name from dimensions."""
    bd = parse_shape(board_shape)
    num_nodes = compute_num_nodes(board_shape, global_shape)
    name = "hx%d_%d" % (bd[0], num_nodes)
    if jellyfish:
        name += "_jellyfish"
        if ft_nodes > 0:
            name += "_ft%d" % ft_nodes
    return name


def make_seed_subdir(graph_seed, gateway_seed):
    """Per-seed output sub-folder so multi-seed runs do not overwrite each other."""
    return "g%d_w%d" % (graph_seed, gateway_seed)


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

    topo_name = make_topo_name(args.board_shape, args.global_shape, args.jellyfish, args.ft_nodes)

    # Ensure output dir exists. For Jellyfish runs the seeds get their own sub-folder so
    # a multi-seed sweep keeps every run side by side (mesh is deterministic -> no subdir).
    out_dir = os.path.join(output_folder, topo_name)
    if args.jellyfish:
        out_dir = os.path.join(out_dir, make_seed_subdir(args.graph_seed, args.gateway_seed))
    pathlib.Path(out_dir).mkdir(parents=True, exist_ok=True)
    output_result = os.path.join(out_dir, str(msg_size))

    jellyfish_flag = "--jellyfish " if args.jellyfish else ""
    ft_nodes_flag = "--ftNodes={} ".format(args.ft_nodes) \
        if (args.jellyfish and args.ft_nodes > 0) else ""
    seed_flags = "--jellyfishSeed={} --gatewaySeed={} ".format(
        args.graph_seed, args.gateway_seed) if args.jellyfish else ""

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
        seed_flags,
        location_motif,
        ember_load,
        output_result,
    )

    if args.env in ("cluster", "slurm", "ault", "slimfly"):
        run_cluster(args, launch_string, msg_size, "AllToAll", topo_name)
    else:
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

    if args.size:
        sizes = [args.size]
    elif args.small_run:
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
    parser.add_argument("--board_shape", type=str, default="4x4",
                        help="Board shape as AxB (default: 4x4)")
    parser.add_argument("--global_shape", type=str, default="8x8",
                        help="Global shape as AxB (default: 8x8)")
    parser.add_argument("--num_threads", type=int, default=8,
                        help="Number of threads for SST (default: 8)")
    parser.add_argument("--small_run", action="store_true",
                        help="Run only 2 message sizes instead of 6")
    parser.add_argument("--size", type=int, default=0,
                        help="Run a single message size in bytes (overrides the sweep / --small_run). 0 = disabled.")
    parser.add_argument("--jellyfish", action="store_true",
                        help="Use Jellyfish random graph as local board topology instead of 2D mesh")
    parser.add_argument("--ft_nodes", type=int, default=0,
                        help="Number of random fat tree gateways per direction per board "
                             "(Jellyfish only; 0 = border nodes, default)")
    parser.add_argument("--graph_seed", type=int, default=0,
                        help="Seed for the Jellyfish random graph wiring (reproducible). "
                             "Vary this to measure graph-generation variation.")
    parser.add_argument("--gateway_seed", type=int, default=0,
                        help="Seed for random gateway selection (Jellyfish ft_nodes>0). "
                             "Vary this to measure gateway-selection variation.")
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
