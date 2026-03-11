# HammingMesh with Jellyfish Local Topology

Branch: `hxjelly`

## What this branch adds

This branch extends HammingMesh by replacing the structured 2D mesh **within each board** with a Jellyfish random regular graph. The global fat tree interconnect is preserved.

### Core changes (`sst-elements-library-11.1.0/src/sst/elements/merlin/`)

**`pymerlin.py`** — Topology builder (Python)
- Jellyfish graph generation for boards: `_generate_jellyfish_graph()`, `_wire_jellyfish_board()`
- Gateway selection with `--ftNodes=N`: `_compute_jf_gateways()`, `_get_reserved_ports()`
- Shortest-path routing table computation: `_compute_routing_tables()`, `_find_nearest_edges()`
- Fat tree: `createRowFatTree()` / `createColFatTree()`.

**`topology/hamming.cc`** — Routing (C++)
- `route_packet_jellyfish()`: table-based intra-board routing and gateway selection for inter-board traffic
- `getOutputPortFor()`: updated for flat fat tree port mapping

**`topology/hamming.h`** — Added Jellyfish and flat fat tree member variables

### Benchmark scripts (`hxnet-master/benchmarks/smallTopology/`)

- `Expansion/launchExpansionStudy.py` — Sweeps board/global shapes and ft_nodes configurations
- `Expansion/plotExpansion.py` — Generates throughput scaling and FT gateway tradeoff plots
- `Expansion/analyzeLinks.py` — Theoretical link budget analysis (no SST needed)
- `Expansion/plot_servers_vs_switches.py` — Servers vs links comparison

### Presentation

`docs/presentation.tex` — Slides covering HammingMesh overview, Jellyfish variant, benchmarks, and expansion study results.

## How to run

All commands from `hxnet-master/benchmarks/smallTopology/`.

```bash
# AllToAll (16 nodes, jellyfish)
cd AllToAll
python3 launchAllToAll_16nodes.py --board_shape 2x2 --global_shape 2x2 --jellyfish --small_run

# AllToAll with reduced fat tree gateways
python3 launchAllToAll_16nodes.py --board_shape 2x2 --global_shape 2x2 --jellyfish --ft_nodes 1 --small_run

# AllReduce (256 nodes, jellyfish)
cd AllReduce
python3 launchAllReduce.py --board_shape 4x4 --global_shape 4x4 --jellyfish --small_run

# Random Permutation
cd RandomPermutation
python3 launchRandomPerm.py --board_shape 2x2 --global_shape 2x2 --jellyfish --small_run

# Expansion study (all configs)
cd Expansion
python3 launchExpansionStudy.py --small_run

# Theoretical link analysis (no SST needed)
cd Expansion
python3 analyzeLinks.py
python3 plot_servers_vs_switches.py

# Generate plots from existing results
cd Expansion
python3 plotExpansion.py
```

Key flags:
- `--jellyfish`: use Jellyfish instead of 2D mesh for intra-board topology
- `--ft_nodes N`: use N dedicated fat tree gateways per direction (default: all border nodes)
- `--small_run`: run with fewer message sizes for quick testing
- `--num_threads N`: SST thread count (default: 8)

## Building

After modifying C++ files, rebuild from `hxnet-master/sst-elements-library-11.1.0/`:

```bash
make -C src/sst/elements/merlin && make install
```
