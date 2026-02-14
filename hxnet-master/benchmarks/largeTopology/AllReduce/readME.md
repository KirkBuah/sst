# AllReduce

This readME explains how to reproduce the results of the AllReduce benchmark for the large topologies (~16k nodes). 
Please note the terminology that we use:
* 05D refers to the Ring algorithm for a general topology (fattree and Dragonfly)
* 2D refers to the Torus algorithm for Mesh like topologies (2D torus and HxMesh)
* 2DRevised refers to the Torus algorithm for Mesh like topologies (2D torus and HxMesh) updated after the first review.
* 25D refers to the Ring algorithm for Mesh like topologies (2D torus and HxMesh)

## Usage

To launch the AllReduce jobs, please use the following script. By default all jobs are run locally using 8 threads.
```bash
python3 launchRing05D.py && python3 launchRing2DRevised.py && python3 launchRing25D.py
```
The three python scripts can also be run individually if needed and they all support the following options:

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
python3 parseAndPlotAllReduce.py
```

The plots will be generated in pdf and png format inside the `plots/` subfolder.
