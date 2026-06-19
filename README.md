# HammingMesh with Jellyfish Local Topology

This repo extends [HammingMesh](hxnet-master/README.md) by allowing each board's
internal 2D mesh to be replaced with a Jellyfish random regular graph, while
keeping the global fat-tree interconnect. The main code lives in
`hxnet-master/sst-elements-library-11.1.0/src/sst/elements/merlin/`.

## Installation

The simulator is SST 11.1.0. Follow **"Installation from Source Code"** in the
HammingMesh paper/artifact:

- Paper & artifact appendix: [docs/3571885.3571899.pdf](docs/3571885.3571899.pdf),
  section *"Installation from Source Code"* (C++11, python3, python-dev, OpenMPI 4.0.5).

After modifying any C++ files, rebuild from
`hxnet-master/sst-elements-library-11.1.0/`:

```bash
make -C src/sst/elements/merlin && make install
```

## Running an AllToAll simulation (large topology)

The main entry point is
[launchAllToAll_large.py](hxnet-master/benchmarks/largeTopology/AllToAll/launchAllToAll_large.py).
It builds the topology, generates the AllToAll traffic motif, and runs SST for a
sweep of message sizes. Run all commands from the script's directory:

```bash
cd hxnet-master/benchmarks/largeTopology/AllToAll
```

### Quick start

```bash
# Default HammingMesh: 4x4 boards in an 8x8 global grid = 1024 nodes
uv run python launchAllToAll_large.py

# Same topology, but each board uses a Jellyfish graph instead of a 2D mesh
uv run python launchAllToAll_large.py --jellyfish

# Quick test: only 2 message sizes instead of 6
uv run python launchAllToAll_large.py --jellyfish --small_run
```

### Common options

| Flag | Meaning | Default |
|------|---------|---------|
| `--board_shape AxB` | Shape of a single board | `4x4` |
| `--global_shape AxB` | Grid of boards | `8x8` |
| `--jellyfish` | Use a Jellyfish graph inside each board instead of a 2D mesh | off (2D mesh) |
| `--ft_nodes N` | Use N dedicated fat-tree gateways per direction per board (Jellyfish only; `0` = all border nodes) | `0` |
| `--small_run` | Run 2 message sizes instead of 6 (quick smoke test) | off |
| `--num_threads N` | SST thread count | `8` |

Total nodes = `board_rows * board_cols * global_rows * global_cols`, so the
defaults (`4x4` x `8x8`) give 1024 nodes.

### Examples

```bash
# Smaller topology, full sweep
uv run python launchAllToAll_large.py --board_shape 2x2 --global_shape 4x4

# Jellyfish boards with a reduced number of fat-tree gateways
uv run python launchAllToAll_large.py --jellyfish --ft_nodes 2

# Use all available cores
uv run python launchAllToAll_large.py --num_threads $(nproc)
```

## Results and plots

Raw simulation output is written to `output/<topo_name>/<message_size>`, where
`<topo_name>` is e.g. `hx4_1024` (or `hx4_1024_jellyfish`, `..._ft2`, etc.).

To regenerate the throughput-vs-message-size plot, run the four reference
configs and then build the plot:

```bash
# Runs hx4_1024, _jellyfish, _jellyfish_ft1, _jellyfish_ft2 sequentially
bash regen_alltoall_plot.sh

# Build PDF/PNG plots from whatever output exists
uv run python parseAndPlotAllToAll.py
```

These are long runs: launch them inside `tmux`/`screen` or with `nohup`.
