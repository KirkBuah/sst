# HammingMesh (HxMesh) Topology: Implementation Analysis

This document provides a detailed analysis of the HammingMesh topology implementation
in the SST (Structural Simulation Toolkit) simulator, as described in the SC'22 paper
*"HammingMesh: A Network Topology for Large-Scale Deep Learning"* by Hoefler et al.

---

## 1. Conceptual Overview

HammingMesh is a two-level hierarchical network topology designed specifically for
deep learning workloads. It combines:

- **Local level**: Inexpensive 2D meshes on PCB boards (short copper traces)
- **Global level**: Fat tree switches connecting boards row-wise and column-wise
  (long fiber cables)

The key insight is that deep learning communication patterns are toroidal (rings along
data, pipeline, and operator parallelism axes), so full global (bisection) bandwidth is
not needed. HxMesh provides high local bandwidth cheaply and adjustable global bandwidth.

### Naming convention

An HxMesh with an `a x b` board is called an **Hx(a*b)Mesh** (or **Hxa*b** for short):
- **Hx4Mesh** (Hx4): 4x4 boards (16 accelerators per board)
- **Hx2Mesh** (Hx2): 2x2 boards (4 accelerators per board)

---

## 2. Source Code Map

All paths are relative to `sst-elements-library-11.1.0/src/sst/elements/`.

### Core topology (C++ routing logic)
| File | Purpose |
|------|---------|
| `merlin/topology/hamming.h` | Class definition for `topo_hamming`, event types, coordinate helpers |
| `merlin/topology/hamming.cc` | Routing algorithms, address decomposition, wrap-around logic |

### Topology builder (Python, wires up the SST simulation)
| File | Purpose |
|------|---------|
| `merlin/pymerlin.py` (class `topoHamming`, lines 391-1037) | Creates all routers, links between mesh switches, and fat tree switches |

### Configuration and loading
| File | Purpose |
|------|---------|
| `ember/test/networkConfig.py` (class `HammingInfo`) | Parses board/global/fat-tree shape parameters |
| `ember/test/defaultParams.py` | Default network parameters (bandwidth, latency, buffer sizes) |
| `ember/test/emberLoad.py` | Entry point that loads topology and workload motifs |

### HxMesh-specific workload motifs
| File | Purpose |
|------|---------|
| `ember/mpi/motifs/emberhxmesh.h` / `.cc` | HxMesh-specific communication motif |

---

## 3. The Coordinate System

Every board switch is identified by a 4-tuple stored in `unique_pos[4]`:

```
unique_pos = [a, b, x, y]
              |  |  |  |
              |  |  |  +-- global column (which column of boards)
              |  |  +----- global row (which row of boards)
              |  +-------- local column within the board
              +----------- local row within the board
```

### Hx4 example: `boardShape=4x4, globalShape=8x8`

- Each board is a 4x4 mesh: `a` in [0..3], `b` in [0..3]
- Boards arranged in 8x8 grid: `x` in [0..7], `y` in [0..7]
- Total accelerators: 4 * 4 * 8 * 8 = **1024**

### Address decomposition (hamming.cc, lines 748-782)

Nodes are numbered linearly. The flat address is decomposed as follows:

```
board_index       = addr / (board_rows * board_cols)
position_in_board = addr % (board_rows * board_cols)

board_row_local   = position_in_board / board_cols     (a)
board_col_local   = position_in_board % board_cols     (b)
board_row_global  = board_index / global_cols           (x)
board_col_global  = board_index % global_cols           (y)
```

Boards are filled left-to-right, top-to-bottom. Within each board, rows are filled
left-to-right, top-to-bottom.

---

## 4. Switch Types and Port Assignments

### 4.1 Board (mesh) switches

Each board switch has exactly **5 ports**:

| Port | ID | Direction | Connects to |
|------|----|-----------|-------------|
| N    | 0  | North     | Neighbor switch one row up, OR column fat tree (if at top edge) |
| E    | 1  | East      | Neighbor switch one column right, OR row fat tree (if at right edge) |
| S    | 2  | South     | Neighbor switch one row down, OR column fat tree (if at bottom edge) |
| W    | 3  | West      | Neighbor switch one column left, OR row fat tree (if at left edge) |
| C    | 4  | NIC       | Host endpoint (1 accelerator per switch) |

Port mapping defined in `hamming.h` (lines 271-293):
```
N=0, E=1, S=2, W=3, C=4 (NIC)
```

Edge switches on a board serve a dual purpose: their edge-facing ports (the ones that
would go "off the board") connect to fat tree switches instead of mesh neighbors.
Specifically:
- **West edge** (b=0): Port W (3) connects to a **row** fat tree edge switch
- **East edge** (b=board_cols-1): Port E (1) connects to a **row** fat tree edge switch
- **North edge** (a=0): Port N (0) connects to a **column** fat tree edge switch
- **South edge** (a=board_rows-1): Port S (2) connects to a **column** fat tree edge switch

### 4.2 Fat tree switches

Fat tree switches have **no NIC ports**. All ports are router-to-router. They come in
two flavors depending on the fat tree size:

**Single-switch fat tree** (when `global_shape[dim] * 2 <= radix`):
All ports are down-ports connecting directly to board edge switches.

**Two-level fat tree** (when `global_shape[dim] * 2 > radix`):

| Level | Role | Down ports | Up ports |
|-------|------|------------|----------|
| 0 (Edge) | Connects to board edges | Ports 0 to `radix/2 - 1` | Ports `radix/2` to `radix - 1` |
| 1 (Core) | Connects edge switches | All ports go to edge switches | N/A |

Each fat tree switch stores:
- `fat_tree_id[0]`: tree type (0 = row tree, 1 = column tree)
- `fat_tree_id[1]`: which row or column this tree serves
- `fat_tree_pos[0]`: level (0 = edge, 1 = core)
- `fat_tree_pos[1]`: switch index within that level

---

## 5. Topology Construction (pymerlin.py)

The `topoHamming.build()` method (line 842) constructs the topology in three phases:

### Phase 1: Build all board meshes (lines 857-937)

For each board, for each switch in the board:

1. Compute the switch's local position (`my_loc_id`), global position (`my_glob_id`),
   and unique 4-tuple position (`unique_pos`).
2. Instantiate an `merlin.hr_router` with 5 ports.
3. Iterate over 4 directions (N=0, E=1, S=2, W=3):
   - Compute the neighbor's position by applying direction offsets:
     ```
     N: [-1, 0], E: [0, +1], S: [+1, 0], W: [0, -1]
     ```
   - If the neighbor is inside the board (`isInsideBoard`), create a link.
   - If the neighbor is outside the board, **leave the port unconnected** for now
     (it will be connected to a fat tree switch later).
4. Connect a NIC endpoint to port 4.

### Phase 2: Build row-wise fat trees (lines 941-987)

For each row of switches across all boards (total_rows = global_shape[0] * board_rows):

- Collect all board-edge switches along that row that are at the **West** (first column
  of a board, b=0) or **East** (last column of a board, b=board_cols-1) edge.
- If `global_shape[1] * 2 <= radix_fat_tree_switches`: create a **single switch**
  connecting all these edge ports.
- Otherwise: call `createRowFatTree()` to build a **two-level fat tree**.

Connection points:
- Board switches at **West edge** (b=0): their Port **W (3)** connects to the fat tree
- Board switches at **East edge** (b=max): their Port **E (1)** connects to the fat tree

Naming: `rowx{row}:{level}x{switch_id}` (e.g., `rowx3:0x1` = row 3, edge level, switch 1)

### Phase 3: Build column-wise fat trees (lines 989-1035)

For each column of switches across all boards (total_cols = global_shape[1] * board_cols):

- Collect all board-edge switches along that column at the **North** (a=0) or **South**
  (a=board_rows-1) edge.
- Same single-switch vs two-level logic as row trees.

Connection points:
- Board switches at **North edge** (a=0): their Port **N (0)** connects to the fat tree
- Board switches at **South edge** (a=max): their Port **S (2)** connects to the fat tree

Naming: `colx{col}:{level}x{switch_id}` (e.g., `colx5:1x0` = column 5, core level, switch 0)

### Visual summary for a single Hx4 board (4x4)

```
          Column Fat Tree (North)
          |    |    |    |
        +-N----N----N----N-+
        | 0,0  0,1  0,2  0,3 |
   Row  W                  E  Row
   Fat  | 1,0  1,1  1,2  1,3 |  Fat
   Tree W                  E  Tree
  (West)| 2,0  2,1  2,2  2,3 |(East)
        W                  E
        | 3,0  3,1  3,2  3,3 |
        +-S----S----S----S-+
          |    |    |    |
          Column Fat Tree (South)

  Each cell (a,b) is a board switch with a NIC on port C.
  Interior switches connect N/E/S/W to mesh neighbors.
  Edge switches connect to fat trees via their outward-facing port.
```

---

## 6. Routing

The main routing function `route_packet()` (hamming.cc, line 208) dispatches based on
switch type:

### 6.1 Board switch routing: `route_packet_mesh()` (line 294)

Given source and destination coordinates, the router determines candidate output ports
across four cases:

**Case 1 - Same board** (same x, same y):
Route within the local mesh using N/S/E/W directions. May wrap through the fat tree
if it's shorter (see Section 6.3).

**Case 2 - Different row of boards, same column** (different x, same y):
Head toward the nearest North or South board edge to enter the **column fat tree**.
Also considers E/W movement if the destination is at a different local column.

**Case 3 - Same row of boards, different column** (same x, different y):
Head toward the nearest East or West board edge to enter the **row fat tree**.
Also considers N/S movement if the destination is at a different local row.

**Case 4 - Different row and column of boards** (different x, different y):
Head toward the **nearest board edge** in any direction. Whichever edge (N, E, S, or W)
is closest becomes a candidate.

### 6.2 Adaptive port selection (lines 457-476)

When multiple candidate ports are valid, the switch picks the one with the **most
available output buffer credits**. This implements minimal adaptive routing -- the
packet always makes progress toward the destination, but the specific direction is
chosen based on current congestion.

```c++
for (size_t i = 0; i < candidate_ports_real.size(); i++) {
    int credits = output_credits[next_port * num_vcs + next_vc];
    if (credits > max_credits) {
        selected_port = next_port;
        max_credits = credits;
    }
}
```

### 6.3 Wrap-around decisions (lines 217-291)

Even when source and destination are on the **same board**, it may be shorter to exit
the board, traverse the fat tree, and re-enter from the opposite edge. The
`wrap_south()`, `wrap_north()`, `wrap_east()`, and `wrap_west()` functions compute
whether wrapping is beneficial by comparing:

- **Direct distance**: hops within the mesh
- **Wrap distance**: hops to board edge + fat tree hops (typically 2 for a two-level
  tree, 1 for a single-switch tree) + hops from opposite edge to destination

Example for `wrap_south()`:
```
distance_south = (board_rows - current_row - 1) + tree_hops + dest_row
distance_north = current_row - dest_row
wrap if distance_south <= distance_north
```

The `min-adaptive-nogl` routing algorithm disables all wrapping, keeping same-board
traffic strictly local.

### 6.4 Fat tree routing: `route_packet_tree()` (line 480)

Fat tree switches route packets back toward the correct board edge:

1. Determine which side of the destination board the packet should enter from:
   - **Row trees**: choose West entry (closer to column 0) or East entry (closer to
     last column), depending on the destination's local column position.
   - **Column trees**: choose North entry (closer to row 0) or South entry (closer to
     last row), depending on the destination's local row position.
2. Use `getOutputPortFor()` to find the correct output port(s).
3. Among valid ports, pick the one with the most credits (adaptive).

### 6.5 Deadlock avoidance

Two mechanisms prevent deadlocks:

**North-Last routing** (line 409-412):
When multiple candidate directions exist and the packet still needs to travel
East or West, the North direction is removed from candidates. North can only be
taken when it is the sole option. This prevents cyclic dependencies in the mesh.

```c++
if (candidate_ports.size() > 1 && board_col_here != board_col_dest) {
    // Remove N from candidate_ports
    candidate_ports.erase(
        std::remove(candidate_ports.begin(), candidate_ports.end(), 'N'),
        candidate_ports.end());
}
```

**Virtual channel escalation** (lines 419-449):
When a packet exits the mesh into the fat tree (crossing a board edge), the virtual
channel (VC) is incremented by 1. This separates mesh traffic from fat-tree-returning
traffic, breaking potential deadlock cycles. Three VCs are allocated per virtual
network (defined in `getVCsPerVN()`, hamming.h line 219).

---

## 7. Default Simulation Parameters

From `defaultParams.py` and `emberLoad.py`:

| Parameter | Default Value | Description |
|-----------|--------------|-------------|
| `link_bw` | 400 Gb/s (overridden to 1600 Gb/s for hx) | Link bandwidth |
| `nic_link_bw` | 1600 Gb/s | NIC injection bandwidth |
| `xbar_bw` | 3200 Gb/s | Crossbar bandwidth |
| `link_lat` | 40 ns | Link latency (same for local and global) |
| `flit_size` | 256 B | Flit size |
| `packet_size` | 8192 B | Packet size |
| `input_buf_size` | 32 MB | Input buffer size |
| `output_buf_size` | 32 MB | Output buffer size |

For HxMesh and torus topologies, the link bandwidth is set to 1600 Gb/s with 3200 Gb/s
crossbar bandwidth (emberLoad.py, lines 472-474). This models 4 links of 400 Gb/s each,
matching the paper's assumption of 16 x 400 Gb/s off-chip links per accelerator.

---

## 8. Benchmark Structure

Benchmarks live in `hxnet-master/benchmarks/` with subdirectories per topology size:

```
benchmarks/
  smallTopology/     (~1024 nodes)
    AllToAll/         - All-to-all traffic pattern
    AllReduce/        - Allreduce collective
    RandomPermutation/
    DLRM/             - Deep Learning Recommendation Model
    GPT3/             - GPT-3 workload
    ResNet/           - ResNet-152 workload
    Cosmo/            - CosmoFlow workload
  largeTopology/     (~16000 nodes)
  1536nodes/
```

Each benchmark folder contains:
- `launch<Name>.py` - Runs the SST simulation
- `parseAndPlot<Name>.py` - Parses output and generates plots

### Running a benchmark locally

```bash
# From benchmarks/smallTopology/AllToAll/
python3 launchAllToAll.py --topo hx4 --num_threads $(nproc)

# Quick run with fewer data points
python3 launchAllToAll.py --topo hx4 --num_threads $(nproc) --small_run
```

### Supported topologies for comparison

| Topology | boardShape | globalShape | Total nodes |
|----------|-----------|-------------|-------------|
| hx4      | 4x4       | 8x8         | 1024        |
| hx2      | 2x2       | 16x16       | 1024        |
| fattree  | -         | -           | 1024        |
| fattree50| -         | -           | 1024 (50% tapered) |
| fattree75| -         | -           | 1024 (75% tapered) |
| torus    | -         | 32x32       | 1024        |
| dragonfly| -         | 8:16:18:8   | 1024        |
| hyperx   | -         | 32x32       | 1024        |

---
## 9. Jellyfish Local Topology Variant

The Jellyfish variant replaces the structured 2D mesh within each board with a **random
regular graph** (Jellyfish topology), while keeping the global fat tree interconnect
unchanged.

### 9.1 Motivation

Random graphs (Jellyfish) can provide shorter average path lengths and higher bisection
bandwidth than structured meshes for the same node degree. By replacing only the local
board topology, we can evaluate whether random connectivity improves performance while
maintaining the HxMesh global hierarchy.

### 9.2 Node Count

The total number of nodes is **identical** to the standard HxMesh:

```
total_nodes = board_rows x board_cols x global_rows x global_cols x local_ports
```

For example, with `boardShape=2x2, globalShape=2x2, hostsPerRtr=1`:
- Each board has 2 x 2 = 4 switches
- There are 2 x 2 = 4 boards
- Total = 4 x 4 x 1 = **16 nodes**

The Jellyfish variant only changes how the 4 (or 16, for 4x4) switches within each
board are connected to each other. The number of switches, boards, and endpoints remains
unchanged.

### 9.3 Port Budget

Each board switch still has exactly **5 ports** (same as the mesh variant):

| Node type | Jellyfish links | Fat tree ports | NIC | Total |
|-----------|----------------|----------------|-----|-------|
| Interior  | 4              | 0              | 1   | 5     |
| Row-edge (first/last col) | 3 | 1 (port W=3 or E=1) | 1 | 5 |
| Col-edge (first/last row) | 3 | 1 (port N=0 or S=2) | 1 | 5 |
| Corner    | 2              | 2              | 1   | 5     |

Edge nodes reserve the **same ports** for fat tree connections as in the mesh:
- Port 0 (N) -> column fat tree (if row == 0)
- Port 1 (E) -> row fat tree (if col == last)
- Port 2 (S) -> column fat tree (if row == last)
- Port 3 (W) -> row fat tree (if col == 0)

Remaining (non-reserved) ports are wired as random intra-board Jellyfish links.

### 9.4 Graph Generation

The random graph is constructed per-board using a **greedy stub-pairing algorithm**:

1. For each node, determine which ports are free (not reserved for fat trees).
2. Build a list of (node, port) "stubs".
3. Shuffle the stubs randomly.
4. Greedily pair stubs: each stub is matched with another stub from a different node,
   avoiding self-loops and duplicate links between the same pair of nodes.
5. If unpaired stubs remain (the greedy algorithm can fail due to the no-duplicate
   constraint), retry with a new shuffle (up to 100 attempts).

This is implemented in `pymerlin.py` method `_generate_jellyfish_graph()`.

### 9.5 Table-Based Routing

Unlike the mesh (which uses directional routing based on coordinates), the Jellyfish
variant uses **pre-computed shortest-path routing tables**:

1. **BFS routing tables** are computed in Python (`_compute_routing_tables()`) for each
   source-destination pair within a board.
2. Tables are passed to the C++ router as a comma-separated string parameter
   `routing_table`, where `routing_table[dest_local_id] = next_hop_port`.
3. Each node also stores:
   - `nearest_row_edge`: local ID of the closest row-edge node (for reaching the row fat tree)
   - `nearest_col_edge`: local ID of the closest col-edge node (for reaching the col fat tree)

The C++ routing function `route_packet_jellyfish()` (hamming.cc) handles three cases:

- **Same board, same switch**: deliver to NIC port
- **Same board, different switch**: use `routing_table[dest_local_id]` to forward
- **Different board**: route toward the nearest edge node (row or col, depending on
  which fat tree is needed), then exit to the fat tree

### 9.6 Usage

**Command-line flag:**
```bash
# Via benchmark script:
python3 launchAllToAll_16nodes.py --jellyfish --small_run

# Via SST directly (add --jellyfish to model options):
sst --model-options="--topo=hx --boardShape=2x2 --globalShape=2x2 \
    --fatTreeShape=1:1,64 --hostsPerRtr=1 --jellyfish \
    --loadFile=loads/motif_file" emberLoad.py
```

**Output directory:** Results go to `output/hx2_16_jellyfish/` (appends `_jellyfish`
to the topology name).

### 9.7 Files Modified for Jellyfish Support

| File | Changes |
|------|---------|
| `merlin/topology/hamming.h` | Added `is_jellyfish`, `jf_routing_table`, `jf_row_ft_port`, `jf_col_ft_port`, `jf_nearest_row_edge`, `jf_nearest_col_edge` members; ELI params; `route_packet_jellyfish()` declaration |
| `merlin/topology/hamming.cc` | Constructor parses Jellyfish params; `route_packet_mesh()` branches to `route_packet_jellyfish()` when `is_jellyfish` is true |
| `merlin/pymerlin.py` | `_generate_jellyfish_graph()`, `_compute_routing_tables()`, `_find_nearest_edges()`, `_wire_jellyfish_board()` methods; conditional mesh/jellyfish wiring in `build()` |
| `ember/test/networkConfig.py` | `HammingInfo` accepts `use_jellyfish` parameter |
| `ember/test/emberLoad.py` | `--jellyfish` CLI flag, passes to `HammingInfo` |

---

## 10. Key Design Decisions in the Implementation

1. **Each accelerator has its own 4x4 switch**: Board switches act as both mesh routers
   and endpoint-attached switches (`hostsPerRtr=1`). This models accelerator packages
   with built-in limited packet forwarding (simple 4x4 switch as described in the paper).

2. **Dual-purpose edge ports**: The same physical port (N/E/S/W) connects either to a
   mesh neighbor or to a fat tree switch. The `isInsideBoard()` check during construction
   determines which. This mirrors the paper's design where board-edge accelerators
   connect off-board.

3. **Row and column trees are independent**: They serve orthogonal global dimensions.
   Row trees handle East-West global connectivity; column trees handle North-South.
   A packet may traverse at most one fat tree to reach its destination board.

4. **Credit-based adaptive routing**: Rather than deterministic routing, the implementation
   uses real-time buffer credit information to spread load across multiple minimal paths.
   This is important for avoiding hotspots in all-to-all traffic patterns.

5. **Flat node numbering mapped to 4D coordinates**: The simulation uses linear node IDs
   externally (for MPI rank assignment) but internally decomposes them into the [a,b,x,y]
   coordinate system for routing decisions.
