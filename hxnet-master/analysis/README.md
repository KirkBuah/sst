# Topology Analysis Tools

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
