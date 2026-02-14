# RandomPermutation

This README explains how to reproduce the results of the RandomPermutation benchmark for the small topologies (~1000 nodes).

## Usage

Before running the benchmark itself it is necessary to generate the pair of couples that will be used by the benchmark itself. To do so, simply run
```bash
python3 generate_partners.py
```
Then, to launch the RandomPermutation jobs, please use the following script. By default all jobs are run locally using 8 threads.
```bash
python3 launchPerm.py
```

The following arguments are available as options.
```bash
  -h, --help            show this help message and exit
  --topo {hx4,hx2,fattree,fattree50,fattree75,torus,dragonfly}
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
  --small_run           If this parameter is set, only some points are run
```

Results will be saved in the `output/` subfolder. Once the jobs has been executed, it is possible to generate the plot using:
```bash
python3 parsePerm.py
```

The plots will be generated in pdf and png format inside the `plots/` subfolder. Standard output will also be used to print the main results.

## Results Only
It is also possible to use the already generated output files to generate the results. To do so, copy the `output` folder inside `results/RandomPermutationSmall/` to this folder (`benchmarks/smallTopology/RandomPermutation/`).
Once that has been done, just follow the previous instructions to generate the results.