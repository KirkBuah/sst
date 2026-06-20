# Troubleshooting: 2D-mesh board vs Jellyfish board — local fabric only

## Why

In the full HammingMesh AllToAll benchmark, swapping the original 2D-mesh local
boards for the modified Jellyfish boards gave *worse* throughput than expected.
This experiment isolates the variable: it runs AllToAll on **one local board** of
each kind — a 2D mesh and a Jellyfish random graph with the **same node count** —
with **no fat tree and no global structure at all**. If the Jellyfish board is
slower here, the local fabric itself is the cause; if it is faster/equal, the
regression comes from how Jellyfish boards integrate with the global / fat-tree
structure.

## What this runs (genuinely standalone single boards)

- **mesh** (`--topo=mesh`): the native merlin 2D mesh (`merlin.mesh`,
  dimension-order routing, no wrap-around, no fat tree).
- **jellyfish** (`--topo=jellyfish`): a standalone single-board Jellyfish — a
  **canonical 4-regular random graph** (every node has 4 random inter-router
  links), shortest-path table routing, no fat tree. Implemented as the
  `topoJellyfish` class in `merlin/pymerlin.py`.

Both run through the **same ember harness with identical link/router parameters**
(`link_bw=400Gb/s`, `nic_link_bw=1600Gb/s`, `xbar_bw=3200Gb/s`, same flit/packet
sizes — the same values the HammingMesh local boards use), so the only difference
is the intra-board fabric.

> Earlier attempts using `--topo=hx` with a small global shape could not isolate
> the fabric: the hamming **mesh** routing crashes on a single board, and the
> hamming **jellyfish** at `1x1` still builds degenerate edge-connecting fat-tree
> switches. These standalone topologies avoid both problems.

### Fairness note (link budget)

At equal node count a 4-regular Jellyfish has somewhat **more** links than a 2D
mesh (whose edge/corner nodes are degree 2–3). This is the standard Jellyfish-vs-
mesh framing (same switches, Jellyfish has higher bisection). So if the Jellyfish
is *slower* here it is a strong result; if it is *faster*, remember it also has a
mild link-count advantage.

## Run

```bash
# Smoke test (4x4 = 16 nodes, 2 message sizes)
uv run python launch_local_topos.py --shape 4x4 --small_run

# Full comparison (8x8 = 64 nodes, full powers-of-2 message sweep)
uv run python launch_local_topos.py --shape 8x8

# Parse + plot (compares every node count that has both fabrics)
uv run python parse_mesh_vs_jellyfish.py
```

Flags: `--shape NxM` (board, = node count, applied to both fabrics),
`--small_run` (2 sizes), `--num_threads T` (default all cores),
`--topos mesh,jellyfish` (subset to run).

## Outputs

- `output/mesh_<N>/<msg_size>`, `output/jellyfish_<N>/<msg_size>` — SST run logs
- `loads/` — generated AllPingPong motif files
- `logs/` — per-run command + status log (each run is verified for
  `STATS` + `Simulation is complete`; the launcher reports `ABORTED` otherwise)
- `plots/mesh_vs_jellyfish_<N>nodes.{png,pdf}` — throughput vs message size

`parse_mesh_vs_jellyfish.py` prints, per node count, a table with the
**jelly/mesh ratio** (`> 1.0` = jellyfish faster). Throughput is the bottleneck
(slowest node) `messageSize·(N−1) / max_latency`, ×8 → Gb/s, matching
`../parseAndPlotAllToAll.py`.

## Files changed to enable this (all pure Python, no SST recompile)

- `merlin/pymerlin.py`: new `topoJellyfish` class; `topoMesh.topoKeys` gained the
  missing `nic_link_bw` (the native mesh otherwise fatals on `hr_router`).
- `ember/test/networkConfig.py`: new `MeshInfo`.
- `ember/test/emberLoad.py`: `--topo=mesh` and `--topo=jellyfish` dispatch; both
  added to the network-params block so they get the standard link bandwidths.

The compiled `hamming.cc` jellyfish router is reused unchanged: for a single
board it routes every (same-board) destination via the per-node routing table and
never touches fat-tree ports.

## Interpreting the result

At small messages throughput is latency-bound (diameter matters); the
bandwidth-bound large-message tail is the more meaningful comparison. If the
Jellyfish ratio is `≥ 1.0` here but the full HammingMesh regressed, the problem
lies in the **global integration** (fat-tree gateways, inter-board routing), not
the local board fabric.
