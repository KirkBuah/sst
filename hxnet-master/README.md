# HammingMesh: A Network Topology for Large-Scale Deep Learning

Numerous microarchitectural optimizations unlocked tremendous processing power for deep neural networks that in turn fueled the AI revolution. With the exhaustion of such optimizations, the growth of modern AI is now gated by the performance of training systems, especially their data movement. Instead of focusing on single accelerators, we investigate data-movement characteristics of large-scale training at full system scale. Based on our workload analysis, we design HammingMesh, a novel network topology that provides high bandwidth at low cost with high job scheduling flexibility. Specifically, HammingMesh can support full bandwidth and isolation to deep learning training jobs with two dimensions of parallelism. Furthermore, it also supports high global bandwidth for generic traffic. Thus, HammingMesh will power future large-scale deep learning systems with extreme bandwidth requirements.


## Introduction
This repository contains the basic requirements and instructions needed to reproduce the results of the paper. 
It is organized in the following directories:
* `benchmarks/` contains all the scripts and supporting code needed to run the various benchmarks (both locally or on a cluster with sbatch). It also containes the code needed to generate the final plots and results. Each subfolder of the `benchmarks/` folder has a more detailed README based on the chosen benchmark.
* `results/` contains most of the actual results obtained from the benchmarks run. It is also possible to use this folder to generate the final plots and results. 
Note that few results are not included directly in this repository due to their large size (100+ GB).
* `allocation_simulations/` contains the code and files used to simulate and test our job allocation algorithm. It also contains the code to generate the respective plots.
* `sstcore-11.1.0/` contains the core functions of the SST Simulator (version 11.1.0). These files have not been changed for the purpose of this paper compared to the original ones.
* `sst-elements-library-11.1.0/` contains the elements part of the SST Simulator and has been heavily modified to support our topology, the benchmarks that we used and all the supporting code.
* `sst_test_outputs` contains some test file used by SST to check its correct behaviour.

We provide two methods to run the project: an easy to install Docker container with everything ready to go (`hx_container` artifact) and the source code which can be installed and tuned to run on any machine including clusters supporting sbatch (`hx_source_code` artifact).
While the container is easy to use and test, it is not always ideal to be used on a general purpose cluster and for this reason we also provide the source code and the relative instructions about how to install it. Having said that, it is theoretically also possible to run all the benchmarks locally although the completion time will be very long in some cases.

## Installation from Docker File
Please download the docker container from [here](https://doi.org/10.5281/zenodo.6462395
) or using the DOI link.

Load and run the docker image using the following command. Note this could take some time to run and might have to be run as root.
```bash
sudo docker load -i hxmesh_container.tar.gz
sudo docker run -it hxmesh:2.0
```

To go into the repository of the code simply
```bash
cd /hxnet
```

If viewing images such as plots inside the container is problematic, it is possible to transfer that file to the host machine using:
```bash
docker cp <containerId>:/file/path/within/container /host/path/target
```

It is possible to obtain the `<containerId>` by running
```bash
sudo docker ps
```

## Installation from Source Code
The installation from source code should take about 10-15 minutes on a modern machine.

### Requirements
C++11, python3, python-dev and OpenMPI 4.0.5 are necessary when installing the project from source code as these are the minimum requirements for SST to run.
In particular, in our case, we run our code locally with the following compilers and software:
* gcc (Ubuntu 9.3.0-10ubuntu2) 9.3.0
* Open MPI 4.0.5
* Python 3.8.10

### Installation
Please first download the repository using its relative DOI or directly from [GitLab](https://spclgitlab.ethz.ch/tbonato/hxnet).

Once, the download has been finished, extract the archive and go inside the extracted folder. Once that has been done, it is possible to start installing SST.

To install SST 11.1.0 and OpenMPI 4.0.5 we refer to the official instructions from the [SST website.](http://sst-simulator.org/SSTPages/SSTBuildAndInstall_11dot1dot0_SeriesDetailedBuildInstructions/#openmpi-405-strongly-recommended) Note that the source files for SST are already part of this repository and it is important to use them as they contains all our modifications compared to the original SST repository (keep this in mind also when setting the location of `SST_CORE_ROOT` and `SST_ELEMENTS_ROOT`)
One common issue could be the `make all` of SST Core or SST Elements failing. In that case please try to run `automake` first.
Once the installation has been done, it is possible to test its correctness by running:
```bash
sst-test-core
sst-test-elements -w "*simple*"
```

The requirements.txt file should list all Python libraries that are used when parsing the data and generating the plots. These libraries can be installed running
```python
pip install -r requirements.txt
```

Finally it is necessary to add this environmental variable to your `~/.bashrc` file or equivalent for the correct execution of the scripts.
```
export PYTHONPATH="${PYTHONPATH}:$SST_ELEMENTS_ROOT/src/sst/elements/ember/test/"
```
## General Usage
The benchmark folder is used to run all the simulations used in this paper. Inside the benchmark folder we can find a serious of topologies. The ones used in the final results of this paper are:
* `smallTopology/`
* `largeTopology/`
* `1536nodes/`

Inside each one of these subfolder there are more subfolders, one for each benchmark. As a general guideline (with few exceptions), each specific subfolder contains two Python files: one to run the benchmark itself and to generate the data and one to parse the data and create the plots in PDF and PNG format. For example, from inside the `benchmarks/smallTopology/DLRM` folder we can run the benchmark by using `python3 launchDLRM.py` and then parse it by using `python3 parseAndPlotDLRM.py`. Having said that, we refer to each individual README for more in-depth details and to the different command line parameters available (can also be shown using the `--help` command for each individual launch script).
We also provide the final data used for the paper inside the `results/` folder. It is possible to use it to generate the plots without having to re-run all the simulations. In that case, simply copy one `output/` folder from `results/` to its corresponding  `benchmarks/` folder (for example copy  `results/DLRMSmall/output/` to  `benchmarks/smallTopology/DLRM`. We will have more details inside each individual README for the corresponding benchmark.
Here is the list of benchmarks that are used for the paper and their locations:
* `benchmarks/smallTopology/AllReduce`
* `benchmarks/smallTopology/AllToAll`
* `benchmarks/smallTopology/RandomPermutation`
* `benchmarks/smallTopology/Cosmo`
* `benchmarks/smallTopology/GPT3`
* `benchmarks/smallTopology/DLRM`
* `benchmarks/smallTopology/ResNet`
* `benchmarks/largeTopology/GPT3MOE` or `benchmarks/1536nodes/GPT3MOE` for faster execution.
* `benchmarks/largeTopology/AllReduce`
* `benchmarks/largeTopology/AllToAll`

### Plots Reproducibility
This section will explain how to generate the plots which are used in the paper. We assume that the data has already been generated using the instructions above or that we are using the already generated and saved results.
* Figure 8-11 can be generated by first running `./run\_all.sh` from inside the `allocation\_simulations/` folder and then running `python3 plot\_paper.py` from the same folder. The plots will be generated in the `allocation\_simulations/plots/` folder.
* Figure 12 can be generated simply by running `python3 parseAndPlotAllToAll.py` from inside the `benchmarks/smallTopology/AllToAll` folder.
* Figure 13 can be generated simply by running `python3 parsePerm.py` from inside the `benchmarks/smallTopology/RandomPermutation` folder.
* Figure 14 can be generated simply by running `python3 parseAndPlotAllReduce.py` from inside the `benchmarks/largeTopology/AllReduce` folder.
* Figure 16 can be generated simply by running `python3 plot\_cost\_savings\_diff\_col.py` from inside the `benchmarks/smallTopology/Plot` folder.

Note that when each benchmark is parsed using the corresponding Python script, the standard output (stdout) will display some key information from the run. These values have been used to build Table II from the paper and also in section V.

## Cluster Usage
All simulations are run by default locally if not specified. It is possible to run them on a cluster supporting sbatch by using the `--env=cluster` parameter when launching the various benchmarks. In this case it is likely necessary to modify the `general_bench.py` (from line 70) to change the various sbatch details such as account name and possibly other limits (such as job duration or memory limits).


## Simulation Times
The simulations used in this work can take a long time to copmplete since we are simulating large networks and billion of packets. We provide below a short summary of the time needed to fully complete the simulations for each benchmark.

| Benchmark | Nodes Used | Runtime (Hours) | Total Node Hours |
| ------ | ------ | ------ | ------ |
| AllToAllSmall | 64 | 38 | 2432 |
| AllReduceSmall | 64 | 10 | 640 |
| AllToAllLarge | 128 | 166 | 21248 |
| AllReduceLarge | 128 | 59 | 7552 |
| RandomPermutation | 32 | <1 | <32 |
| ResNet | 64 | <1 | <64 |
| GPT3 | 64 | 4 | 256 |
| GPT3-MOE | 64 | 12 | 768 |
| Cosmo | 64 | 15 | 960 |
| DLRM | 16 | <1 | <16 |

Note that in some benchmarks we also provide an option to run only a fraction of the final data points in order to have quickly access to at least some of the results. The details are reported in the README of each individual benchmark.

## Common Problems
**Q:** The installationf fails when runnign `configure` or when trying to build it with `make`

**A:** In that case please make sure to run `automake` first.

**Q:** When trying to run the Python scrirpts for the benchmark, I get an error about a failed import.

**A:** Plese make sure that `export PYTHONPATH="${PYTHONPATH}:$SST_ELEMENTS_ROOT/src/sst/elements/ember/test/"` has been run. To make it permanent please consider adding this to your `~/.bashrc` file or equivalent.

**Q:** When parsing the data for the plots, I get an error

**A:** Please make sure the output files are not corrupted and that the simulations have fully completed.
