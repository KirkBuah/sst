# Jellyfish-board routing changes

This documents how inter-/intra-board routing for **Jellyfish local boards** in the
modified HammingMesh (`topo_hamming`) differs from the original implementation, and
why. All changes are in `topology/hamming.cc`, `topology/hamming.h`, and the topology
builder `pymerlin.py` (`topoHamming._wire_jellyfish_board`). The 2D-mesh routing path
(`is_jellyfish == false`) is untouched.

## Problem being fixed

Benchmarks showed the Jellyfish variant getting **low throughput / poor load
balance** vs. the mesh variant. Three root causes in `route_packet_jellyfish`:

1. **Single-gateway funnel.** Every switch routed *all* inter-board traffic toward a
   single precomputed `nearest_row_edge` / `nearest_col_edge`. Although a board has
   the same number of fat-tree gateways as the mesh, only the nearest one was ever
   used, so egress collapsed onto one link per (switch, dimension) → congestion.
2. **Broken diagonal heuristic.** For destinations differing in *both* global row and
   column, the "pick the closer edge" code was stubbed dead code (`cur = -1; break;`)
   that always evaluated to taking the **row** fat tree. Diagonal traffic therefore
   always loaded row trees and never split across col trees.
3. **No intra-board fat-tree shortcut.** Same-board traffic always used the local
   shortest-path table and never considered a fat-tree wrap, unlike the mesh
   `wrap_north/south/east/west` cost model.

## What changed

### Inter-board gateway balancing (fixes #1)

The single `nearest_*_edge` funnel is replaced by **`jf_pick_gateway()`**, which
selects a gateway from the board-wide list as

```
gateway = gateways[ dest_board % gateways.size() ]
```

Because this depends only on the **destination board** and the board-wide gateway
list (identical on every switch of the board), every switch the packet visits agrees
on the same target gateway → the path stays loop-free, while different destinations
fan out across **all** gateways → load is balanced. Packets are routed toward the
chosen gateway with the existing shortest-path table; the gateway exits to the fat
tree via its `row_ft_port`/`col_ft_port` with the usual `vc+1` escalation.

### Real diagonal dimension choice (fixes #2)

The stubbed hop-count loops are deleted. For destinations differing in both row and
column, the first dimension is chosen deterministically from the destination
(`(row_dest + col_dest) & 1`), splitting diagonal traffic ~50/50 across row and col
trees (like the mesh diagonal case). After the first tree traversal the packet is no
longer diagonal and proceeds deterministically along the remaining dimension, so the
whole journey is still loop-free.

### Intra-board fat-tree shortcut (addresses #3)

`route_packet_jellyfish` Case 2 now optionally exits via a fat-tree **wrap-around**
link. This is gated to fire only when it is physically a wrap and genuinely useful:
the board is alone in its global row (`get_nrows()==1`, vertical/col wrap) or column
(`get_ncols()==1`, horizontal/row wrap), the switch is itself the relevant gateway,
the direct in-board path is long (`dist_table[dest] > 2`, which also prevents the
closer re-entry point from re-triggering it), and `routing_algo != "min-adaptive-nogl"`.

Note: for the usual multi-board global shapes (e.g. 8×8) there is **no** same-board
wrap, and a Jellyfish board's diameter is tiny, so this path is intentionally inert —
the direct shortest-path is essentially always best. It is implemented for parity
with the mesh `wrap_*` semantics.

## New topology parameters

Produced per board in `topoHamming._wire_jellyfish_board` and read in the
`topo_hamming` constructor:

| Param              | Scope        | Meaning                                                        |
|--------------------|--------------|---------------------------------------------------------------|
| `row_ft_gateways`  | board-wide   | CSV of local IDs of all row-FT gateway nodes                  |
| `col_ft_gateways`  | board-wide   | CSV of local IDs of all col-FT gateway nodes                  |
| `dist_table`       | per switch   | CSV `dist[d]` = hop distance from this switch to local node d |

`row_ft_gateways`/`col_ft_gateways` are derived from the same `reserved_ports` map
used for the mesh-equivalent gateway selection (`_compute_jf_gateways` /
`_get_reserved_ports`). `dist_table` is computed with the existing `_hop_distance`
helper over the per-board routing tables. The legacy `nearest_row_edge` /
`nearest_col_edge` params are still set and used as a fallback when the gateway lists
are absent.

## Why it is loop-free

- Intra-board routing still uses the precomputed **shortest-path** tables.
- Gateway choice and the diagonal dimension choice are **pure functions of the
  destination**, so every switch agrees on the same next target and the packet always
  makes monotone progress toward it.
- VC escalation at the board→tree boundary (`vc+1`) is unchanged.

Caveat: mixing per-destination row-first and col-first orders means row and col fat
trees can have cross-dependencies; like the mesh path this relies on VC separation.
Validate drain/no-hang on a small config (see plan verification).

## Reverting

Restore `route_packet_jellyfish` Cases 2–3 to use `jf_nearest_row_edge` /
`jf_nearest_col_edge` directly and drop the three new params + `jf_pick_gateway`.
The mesh path and all other topology code are unaffected.
