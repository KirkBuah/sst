# DLRM

This README explains how to reproduce the results of the DLRM benchmark for the small topologies (~1000 nodes).

## Usage

To launch the DLRM jobs, please use the following script. By default all jobs are run locally using 8 threads.
```bash
python3 launchDLRM.py
```

The following arguments are available as options.
```bash
  -h, --help            show this help message and exit
  --topo {hx4,hx2,fattree,fattree50,fattree75,torus,dragonfly,hyperx}
                        Topology to run
  --env {cluster,local,slimfly}
                        Local or cluster environment
  --num_threads NUM_THREADS
                        Number of threads to use for SST
  --nodes NODES         Number of nodes for cluster (only)
  --cpus_per_task CPUS_PER_TASK
                        Number of cores per node for cluster (only)
  --mem MEM             Memory per node for cluster (only)
  --hostfile HOSTFILE   Hostfile name for Slimfly (only)
  --size SIZE           Size of the job, internal paramter
```

Results will be saved in the `output/` subfolder. Once the jobs has been executed, it is possible to generate the plot using:
```bash
python3 parseAndPlotDLRM.py
```

The plots will be generated in pdf and png format inside the `plots/` subfolder. Standard output will also be used to print the main results.

## Results Only
It is also possible to use the already generated output files to generate the results. To do so, copy the `output` folder inside `results/DLRMSmall/` to this folder (`benchmarks/smallTopology/DLRM/`).
Once that has been done, just follow the previous instructions to generate the results.