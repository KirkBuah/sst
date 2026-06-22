# Topology Analysis Tools

## router_load_diag.py  (+ router_stats_mod.py)

**Why HammingMesh-with-Jellyfish is slower than HammingMesh-with-mesh on AllToAll.**
Runs the *same* AllToAll (AllPingPong, the motif the benchmark uses) on the 2D-mesh
boards (`--topo=hx`) and the Jellyfish boards (`--topo=hx --jellyfish`), with
merlin's per-port router statistics on, and quantifies **where the load goes**. The
slowdown is **routing-induced congestion**, not topology or hop count.

Everything is measured from SST itself: one `sst --run-mode=both
--output-json=graph.json --statsModule=router_stats_mod --statsFile=stats.csv`
invocation gives the exact built graph *and* the per-port stats from the same run.
`router_stats_mod.py` is the `--statsModule` hook that turns on the per-port stats
(`send_bit_count`, `send_packet_count`, `output_port_stalls`). Ports are classified
from the graph's link names (uniform across mesh/Jellyfish): `nic.*`=NIC,
`link.row*`=row uplink, `link.col*`=col uplink (the board switch is always the
link's `right` endpoint); everything else on a board switch is intra-board.

```bash
uv run python router_load_diag.py --board_shape 4x4 --global_shape 4x4 --msg_size 16384
uv run python router_load_diag.py --board_shape 4x4 --global_shape 8x8   # benchmark scale (1024 nodes)
```

Outputs a per-topology report, a mesh-vs-Jellyfish comparison table, and
`output/router_load/router_load_<board>_<global>.png` (per-link load distribution,
board→tree uplink distribution, row-vs-col tree usage).

**Important runtime notes:**
- **`--num_threads 1` (default).** With >1 thread SST splits/loses the per-port
  stats and the totals come out wrong; single-threaded is required for correct
  numbers.
- Load is measured in **bits** (`send_bit_count`), not packets: `reorderlinkcontrol`
  groups payload into different-size packets for mesh vs Jellyfish, so packet counts
  are not comparable while bits (the true offered load) are conserved.
- `router_stats_mod.py` uses **`enableAllStatisticsForComponentType`** (not the
  per-stat `enableStatisticForComponentType`), which in SST 11.1.0 would emit many
  rows with a blank `StatisticName`/`StatisticSubId` and corrupt the totals.

### Finding (as of this writing)

Board **4x4 / global 4x4** (256 nodes), AllToAll of 16 KB messages, identical
offered load (both deliver 8.58 Gb):

| metric | mesh | jellyfish | jf/mesh |
| --- | --- | --- | --- |
| **simulated completion time** | 173 µs | **390 µs** | **2.25x slower** |
| busiest link load | 60 Mb | **151 Mb** | **2.5x** |
| board→tree uplink max/mean | 1.2x | **3.0x** | gateway funneling |
| board→tree uplink CV | 0.12 | **0.46** | 3.8x more skewed |
| avg inter-switch hops / msg | 5.14 | 5.95 | 1.16x (≈equal) |

This holds at benchmark scale too — board **4x4 / global 8x8** (1024 nodes):
jellyfish completion **1798 µs vs 757 µs (2.38x slower)**, busiest link **707 vs
288 Mb (2.45x)**, board→tree uplink **max/mean 3.0x vs 1.22x** (identical funneling
ratio), avg hops 6.53 vs 5.57 (1.17x). The signature is scale-invariant.

**Root cause = gateway hot-spotting + no adaptive routing** (see
`merlin/topology/hamming.cc`): `route_packet_jellyfish` sends *all* of a board's
off-board traffic to a **single fixed edge node** (`jf_nearest_row_edge` /
`jf_nearest_col_edge`) out a **single uplink**, with a **deterministic single
next-hop** (`jf_routing_table`). The mesh (`route_packet_mesh`) spreads off-board
traffic across the **whole perimeter** (each board row/col exits via its own edge
node) and picks among minimal ports by **output credits**. Result: Jellyfish's
busiest link carries ~2.5x the mesh's, and AllToAll completion is gated by that
bottleneck → ~2.25x slower. Hop count is ≈equal, so longer paths are **not** the
cause. (Row-vs-col tree totals come out ≈1:1 globally — the diagonal-always-row-first
rule in `hamming.cc:555-590` concentrates load onto specific gateways rather than
skewing the global row/col split, which is why it shows up as uplink CV, not the
row/col ratio.)

> Note: board **8x8** mesh routing crashes at run time ("Received a packet from NIC
> but not from the correct port"), so the mesh-vs-Jellyfish comparison uses **board
> 4x4** (the board shape the AllToAll benchmark actually uses).

### Attempted routing fixes (and why the gap does NOT close)

We then tried to fix the Jellyfish routing (`merlin/topology/hamming.cc`
`route_packet_jellyfish` + `pymerlin.py` `_compute_balanced_gateways` /
`_compute_multipath_routing`). Completion time vs mesh (lower = better):

| Jellyfish routing | 256 (global 4x4) | 1024 (global 8x8) |
| --- | --- | --- |
| baseline (single nearest gateway) | 2.25x | 2.38x |
| balanced gateways (spread uplinks) | 3.47x | worse |
| balanced gateways + intra multipath | **2.19x** | **2.63x** |

What each step showed (all measured, identical offered load, correctness verified):
1. **Spreading off-board traffic across gateways** balances the uplinks *perfectly*
   (max/mean 3.0x → **1.0x**, CV → 0.00) — but **backfires**: it forces traffic to
   non-nearest, row/col-aligned gateways, which **inflates hop count** (5.95 → 7.8)
   and shifts the bottleneck to a **worse intra-board hotspot** (86 → 235 Mb). Among
   gateway-only choices, the *nearest* baseline is actually the best (it trades a
   151 Mb uplink hotspot for a 235 Mb intra one).
2. **Adding credit-adaptive intra-board multipath** (pick among all shortest-path
   next-hops by downstream credits, like the mesh) cuts the intra hotspot back
   (235 → 147 Mb) and recovers to ~baseline at 256 nodes — but **only ~24% of
   shortest paths in the sparse 4-regular graph have more than one minimal next-hop**
   (mean 1.28), so multipath has little to spread onto.

**Conclusion — the gap is structural, not a routing bug.** HammingMesh's row/col
fat trees reward a board topology whose structure *aligns* with them (the 2D mesh:
short, row/col-aligned paths to the right gateway). A random Jellyfish fabric —
even though it beats the mesh *in isolation* (step 1) — has no such alignment, so
reaching the structured gateways **inflates path length**, and that inflation
**grows with the global size** (avg hops 7.25 at 4x4 → 8.16 at 8x8 global, vs
mesh ~5.1–5.6). The intra-board load that follows can't be spread away because the
sparse graph offers few equal-cost paths. Net: the fixes balance the uplinks and
fix the regression, but at benchmark scale the Jellyfish board stays ~2.4–2.6x
slower. This is *why* Jellyfish local boards do not help HammingMesh, and why the
original paper uses 2D-mesh boards.

The fixes are reversible (git); the binary is rebuilt + installed via
`make && make install` in `sst-elements-library-11.1.0`.

### Ruling out the same-board fat-tree shortcut

A reviewer noted that the 2D-mesh routing lets **same-board** traffic take a
torus-style shortcut through the fat tree (`wrap_north/south/east/west`,
`hamming.cc:271-306`), while the Jellyfish `dest_board == my_board` branch never
does — possibly an unfair advantage for the mesh. We isolated this by running the
mesh with `--algorithm=min-adaptive-nogl`, which makes `wrap_*` return false
(shortcut OFF), no code change:

| config | mesh shortcut ON | shortcut OFF (nogl) | Δ |
| --- | --- | --- | --- |
| 256 (global 4x4) | 173.4 µs (5.14 hops) | 172.1 µs (5.15 hops) | −0.7% |
| 1024 (global 8x8) | 756.7 µs (5.57 hops) | 755.5 µs (5.57 hops) | −0.15% |

**Verdict: the same-board shortcut is negligible (<1%).** At board 4x4 the 2-tree-hop
wrap is rarely shorter than the direct in-board path, and same-board traffic is only
~6% (global 4x4) / ~1.5% (global 8x8) of AllToAll anyway. So it does **not** explain
the mesh's ~2.4x advantage — the cause is the **inter-board** gateway funnel + hop
inflation (above), not the intra-board shortcut.

## visualize_topology.py

Exports the HammingMesh **switch fabric** (mesh or Jellyfish boards) to
**GraphML + GEXF** for interactive exploration in **Gephi** / **Cytoscape**, with a
**structure-aware layout and colors baked in**. Graph source is SST's elaborated
graph (`sst --run-mode=init --output-json`). Boards are placed in the global grid,
each board as its own grid of switches, so the **mesh** shows clean short grid
edges while the **Jellyfish** shows the same node grid with random intra-board
links crossing — the difference is obvious at a glance.

```bash
uv run python visualize_topology.py                                  # both, board 8x8 / global 4x4
uv run python visualize_topology.py --topo jellyfish --preview       # + a matplotlib PNG preview
uv run python visualize_topology.py --board_shape 4x4 --global_shape 2x2 --preview
```

Outputs to `output/viz/<topo>_<board>_<global>.{gexf,graphml[,png]}`.
- Nodes carry visual attributes `x, y, size, r, g, b` (read directly by Gephi) and
  analytic attributes `role` (board/fat_tree), `board_id`, `local_id`,
  `intra_degree`, `is_gateway`. Edges carry `link_type` (`intra_board` vs
  `fat_tree`). NICs omitted by default (`--include_nics` to add them).

**How to view (Gephi, free desktop app):**
1. File → Open the `.gexf` (positions + colors load automatically).
2. Appearance → color by `board_id` (or `role`); size by `intra_degree`.
3. Filters → by `role` to isolate board vs fat-tree switches; partition edges by
   `link_type` to show/hide the fat-tree links and compare the intra-board fabric.
4. (Optional) run ForceAtlas2 if you want a force layout instead of the grid.

Cytoscape works similarly via the `.graphml`. `--preview` also drops a quick PNG so
you can eyeball mesh-grid vs jellyfish-crossings without opening Gephi.

**Node size in Gephi.** Gephi draws node radius in the same coordinate space as the
positions, so node size is relative to node spacing. Tune it with `--scale`
(position spacing, default 20) and `--node_size` (default 2.5) — larger `--scale`
or smaller `--node_size` makes nodes appear smaller. (In-app alternatives: run the
*Expansion* layout to spread nodes, or set a small fixed node size in the
Appearance panel.)

## jellyfish_min_degree.py

Reports the **minimum number of connections (degree)** a node has within a
Jellyfish board, from SST's elaborated graph (`sst --run-mode=init
--output-json`). Two notions are reported: **intra-board jellyfish degree** (links
to other switches of the same board — the headline) and **total degree**
(intra-board + fat-tree uplinks).

```bash
uv run python jellyfish_min_degree.py                                  # both contexts, board 8x8 / global 4x4
uv run python jellyfish_min_degree.py --context full --board_shape 8x8 --global_shape 4x4
```

**Findings (board 8x8):**

| context | intra-board degree histogram | min intra-board | min total |
|---------|------------------------------|-----------------|-----------|
| **Standalone** (no fat tree) | `{4: all}` | **4** | 4 |
| **Full HammingMesh** | `{2: corners, 3: edges, 4: interior}` | **2** | 4 |

So within a Jellyfish *board* in the full HammingMesh, the worst-connected switch
(a corner) has only **2 intra-board links** — no better than a 2D-mesh corner —
because the perimeter spends ports on fat-tree uplinks (every node still uses all
4 ports total). The *standalone* Jellyfish board is 4-regular, so its minimum is
4. The distribution is invariant to the random draw (verified with `--builds`) and
to `ft_nodes` (gateways are always the perimeter).

## count_links.py

Counts the links of a **2D-mesh board vs a Jellyfish board** (same size) and
reports whether the mesh has greater/equal/less links, in two contexts. Links are
taken from SST's elaborated graph (`sst --run-mode=init --output-json`).

```bash
uv run python count_links.py                                   # both contexts, board 8x8 / global 4x4
uv run python count_links.py --context standalone --board_shape 8x8
uv run python count_links.py --context full --board_shape 8x8 --global_shape 4x4
```

**Findings:**

| context | mesh | jellyfish | relation |
|---------|------|-----------|----------|
| **Standalone board** (no fat tree, step-1 topos) | `R(C-1)+C(R-1)` — 8x8: **112** (degrees 2/3/4) | 4-regular `2N` — 8x8: **128** (all degree 4) | **mesh < jellyfish** |
| **Full-HammingMesh** intra-board (per board) | 8x8: **112**/board | 8x8: **112**/board | **EQUAL** |

So in isolation the Jellyfish board has *more* links (every node degree 4 vs the
mesh's degree-2/3 edges/corners), but inside the full HammingMesh the two are
*equal* per board — the Jellyfish reserves the same perimeter ports for fat-tree
uplinks that the mesh uses, so the intra-board link budgets match. Counts are
deterministic w.r.t. the random Jellyfish draw (verified with `--builds`).

## jellyfish_fattree_distance.py

Computes the **worst-case in-board distance from a node to the fat tree** for
Jellyfish local boards: for every board switch, its shortest hop count to the
nearest **gateway** (a board switch that holds a fat-tree uplink; gateway = 0),
then the maximum over all nodes of every board —
`max_boards max_nodes min_gateways hops(node, gateway)`. A large value means some
compute node sits deep inside its board, far from any uplink.

Like `check_connectivity.py`, it uses SST's own elaborated graph
(`sst --run-mode=init --output-json`, no simulation), so it is faithful to the
current `pymerlin.py` wiring and works for ft0/ft1/ft2 (the graph builds even
though ft1/ft2 crash at run time). Distance is hops to the nearest gateway node;
the fat-tree switch itself is `+1`.

```bash
# default: board 8x8, global 4x4 (1024 nodes), ft0, 5 random builds
uv run python jellyfish_fattree_distance.py
uv run python jellyfish_fattree_distance.py --ft_nodes 1 --builds 5
uv run python jellyfish_fattree_distance.py --graph path/to/graph.json   # analyze an existing dump
```

| Argument | Default | Description |
|----------|---------|-------------|
| `--board_shape` / `--global_shape` | `8x8` / `4x4` | board and global shapes |
| `--ft_nodes` | `0` | FT gateways per direction (0 = border) |
| `--builds` | `5` | random builds (jellyfish RNG is unseeded) |
| `--graph` | – | analyze an existing `graph.json` instead of dumping |

**Finding (board 8x8, global 4x4):** 28 perimeter gateways per board; worst-case
node→gateway distance is **2–3 hops** (mean ~2.3) and identical across ft0/ft1/ft2
(the `ft_nodes` magnitude does not change the gateway set — gateways are the board
perimeter). All nodes are reachable from a gateway. So no node is pathologically
far from the fabric — the worst-case fat-tree access depth is small.

## check_connectivity.py

Checks whether a generated HammingMesh (mesh or Jellyfish local boards) is
**physically connected** and whether its **routing can actually deliver** between
every node pair. Both checks operate on what **SST actually builds** — there is no
Python reconstruction of the topology or the routing (unlike `edgeBetweenness.py`,
see the caveat below).

### What it does

- **Part A — physical connectivity (BFS, no simulation):** dumps the elaborated
  component+link graph with `sst --run-mode=init --output-json`, builds it with
  NetworkX, and reports the number of connected components and any isolated
  switches/endpoints.
- **Part B — routing reachability (real run):** runs a tiny AllToAll
  (`AllPingPong`, all-to-all) and verifies SST's router delivered between every
  pair — the run must complete and every NIC must receive the same full byte
  total. It classifies failures as `SEGFAULT` / `SST FATAL` / `TIMEOUT (deadlock)`
  / short-or-missing NICs.

Because `pymerlin.py`'s Jellyfish RNG is unseeded, each build is a different
random instance; `--builds R` repeats to check it is *always* connected/routable.

### Usage

```bash
# One config
uv run python check_connectivity.py --board_shape 4x4 --global_shape 2x2 --jellyfish --ft_nodes 0

# Full suite: mesh control + jellyfish ft0/ft1/ft2, 3 random builds each
uv run python check_connectivity.py --board_shape 4x4 --global_shape 2x2 --suite --builds 3
```

| Argument | Default | Description |
|----------|---------|-------------|
| `--board_shape` / `--global_shape` | `4x4` / `4x4` | board and global shapes |
| `--jellyfish` / `--ft_nodes` | off / `0` | Jellyfish local boards; FT gateways per direction (0 = border) |
| `--suite` | off | run mesh + jellyfish ft0/ft1/ft2 |
| `--builds` | `3` | random builds per config |
| `--msg_size` | `8` | AllToAll message size (bytes) for the routing check |
| `--timeout` | `900` | per-run timeout (deadlock guard), seconds |

Artifacts (graph dump, AllToAll stdout/stderr) are kept under
`analysis/output/connectivity/<config>/build<N>/`.

### Finding (as of this writing)

Across 2x2 and 4x4 boards, multiple builds: **mesh** and **jellyfish `ft_nodes=0`
(border gateways)** are connected *and* routable. **Jellyfish `ft_nodes=1` and
`ft_nodes=2`** are physically **connected** but **NOT routable** — SST
**segfaults during routing** (the jellyfish-as-fat-tree-leaf path in `hamming.cc`).
So the `ft1`/`ft2` variants in `benchmarks/.../run_all_jellyfish.sh` do not
actually deliver traffic; only the border-gateway (`ft0`) jellyfish works.

### Caveat: edgeBetweenness.py is stale for `ft_nodes>0`

`edgeBetweenness.py` reconstructs the topology in pure Python. Its
`compute_jf_gateways` still uses the old scheme (`row_ft=range(N)`,
`col_ft=range(N,2N)`), whereas the current
`pymerlin.py._compute_jf_gateways` selects **perimeter** gateway nodes and ignores
the magnitude of `ft_nodes`. So `edgeBetweenness.py`'s graph is **wrong for
`ft_nodes>0`** (the `ft_nodes=0` / mesh cases still match). `check_connectivity.py`
avoids this by using SST's own graph dump. (Fixing `edgeBetweenness.py` is a
separate task.)

## edgeBetweenness.py

Computes edge betweenness centrality for the Hamming mesh topology,
supporting both 2D mesh and Jellyfish intra-board wiring modes.

### What it does

1. Reconstructs the full topology (board switches + fat tree switches) as an
   offline NetworkX graph
2. Computes edge betweenness centrality using **Brandes' algorithm**
3. Outputs a histogram showing the distribution of shortest paths across edges,
   plus summary statistics

### Usage

```bash
# Mesh topology, 2x2 boards in a 2x2 grid (16 board switches)
python3 edgeBetweenness.py --board_shape 2x2 --global_shape 2x2

# Jellyfish topology with 1 FT gateway per direction
python3 edgeBetweenness.py --board_shape 2x2 --global_shape 2x2 --jellyfish --ft_nodes 1

# Larger topology with custom output
python3 edgeBetweenness.py --board_shape 3x3 --global_shape 4x4 --output large_mesh.png

# Jellyfish with specific random seed
python3 edgeBetweenness.py --board_shape 3x3 --global_shape 3x3 --jellyfish --ft_nodes 1 --seed 123
```

### Arguments

| Argument | Default | Description |
|----------|---------|-------------|
| `--board_shape` | `2x2` | Dimensions of each board (e.g. `3x3`, `4x4`) |
| `--global_shape` | `2x2` | Grid of boards (e.g. `2x2` = 4 boards) |
| `--jellyfish` | off | Use Jellyfish random graph for intra-board wiring |
| `--ft_nodes` | `0` | Number of FT gateway nodes per direction per board (jellyfish only; 0 = border nodes) |
| `--fat_tree_radix` | `64` | Port count of fat tree switches |
| `--seed` | `42` | Random seed for jellyfish graph generation |
| `--output` | `edge_betweenness.png` | Output histogram filename |

### Algorithm: Brandes' Edge Betweenness

The script uses [Brandes' algorithm](https://doi.org/10.1080/0022250X.2001.9990249)
adapted for **edge** betweenness centrality. This is an algorithm with time complexity O(V * E) for unweighted graphs, where V is the
number of nodes and E is the number of edges.

The algorithm works as follows:

1. For each source node `s` (restricted to board switches):
   - Run BFS from `s` to compute:
     - `dist[v]`: shortest distance from `s` to each node `v`
     - `sigma[v]`: **number of shortest paths** from `s` to `v`
     - `pred[v]`: list of predecessors of `v` on shortest paths from `s`
   - Back-propagate dependencies in reverse BFS order:
     - For each node `v` (farthest first), distribute its dependency
       to predecessors proportionally to the number of shortest paths
       through each predecessor

2. Divide all values by 2 (since each unordered pair is visited from both
   directions in the BFS loop).

### Handling Multiple Shortest Paths

When multiple shortest paths exist between a pair of nodes (s, t), the
contribution to each edge is **split evenly** among all shortest paths.
This is the standard definition of betweenness centrality.

Concretely, if there are K shortest paths between s and t, and M of them
pass through edge e, then edge e receives a contribution of M/K from this
pair. This is computed automatically by the sigma-based proportional
splitting in Brandes' algorithm:

- `sigma[v]` counts the total number of shortest paths from `s` to `v`
- When back-propagating from `v` to predecessor `p`, the fraction
  `sigma[p] / sigma[v]` represents the proportion of shortest paths to `v`
  that come through `p`
- This fraction is multiplied by the accumulated dependency at `v`
  (which includes the `1.0` injection for valid target nodes)

This means that:
- **Pairs with a unique shortest path**: The edges on that path each get
  a full +1.0 contribution
- **Pairs with K equal-cost shortest paths**: Each edge on each path gets
  a fractional contribution that sums to 1.0 across all paths. Edges shared
  by multiple shortest paths get proportionally higher contributions

### Output

The script produces:

1. **Console output**: Summary statistics including node/edge counts,
   min/max/mean/std of edge betweenness, and the average shortest path
   fraction per edge

2. **Histogram plot**: Distribution of edge betweenness values across all
   edges in the topology. The x-axis shows the betweenness value, and the
   y-axis shows how many edges have that betweenness value

### Endpoints

Only **board switches** (compute nodes) are used as source/target pairs.
Fat tree switches are part of the graph and are traversed by shortest paths,
but they are not endpoints.
