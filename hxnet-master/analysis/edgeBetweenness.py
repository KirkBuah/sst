"""
Edge betweenness analysis for the Hamming mesh topology.

Reconstructs the full topology (board switches + fat tree switches) as a
NetworkX graph, computes edge betweenness centrality using Brandes' algorithm,
and outputs a histogram plus summary statistics.

Supports both 2D mesh and Jellyfish intra-board wiring.

Usage:
    python3 edgeBetweenness.py --board_shape 2x2 --global_shape 2x2
    python3 edgeBetweenness.py --board_shape 2x2 --global_shape 2x2 --jellyfish --ft_nodes 1
    python3 edgeBetweenness.py --board_shape 3x3 --global_shape 4x4 --output my_plot.png
"""

import math
import os
import pathlib
import random
from argparse import ArgumentParser
from collections import defaultdict, deque
from datetime import datetime

import matplotlib.pyplot as plt
import networkx as nx
import numpy as np


# ---------------------------------------------------------------------------
# Helper functions (replicated from pymerlin.py, no SST dependency)
# ---------------------------------------------------------------------------


def get_offset_per_direction(direction):
    """Return [row_offset, col_offset] for direction 0=N, 1=E, 2=S, 3=W."""
    return [[-1, 0], [0, 1], [1, 0], [0, -1]][direction]


def is_inside_board(pos, dims):
    return 0 <= pos[0] < dims[0] and 0 <= pos[1] < dims[1]


def is_first_or_last(pos, limit):
    p = pos % limit
    return p == 0 or p == limit - 1


def is_first(pos, limit):
    return (pos % limit) == 0


def compute_jf_gateways(board_id, jf_ft_nodes):
    """Select fixed gateway positions for a Jellyfish board.
    Nodes 0..N-1 -> row FT gateways, Nodes N..2*N-1 -> col FT gateways."""
    N = jf_ft_nodes
    return {
        "row_ft": set(range(N)),
        "col_ft": set(range(N, 2 * N)),
    }


def get_reserved_ports(local_id, dims, jf_ft_nodes, gateway_map):
    """Determine which ports are reserved for fat tree connections."""
    reserved = {}
    if jf_ft_nodes > 0:
        if local_id in gateway_map.get("row_ft", set()):
            reserved[3] = "row_ft"
        if local_id in gateway_map.get("col_ft", set()):
            reserved[0] = "col_ft"
    else:
        row = local_id // dims[1]
        col = local_id % dims[1]
        if row == 0:
            reserved[0] = "col_ft"
        if col == dims[1] - 1:
            reserved[1] = "row_ft"
        if row == dims[0] - 1:
            reserved[2] = "col_ft"
        if col == 0:
            reserved[3] = "row_ft"
    return reserved


def count_jf_ft_connections(
    ft_type,
    fixed_axis,
    fixed_global_idx,
    total_varying,
    dims,
    global_shape,
    gateway_maps,
):
    """Count how many gateway connections exist for a given fat tree row or col."""
    count = 0
    for v in range(total_varying):
        if fixed_axis == "row":
            gr, gc = fixed_global_idx, v
        else:
            gr, gc = v, fixed_global_idx
        board_id = (gr // dims[0]) * global_shape[1] + (gc // dims[1])
        local_id = (gr % dims[0]) * dims[1] + (gc % dims[1])
        if local_id in gateway_maps.get(board_id, {}).get(ft_type, set()):
            count += 1
    return count


# ---------------------------------------------------------------------------
# Jellyfish graph generation (replicated from pymerlin.py lines 951-1137)
# ---------------------------------------------------------------------------


def generate_jellyfish_graph(num_nodes, reserved_ports_per_node, rng):
    """Generate a random graph for a board. Returns adjacency and port_map."""
    available = {}
    for n in range(num_nodes):
        reserved = reserved_ports_per_node.get(n, {})
        available[n] = [p for p in range(4) if p not in reserved]

    # Greedy non-multi-edge matching
    max_attempts = 100
    for _ in range(max_attempts):
        stubs = []
        for n in range(num_nodes):
            for p in available[n]:
                stubs.append((n, p))
        rng.shuffle(stubs)

        adjacency = {n: [] for n in range(num_nodes)}
        port_map = {n: {} for n in range(num_nodes)}
        used_pairs = set()
        paired = [False] * len(stubs)
        for i in range(len(stubs)):
            if paired[i]:
                continue
            n1, p1 = stubs[i]
            for j in range(i + 1, len(stubs)):
                if paired[j]:
                    continue
                n2, p2 = stubs[j]
                if n1 == n2:
                    continue
                pair_key = (min(n1, n2), max(n1, n2))
                if pair_key in used_pairs:
                    continue
                paired[i] = True
                paired[j] = True
                adjacency[n1].append((n2, p1, p2))
                adjacency[n2].append((n1, p2, p1))
                port_map[n1][p1] = n2
                port_map[n2][p2] = n1
                used_pairs.add(pair_key)
                break

        if sum(1 for p in paired if not p) == 0:
            return ensure_connected(adjacency, port_map, num_nodes)

    # Fallback: degree-ordered matching (allows multi-edges)
    stubs_per_node = {}
    for n in range(num_nodes):
        ports = list(available[n])
        rng.shuffle(ports)
        stubs_per_node[n] = ports

    adjacency = {n: [] for n in range(num_nodes)}
    port_map = {n: {} for n in range(num_nodes)}

    total_stubs = sum(len(s) for s in stubs_per_node.values())
    for _ in range(total_stubs // 2):
        remaining = [(len(s), n) for n, s in stubs_per_node.items() if s]
        if not remaining:
            break
        remaining.sort(reverse=True)
        n1 = remaining[0][1]
        p1 = stubs_per_node[n1].pop()

        found = False
        for _, n2 in remaining:
            if n2 == n1 or not stubs_per_node[n2]:
                continue
            p2 = stubs_per_node[n2].pop()
            adjacency[n1].append((n2, p1, p2))
            adjacency[n2].append((n1, p2, p1))
            port_map[n1][p1] = n2
            port_map[n2][p2] = n1
            found = True
            break

        if not found:
            pass  # stub has no eligible partner

    return ensure_connected(adjacency, port_map, num_nodes)


def ensure_connected(adjacency, port_map, num_nodes):
    """Perform edge swaps to merge disconnected components."""

    def get_component(start):
        comp = set()
        stack = [start]
        while stack:
            n = stack.pop()
            if n in comp:
                continue
            comp.add(n)
            for neighbor, _, _ in adjacency[n]:
                if neighbor not in comp:
                    stack.append(neighbor)
        return comp

    for _ in range(num_nodes * num_nodes):
        comp1 = get_component(0)
        if len(comp1) == num_nodes:
            break

        comp2_node = next(n for n in range(num_nodes) if n not in comp1)
        comp2 = get_component(comp2_node)

        edge1 = None
        for a in comp1:
            for b, pa, pb in adjacency[a]:
                if b in comp1:
                    edge1 = (a, b, pa, pb)
                    break
            if edge1:
                break

        edge2 = None
        for c in comp2:
            for d, pc, pd in adjacency[c]:
                if d in comp2:
                    edge2 = (c, d, pc, pd)
                    break
            if edge2:
                break

        if edge1 is None or edge2 is None:
            break

        a, b, pa, pb = edge1
        c, d, pc, pd = edge2

        for i, (n, mp, tp) in enumerate(adjacency[a]):
            if n == b and mp == pa:
                adjacency[a].pop(i)
                break
        for i, (n, mp, tp) in enumerate(adjacency[b]):
            if n == a and mp == pb:
                adjacency[b].pop(i)
                break
        port_map[a].pop(pa, None)
        port_map[b].pop(pb, None)

        for i, (n, mp, tp) in enumerate(adjacency[c]):
            if n == d and mp == pc:
                adjacency[c].pop(i)
                break
        for i, (n, mp, tp) in enumerate(adjacency[d]):
            if n == c and mp == pd:
                adjacency[d].pop(i)
                break
        port_map[c].pop(pc, None)
        port_map[d].pop(pd, None)

        adjacency[a].append((c, pa, pc))
        adjacency[c].append((a, pc, pa))
        port_map[a][pa] = c
        port_map[c][pc] = a

        adjacency[b].append((d, pb, pd))
        adjacency[d].append((b, pd, pb))
        port_map[b][pb] = d
        port_map[d][pd] = b

    return adjacency, port_map


# ---------------------------------------------------------------------------
# Topology graph construction
# ---------------------------------------------------------------------------


def build_topology_graph(
    dims, global_shape, use_jellyfish, jf_ft_nodes, fat_tree_radix, rng
):
    """Build a NetworkX graph representing the full Hamming mesh topology.

    Returns (G, board_node_ids) where board_node_ids is the set of node IDs
    that are board switches (as opposed to fat tree switches).
    """
    G = nx.Graph()
    board_node_ids = set()
    switch_per_board = dims[0] * dims[1]
    num_boards = global_shape[0] * global_shape[1]
    total_rows = global_shape[0] * dims[0]
    total_cols = global_shape[1] * dims[1]

    # Mapping: (global_row, global_col) -> node_id
    global_pos_to_id = {}
    # Gateway maps for jellyfish boards
    gateway_maps = {}  # board_id -> {'row_ft': set, 'col_ft': set}

    next_id = 0

    # --- Phase 1: Board switches ---
    for board_id in range(num_boards):
        board_row = board_id // global_shape[1]
        board_col = board_id % global_shape[1]
        glob_row_offset = board_row * dims[0]
        glob_col_offset = board_col * dims[1]

        # Compute jellyfish gateways for this board
        if use_jellyfish and jf_ft_nodes > 0:
            gateway_maps[board_id] = compute_jf_gateways(board_id, jf_ft_nodes)

        # Create board switch nodes
        board_start_id = next_id
        local_to_global = {}
        for local_id in range(switch_per_board):
            local_row = local_id // dims[1]
            local_col = local_id % dims[1]
            glob_row = glob_row_offset + local_row
            glob_col = glob_col_offset + local_col
            node_id = next_id
            G.add_node(
                node_id,
                type="board",
                board_id=board_id,
                local_id=local_id,
                global_pos=(glob_row, glob_col),
            )
            board_node_ids.add(node_id)
            global_pos_to_id[(glob_row, glob_col)] = node_id
            local_to_global[local_id] = node_id
            next_id += 1

        if use_jellyfish:
            # Generate random intra-board graph
            gw_map = gateway_maps.get(board_id, {})
            reserved = {}
            for lid in range(switch_per_board):
                reserved[lid] = get_reserved_ports(lid, dims, jf_ft_nodes, gw_map)

            adjacency, port_map = generate_jellyfish_graph(
                switch_per_board, reserved, rng
            )

            # Add edges from jellyfish adjacency (avoid duplicates)
            added = set()
            for n in range(switch_per_board):
                for neighbor, my_port, their_port in adjacency[n]:
                    edge_key = (min(n, neighbor), max(n, neighbor))
                    if edge_key not in added:
                        added.add(edge_key)
                        G.add_edge(
                            local_to_global[n],
                            local_to_global[neighbor],
                            link_type="intra_board",
                        )
        else:
            # Mesh wiring: connect in N and E directions to avoid duplicates
            for local_id in range(switch_per_board):
                local_row = local_id // dims[1]
                local_col = local_id % dims[1]
                for direction in range(2):  # 0=N, 1=E only
                    offset = get_offset_per_direction(direction)
                    partner_row = local_row + offset[0]
                    partner_col = local_col + offset[1]
                    if is_inside_board([partner_row, partner_col], dims):
                        partner_local = partner_row * dims[1] + partner_col
                        G.add_edge(
                            local_to_global[local_id],
                            local_to_global[partner_local],
                            link_type="intra_board",
                        )

    # --- Phase 2: Row fat trees ---
    for row in range(total_rows):
        if use_jellyfish and jf_ft_nodes > 0:
            nodes_count = count_jf_ft_connections(
                "row_ft", "row", row, total_cols, dims, global_shape, gateway_maps
            )
            if nodes_count == 0:
                continue
        else:
            nodes_count = global_shape[1] * 2

        # Collect gateway node IDs for this row
        gateways = []
        for col in range(total_cols):
            if use_jellyfish and jf_ft_nodes > 0:
                bid = (row // dims[0]) * global_shape[1] + (col // dims[1])
                lid = (row % dims[0]) * dims[1] + (col % dims[1])
                should_connect = lid in gateway_maps.get(bid, {}).get("row_ft", set())
            else:
                should_connect = is_first_or_last(col, dims[1])
            if should_connect:
                gateways.append(global_pos_to_id[(row, col)])

        next_id = _wire_fat_tree(
            G, gateways, nodes_count, fat_tree_radix, next_id, "row", row
        )

    # --- Phase 3: Column fat trees ---
    for col in range(total_cols):
        if use_jellyfish and jf_ft_nodes > 0:
            nodes_count = count_jf_ft_connections(
                "col_ft", "col", col, total_rows, dims, global_shape, gateway_maps
            )
            if nodes_count == 0:
                continue
        else:
            nodes_count = global_shape[0] * 2

        gateways = []
        for row in range(total_rows):
            if use_jellyfish and jf_ft_nodes > 0:
                bid = (row // dims[0]) * global_shape[1] + (col // dims[1])
                lid = (row % dims[0]) * dims[1] + (col % dims[1])
                should_connect = lid in gateway_maps.get(bid, {}).get("col_ft", set())
            else:
                should_connect = is_first_or_last(row, dims[0])
            if should_connect:
                gateways.append(global_pos_to_id[(row, col)])

        next_id = _wire_fat_tree(
            G, gateways, nodes_count, fat_tree_radix, next_id, "col", col
        )

    return G, board_node_ids


def _wire_fat_tree(G, gateways, nodes_count, radix, next_id, tree_type, idx):
    """Wire a fat tree (single-switch or 2-level) for a given row or column.

    Args:
        G: NetworkX graph to add nodes/edges to
        gateways: list of board node IDs that connect to this fat tree
        nodes_count: number of gateway connections
        radix: fat tree switch radix
        next_id: next available node ID
        tree_type: 'row' or 'col' (for labeling)
        idx: row or column index

    Returns:
        next_id after adding fat tree switches
    """
    if nodes_count <= radix:
        # Single switch: connect all gateways to one switch
        ft_node = next_id
        G.add_node(ft_node, type="ft_single", tree_type=tree_type, idx=idx)
        next_id += 1
        for gw in gateways:
            G.add_edge(ft_node, gw, link_type="ft_gateway")
    else:
        # 2-level fat tree
        down_ports = radix // 2
        num_edge = int(math.ceil(nodes_count / down_ports))
        tot_ports_up = num_edge * down_ports
        num_core = int(math.ceil(tot_ports_up / radix))

        # Create edge switches and wire gateways
        edge_ids = []
        gw_idx = 0
        for e in range(num_edge):
            ft_node = next_id
            G.add_node(
                ft_node, type="ft_edge", tree_type=tree_type, idx=idx, level=0, pos=e
            )
            edge_ids.append(ft_node)
            next_id += 1

            # Connect up to down_ports gateways to this edge switch
            count = 0
            while gw_idx < len(gateways) and count < down_ports:
                G.add_edge(ft_node, gateways[gw_idx], link_type="ft_gateway")
                gw_idx += 1
                count += 1

        # Create core switches
        core_ids = []
        for c in range(num_core):
            ft_node = next_id
            G.add_node(
                ft_node, type="ft_core", tree_type=tree_type, idx=idx, level=1, pos=c
            )
            core_ids.append(ft_node)
            next_id += 1

        # Wire edge-to-core: each core connects to every edge switch
        # with links_num links. In the graph, this is one edge per pair
        # (since we model connectivity, not port-level detail).
        for e_id in edge_ids:
            for c_id in core_ids:
                G.add_edge(e_id, c_id, link_type="ft_interswitch")

    return next_id


# ---------------------------------------------------------------------------
# Edge betweenness computation (Brandes' algorithm)
# ---------------------------------------------------------------------------


def compute_edge_betweenness(G, endpoint_nodes):
    """Compute edge betweenness centrality restricted to endpoint_nodes as
    sources and targets, using Brandes' algorithm.

    When multiple shortest paths exist between a pair (s, t), the contribution
    is split evenly among them. For example, if there are K shortest paths
    between s and t, and 3 of them pass through edge e, then edge e receives
    a contribution of 3/K from this pair.

    Args:
        G: NetworkX graph
        endpoint_nodes: set of node IDs to use as sources/targets

    Returns:
        edge_betweenness: dict mapping (u, v) with u < v to betweenness value
        num_pairs: number of (s, t) pairs with s < t
    """
    edge_betweenness = defaultdict(float)
    endpoint_set = set(endpoint_nodes)
    num_pairs = 0

    for s in endpoint_nodes:
        # BFS from s
        dist = {s: 0}
        sigma = defaultdict(float)  # number of shortest paths from s
        sigma[s] = 1.0
        pred = defaultdict(list)  # predecessors on shortest paths
        queue = deque([s])
        order = []

        while queue:
            v = queue.popleft()
            order.append(v)
            for w in G.neighbors(v):
                if w not in dist:
                    dist[w] = dist[v] + 1
                    queue.append(w)
                if dist[w] == dist[v] + 1:
                    sigma[w] += sigma[v]
                    pred[w].append(v)

        # Back-propagation
        delta = defaultdict(float)

        for v in reversed(order):
            # Inject 1.0 only for board-switch targets (not s itself)
            if v in endpoint_set and v != s:
                delta[v] += 1.0
                if v > s:  # count unordered pairs once
                    num_pairs += 1

            for p in pred[v]:
                frac = sigma[p] / sigma[v]
                contrib = frac * delta[v]
                edge_key = (min(p, v), max(p, v))
                edge_betweenness[edge_key] += contrib
                delta[p] += contrib

    # Each unordered pair (s, t) is counted from both directions (s->t and t->s)
    # so divide by 2 for undirected graph
    for e in edge_betweenness:
        edge_betweenness[e] /= 2.0

    return dict(edge_betweenness), num_pairs


# ---------------------------------------------------------------------------
# Plotting and statistics
# ---------------------------------------------------------------------------


def print_statistics(edge_betweenness, num_pairs, G, board_node_ids):
    """Print summary statistics. Values are already normalized (fraction of
    total shortest paths passing through each edge)."""
    values = list(edge_betweenness.values())
    # Include edges with 0 betweenness
    all_edges = set((min(u, v), max(u, v)) for u, v in G.edges())
    for e in all_edges:
        if e not in edge_betweenness:
            values.append(0.0)

    values = np.array(values)

    print("\n=== Edge Betweenness Statistics (fraction of total SPs) ===")
    print("Board switches:     %d" % len(board_node_ids))
    print("Total nodes:        %d" % G.number_of_nodes())
    print("Total edges:        %d" % G.number_of_edges())
    print("Source-target pairs: %d" % num_pairs)
    print("---")
    print("Min SP fraction:    %.6f" % values.min())
    print("Max SP fraction:    %.6f" % values.max())
    print("Mean SP fraction:   %.6f" % values.mean())
    print("Std SP fraction:    %.6f" % values.std())
    print("Median SP fraction: %.6f" % np.median(values))
    print()


def plot_histogram(edge_betweenness, G, output_file, title_extra=""):
    """Plot histogram of edge betweenness values."""
    # Include edges with 0 betweenness
    all_edges = set((min(u, v), max(u, v)) for u, v in G.edges())
    values = []
    for e in all_edges:
        values.append(edge_betweenness.get(e, 0.0))
    values = np.array(values)

    fig, ax = plt.subplots(figsize=(10, 6))

    num_bins = min(50, max(10, len(set(np.round(values, 2)))))
    ax.hist(values, bins=num_bins, edgecolor="black", alpha=0.7, color="steelblue")

    ax.set_xlabel("SP Fraction per Edge (SPs through edge / total SPs)", fontsize=12)
    ax.set_ylabel("Number of Edges", fontsize=12)
    ax.set_ylim(0, 1200)
    title = "Edge Betweenness Distribution"
    if title_extra:
        title += " — " + title_extra
    ax.set_title(title, fontsize=14)
    ax.grid(axis="y", alpha=0.3)

    mean_val = values.mean()
    median_val = np.median(values)
    ax.axvline(
        mean_val,
        color="red",
        linestyle="--",
        linewidth=1.5,
        label="Mean: %.6f" % mean_val,
    )
    ax.axvline(
        median_val,
        color="orange",
        linestyle="-.",
        linewidth=1.5,
        label="Median: %.6f" % median_val,
    )
    ax.legend(fontsize=11)

    plt.tight_layout()
    plt.savefig(output_file, dpi=150)
    print("Histogram saved to: %s" % output_file)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main():
    parser = ArgumentParser(
        description="Edge betweenness analysis for Hamming mesh topology"
    )
    parser.add_argument(
        "--board_shape", default="2x2", help="Board dimensions, e.g. 3x3 (default: 2x2)"
    )
    parser.add_argument(
        "--global_shape", default="2x2", help="Grid of boards, e.g. 4x4 (default: 2x2)"
    )
    parser.add_argument(
        "--jellyfish",
        action="store_true",
        help="Use Jellyfish random graph as intra-board topology",
    )
    parser.add_argument(
        "--ft_nodes",
        type=int,
        default=0,
        help="Jellyfish: FT gateway nodes per direction (0 = border nodes, default)",
    )
    parser.add_argument(
        "--fat_tree_radix",
        type=int,
        default=64,
        help="Radix of fat tree switches (default: 64)",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Random seed for Jellyfish graph (default: 42)",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Output plot filename. If not specified, "
        "auto-generates in output/ directory.",
    )
    parser.add_argument(
        "--output_dir", default="output", help="Output directory (default: output/)"
    )
    args = parser.parse_args()

    dims = [int(x) for x in args.board_shape.split("x")]
    global_shape = [int(x) for x in args.global_shape.split("x")]
    rng = random.Random(args.seed)

    total_nodes = dims[0] * dims[1] * global_shape[0] * global_shape[1]
    topo_type = "jellyfish" if args.jellyfish else "mesh"
    print(
        "Topology: %s, Board: %s, Global: %s => %d board switches"
        % (topo_type, args.board_shape, args.global_shape, total_nodes)
    )
    if args.jellyfish and args.ft_nodes > 0:
        print("FT gateway nodes per direction: %d" % args.ft_nodes)

    # Auto-generate output filename if not specified
    if args.output is None:
        script_dir = os.path.dirname(os.path.abspath(__file__))
        out_dir = os.path.join(script_dir, args.output_dir)
        pathlib.Path(out_dir).mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        name_parts = [
            "eb",
            "board_%s" % args.board_shape,
            "global_%s" % args.global_shape,
            topo_type,
        ]
        if args.jellyfish and args.ft_nodes > 0:
            name_parts.append("ft%d" % args.ft_nodes)
        name_parts.append(timestamp)
        output_file = os.path.join(out_dir, "_".join(name_parts) + ".png")
    else:
        output_file = args.output

    # Build graph
    print("Building topology graph...")
    G, board_node_ids = build_topology_graph(
        dims, global_shape, args.jellyfish, args.ft_nodes, args.fat_tree_radix, rng
    )
    print("Graph: %d nodes, %d edges" % (G.number_of_nodes(), G.number_of_edges()))

    # Verify connectivity
    if not nx.is_connected(G):
        components = list(nx.connected_components(G))
        print("WARNING: Graph is not connected! %d components" % len(components))
        for i, comp in enumerate(components):
            board_in_comp = len(comp & board_node_ids)
            print(
                "  Component %d: %d nodes (%d board switches)"
                % (i, len(comp), board_in_comp)
            )

    # Compute edge betweenness
    print("Computing edge betweenness (Brandes' algorithm)...")
    edge_betweenness, num_pairs = compute_edge_betweenness(G, board_node_ids)

    # Normalize: convert raw counts to fraction of total shortest paths
    if num_pairs > 0:
        for e in edge_betweenness:
            edge_betweenness[e] /= num_pairs

    # Output
    title_extra = "%s %s, global %s" % (topo_type, args.board_shape, args.global_shape)
    if args.jellyfish and args.ft_nodes > 0:
        title_extra += ", ft_nodes=%d" % args.ft_nodes

    print_statistics(edge_betweenness, num_pairs, G, board_node_ids)
    plot_histogram(edge_betweenness, G, output_file, title_extra)


if __name__ == "__main__":
    main()
