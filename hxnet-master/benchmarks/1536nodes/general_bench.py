import re
import subprocess
from pathlib import Path
import sys
from argparse import ArgumentParser
import pathlib
import os
import time

# Change this to Path later
logs_folder = "logs"
motif_folder = "loads"
output_folder = "output"
sbatch_folder = "sbatch"
default_param_file = "defaultParams.py"
ember_load_folder = "../../../sst-elements-library-11.1.0/src/sst/elements/ember/test/"
default_file = "../../../sst-elements-library-11.1.0/src/sst/elements/ember/test/defaultParams.py"
file_ember_load_slimfly = "/scratch/tbonato/hxnet/sst-elements-library-11.1.0/src/sst/elements/ember/test/emberLoad.py"
folder_load_motif_slimfly = os.getcwd() + "/loads"
folder_save_file_slimfly = os.getcwd() + "/output"
generate_id_string_dragonfly = "[NID_LIST] generateNidList=generateNidListRange(0,1632)\n"
generate_id_string_fattree_torus = "[NID_LIST] generateNidList=generateNidListRange(0,1536)\n"
generate_id_string_hx4 = "[NID_LIST] generateNidList=generateNidListHx(4x4x12x8)\n"
generate_id_string_hx2 = "[NID_LIST] generateNidList=generateNidListHx(2x2x24x16)\n"

def check_if_exist(topo):
    # First check if the folder we need to use exist
    path_motif = pathlib.Path(motif_folder)
    path_motif.mkdir(parents=True, exist_ok=True)
    path_out = pathlib.Path(output_folder)
    path_out.mkdir(parents=True, exist_ok=True)
    path_sbatch = pathlib.Path(sbatch_folder)
    path_sbatch.mkdir(parents=True, exist_ok=True)
    path_topo = pathlib.Path(output_folder + "/" + topo)
    path_topo.mkdir(parents=True, exist_ok=True)
    path_logs = pathlib.Path(logs_folder)
    path_logs.mkdir(parents=True, exist_ok=True)

def run_slim(args, launch_string, size, name, topo):
    if (topo == "dragonfly" and args.nodes > 4):
        node_num = 16
    else:
        node_num = args.nodes
    slim_string = " /scratch/2/t2hx/dep/openmpi/bin/mpirun -mca plm_rsh_no_tree_spawn 1 --map-by node -mca btl openib,self,sm -mca btl_openib_if_include mlx4_0 --hostfile /home/tbonato/{} -mca orte_base_help_aggregate 0  -np {} /scratch/tbonato/sstcore-11.1.0/libexec/sstsim.x".format(args.hostfile, node_num)
    print(slim_string + " " + launch_string)
    os.system(slim_string + " " + launch_string)

def run_cluster(args, launch_string, size, name, topo):

    # Special case for Dragonfly (max 32 componenst for Small topo) -- Need Fix
    '''if (topo == "dragonfly"):
        old_nodes = args.nodes
        if args.nodes > 4:
            args.nodes = 4'''

    # Special case if we are running on SlimFly
    if (args.env == "slimfly"):
        return run_slim(args, launch_string, size, name, topo)
    
    my_sbatch_cont = ["#!/bin/bash\n",
    "#SBATCH -N {}\n".format(args.nodes),
    "#SBATCH -n {}\n".format(args.nodes),
    "#SBATCH --time=03:59:59\n",
    "#SBATCH -A g34\n",
    "#SBATCH --mem={}\n".format(args.mem),
    "#SBATCH --cpus-per-task={}\n".format(args.cpus_per_task),
    "#SBATCH -C mc\n",
    "#SBATCH --output=logs/slurm-%A.out\n",
    "# Load the module environment suitable for the job\n" ,   
    "module load openmpi\n",
    "# And finally run the job\n"]

    if (args.env == "ault"):
        my_sbatch_cont = [ x for x in my_sbatch_cont if x != "#SBATCH -C mc\n"]
        my_sbatch_cont = [ x for x in my_sbatch_cont if x != "#SBATCH -A g34\n"]

    my_sbatch_cont.append("srun --mem={} -N {} -n {} --cpus-per-task={} sstsim.x ".format(args.mem, args.nodes, args.nodes, args.cpus_per_task) + launch_string)
    # Write the array back to the same file
    file_name = "launch{}_{}_{}".format(topo, name, size)
    with open(sbatch_folder + "/" + file_name, 'w') as file:
        file.writelines(my_sbatch_cont)

    os.system("sbatch " + sbatch_folder + "/" + file_name)
    time.sleep(2)

def run_sst(args, topo, size, name = ""):

    ember_load = ember_load_folder + "emberLoad.py"
    tmp = size
    if (topo == "dragonfly" or topo == "fattree" or topo == "fattree50" or topo == "fattree80" or topo == "fattree75" ):
        if (name == "AllToAll" or name == "AllToAllSalvo" or name == "AllToAllTom" or name == "AllReduceRing"):
            tmp = int(size / 4)
    output_result = output_folder + "/" + topo + "/" + str(tmp)

    location_motif = motif_folder + "/" + name

    if (args.env == "slimfly"):
        location_motif = folder_load_motif_slimfly + "/" + name
        output_result = folder_save_file_slimfly + "/" + topo + "/" + str(size)

    if (topo == "hx4"):
        launch_string = '--num_threads={} --model-options="--param="nic:module=merlin.reorderlinkcontrol" --topo=hx --boardShape=4x4 --globalShape=12x8 --fatTreeShape=1:1,64 --hostsPerRtr=1 --loadFile={}" {} > {}'.format(str(args.num_threads), location_motif, ember_load, output_result)
    elif (topo == "hx2"):
        launch_string = '--num_threads={} --model-options="--param="nic:module=merlin.reorderlinkcontrol" --topo=hx --boardShape=2x2 --globalShape=24x16 --fatTreeShape=1:1,64 --hostsPerRtr=1 --loadFile={}" {} > {}'.format(str(args.num_threads), location_motif, ember_load, output_result)
    elif (topo == "hyperx"):
        launch_string = '--num_threads={} --model-options="--param="nic:module=merlin.reorderlinkcontrol" --topo=hyperx --shape=48x32 --loadFile={}" {} > {}'.format(str(args.num_threads), location_motif, ember_load, output_result)
    elif (topo == "fattree"):
        launch_string = '--num_threads={} --model-options="--param="nic:module=merlin.reorderlinkcontrol" --topo=fattree --shape=32,48:48 --loadFile={}" {} > {}'.format(str(args.num_threads), location_motif, ember_load, output_result)
    elif (topo == "fattree50"):
        launch_string = '--num_threads={} --model-options="--param="nic:module=merlin.reorderlinkcontrol" --topo=fattree --shape=32,24:48 --loadFile={}" {} > {}'.format(str(args.num_threads), location_motif, ember_load, output_result)
    elif (topo == "fattree80" or topo == "fattree75"):
        launch_string = '--num_threads={} --model-options="--param="nic:module=merlin.reorderlinkcontrol" --topo=fattree --shape=32,12:48 --loadFile={}" {} > {}'.format(str(args.num_threads), location_motif, ember_load, output_result)
    elif (topo == "torus"):
        launch_string = '--num_threads={} --model-options="--param="nic:module=merlin.reorderlinkcontrol" --topo=torus --shape=48x32 --hostsPerRtr=1 --loadFile={}" {} > {}'.format(str(args.num_threads), location_motif, ember_load, output_result)
    elif (topo == "dragonfly"):
        # Special case for Dragonfly
        if args.num_threads > 8:
            args.num_threads = 2
        launch_string = '--num_threads={} --model-options="--param="nic:module=merlin.reorderlinkcontrol" --topo=dragonfly --shape=17:32:512:3 --loadFile={}" {} > {}'.format(str(args.num_threads), location_motif, ember_load, output_result)
    else:
        print("Error, unknown topo")
        sys.exit(0)

    if (args.env == "local" or args.env == ""):
        print(launch_string)
        process = subprocess.Popen(["sst " + launch_string], shell=True)
        process.wait()
    elif (args.env == "slurm" or args.env == "cluster" or args.env == "ault" or args.env == "slimfly"):
        run_cluster(args, launch_string, size, name, topo)
    else:
        print("Error, unknown env")
        sys.exit(0)