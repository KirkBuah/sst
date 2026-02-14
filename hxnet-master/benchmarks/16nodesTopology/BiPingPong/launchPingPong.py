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

topologies = {
  "hx4": 1024,
  "hx2": 1024,
  "fattree": 1024,
  "fattree50": 1024,
  "fattree80": 1024,
  "torus": 1024,
  "dragonfly": 1024,
}

#sizes = [512, 8192, 65536, 131072, 262144, 1048576, 2097152, 4194304, 8388608]
sizes = [4096]

def create_motif_load(name):
    path_motif = pathlib.Path(motif_folder)
    path_motif.mkdir(parents=True, exist_ok=True)

    motif_content = ["[JOB_ID] 10\n",
    "[NID_LIST] generateNidList=generateNidListRange(0,1024)\n",
    "[MOTIF] Init\n",
    "[MOTIF] BiPingPong messageSize=5001\n",
    "[MOTIF] Fini"]

    with open(motif_folder + "/" + name, 'w') as file:
        file.writelines(motif_content)

def generate_simulations(args, to_replace, name, topologies, sizes):
    for msg_size in sizes:
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
                            generating_id_string = "[NID_LIST] generateNidList=generateNidListRange(0,1088)\n"
                        elif (topo != "hx4" and topo != "hx2"):
                            generating_id_string = "[NID_LIST] generateNidList=generateNidListRange(0,1024)\n"
                        elif (topo == "hx4"):
                            generating_id_string = "[NID_LIST] generateNidList=generateNidListHx(4x4x8x8)\n"
                        elif (topo == "hx2"):
                            generating_id_string = "[NID_LIST] generateNidList=generateNidListHx(2x2x16x16)\n"

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
    name = "BiPingPong"
    create_motif_load(name)
    generate_simulations(args, "messageSize=", name, topologies, sizes)    

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