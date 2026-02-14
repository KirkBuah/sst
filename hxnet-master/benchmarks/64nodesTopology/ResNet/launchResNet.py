import re
import subprocess
from pathlib import Path
import sys
from argparse import ArgumentParser
import pathlib
import os
import time
sys.path.append("../")
from general_bench import *
from generateNidListHx import generate
from generateNidListRange import generate as generateRange

sizes = [256, 512, 1024]

topologies = {
  "fattree": 1024,
  "fattree50": 1024,
  "fattree80": 1024,
  "dragonfly": 1024,
  "hx2":1024,
}

def nid_generation(topo, size):
    list_other_nodes = []
    topo_nodes = range(0, 1024)
    if (topo == "dragonfly"):
        topo_nodes = range(0, 1088)

    size = int(size)
    if (size != 256 and size != 512 and size != 1024):
        print("Size not supported!\n")
        exit(0)

    if (topo == "dragonfly"):
        list_gpt_nodes = range(0, size)
        list_gpt_nodes = [int(i) for i in list_gpt_nodes]
        list_other_nodes = list(set(topo_nodes) - set(list_gpt_nodes))
    elif (topo != "hx4" and topo != "hx2"):
        list_gpt_nodes = range(0, size)
        list_gpt_nodes = [int(i) for i in list_gpt_nodes]
        list_other_nodes = list(set(topo_nodes) - set(list_gpt_nodes))
    elif (topo == "hx4"):
        if (size == 256):
            list_gpt_nodes = generate("4x4x8x8_16x16")
        elif (size == 512):
            list_gpt_nodes = generate("4x4x8x8_32x16")
        elif (size == 1024):
            list_gpt_nodes = generate("4x4x8x8")
        list_gpt_nodes = list_gpt_nodes.split(",")
        list_gpt_nodes = [int(i) for i in list_gpt_nodes]
        list_other_nodes = list(set(topo_nodes) - set(list_gpt_nodes))
    elif (topo == "hx2"):
        if (size == 256):
            list_gpt_nodes = generate("2x2x16x16_16x16")
        elif (size == 512):
            list_gpt_nodes = generate("2x2x16x16_32x16")
        elif (size == 1024):
            list_gpt_nodes = generate("2x2x16x16")
        list_gpt_nodes = list_gpt_nodes.split(",")
        list_gpt_nodes = [int(i) for i in list_gpt_nodes]
        list_other_nodes = list(set(topo_nodes) - set(list_gpt_nodes))

    return list_gpt_nodes, list_other_nodes

def all_reduce_type_from_topo(topo):
    if (topo == "hx2" or topo == "hx4" or topo == "torus"):
        return "25D"
    else:
        return "05D"

def create_motif_load(name, motif_folder, topo, sizeJob):

    list_gpt_nid, list_null_nid = nid_generation(topo, sizeJob)
    all_reduce_type = all_reduce_type_from_topo(topo)

    path_motif = pathlib.Path(motif_folder)
    path_motif.mkdir(parents=True, exist_ok=True)

    motif_content = ["[JOB_ID] 10\n",
    "[NID_LIST] {}\n".format(",".join([str(a) for a in list_gpt_nid])),
    "[MOTIF] Init\n",
    "[MOTIF] ResNet152 all_reduce_type={}\n".format(all_reduce_type),
    "[MOTIF] Fini\n",
    "\n[JOB_ID] 11\n",
    "[NID_LIST] {}\n".format(",".join([str(a) for a in list_null_nid])),
    "[MOTIF] Init\n",
    "[MOTIF] Null\n",
    "[MOTIF] Fini\n"]

    with open(motif_folder + "/" + name, 'w') as file:
        file.writelines(motif_content)

    time.sleep(10)


def create_basic_motif(name):
    path_motif = pathlib.Path(motif_folder)
    path_motif.mkdir(parents=True, exist_ok=True)

    motif_content = ["[JOB_ID] 10\n",
    "[NID_LIST] generateNidList=generateNidListRange(0,1024)\n",
    "[MOTIF] Init\n",
    "[MOTIF] ResNet152\n",
    "[MOTIF] Fini"]

    with open(motif_folder + "/" + name, 'w') as file:
        file.writelines(motif_content)

def generate_simulations(args, to_replace, name, topologies, sizes):
    for msg_size in sizes:
        args.size = msg_size
        for topo in topologies:
            if (args.topo != "" and args.topo != topo):
                continue
            print(topo)
            check_if_exist(topo)
            # Parse Current File, replace data and store it in an array
            new_lines = []
            generating_id_string = ""
            location_motif = motif_folder + "/" + name

            ## If jobs using all nodes
            if (args.size == 0):
                with open(location_motif, 'r') as f:
                    for line in f:
                        # Change topo size based on topology
                        if (topo == "dragonfly"):
                            generating_id_string = generate_id_string_dragonfly
                        elif (topo != "hx4" and topo != "hx2"):
                            generating_id_string = generate_id_string_fattree_torus
                        elif (topo == "hx4"):
                            generating_id_string = generate_id_string_hx4
                        elif (topo == "hx2"):
                            generating_id_string = generate_id_string_hx2

                        tmp = msg_size
                        line = re.sub(r"{}\d+".format(to_replace), "{}{}".format(to_replace, tmp), line)
                        new_lines.append(line)

                # Write the array back to the same file
                with open(location_motif, 'w') as file:
                    print(generating_id_string)
                    new_lines[1] = generating_id_string
                    file.writelines(new_lines)

            # If size is not zero then we need to create a custom motif with also null nids
            if (args.size != 0):
                create_motif_load(name, motif_folder, topo, args.size)
            run_sst(args, topo, msg_size, name)

def main(args):
    # Generate our custom Motif for this specific benchmark
    name = "ResNet152"
    create_basic_motif(name)
    generate_simulations(args, "NONE", name, topologies, sizes)    

if __name__ == "__main__":
    parser = ArgumentParser()
    parser.add_argument("--topo", type=str, help="Topology to run", default="", choices=["hx4", "hx2", "fattree", "fattree50", "fattree80", "torus", "dragonfly"])
    parser.add_argument("--env", type=str, help="Local or Cluster", default="", choices=["cluster", "daint", "ault", "local", "slimfly"])
    parser.add_argument("--num_threads", type=int, help="Number of threads to use for SST", default=8)
    parser.add_argument("--nodes", type=int, help="Number of nodes for cluster", default="8")
    parser.add_argument("--cpus_per_task", type=str, help="Number of cores per node for cluster", default="8")
    parser.add_argument("--mem", type=str, help="Memory per Node for cluster", default="16G")
    parser.add_argument("--hostfile", type=str, help="Hostfile name for Slimfly", default="hostfile")
    parser.add_argument("--size", type=str, help="Size of the job", default=0)
    args = parser.parse_args()
    main(args)