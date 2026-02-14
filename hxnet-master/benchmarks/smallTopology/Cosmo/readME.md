# CosmoFlow

This README explains how to reproduce the results of the CosmoFlow benchmark for the small topologies (~1000 nodes).

## Usage

To launch the CosmoFlow jobs, please use the following script. By default all jobs are run locally using 8 threads.
```bash
python3 launchCosmo.py
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

Results will be saved in the `output/` subfolder. Once the jobs has been executed, it is possible to generate the results using:
```bash
python3 parseAndPlotCosmo.py
```

Standard output will show the runtime, compute time and communication overhead.


## Results Only
It is also possible to use the already generated output files to generate the results. To do so, copy the `output` folder inside `results/CosmoFlowSmall/` to this folder (`benchmarks/smallTopology/Cosmo/`).
Once that has been done, just follow the previous instructions to generate the results.