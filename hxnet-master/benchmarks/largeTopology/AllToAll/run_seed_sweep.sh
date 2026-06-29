#!/bin/bash
# Multi-seed AllToAll sweep for the Jellyfish-board statistical evaluation.
#
# Addresses the thesis-committee request to report the random topology as a
# DISTRIBUTION rather than a single draw. This phase varies the Jellyfish GRAPH
# seed (graph-generation variation); gateway selection is the deterministic
# border set (gateway-variation is a later phase that needs the ft_nodes>0 fix).
#
# It runs, for N seeds, on the SAME geometry as the thesis:
#   * Integrated 1024-node topology : 8x8 board, 4x4 global   (Sec 5.4 plateau)
#   * Isolated 64-node board        : 8x8 single board        (Sec 4.4)
# plus one deterministic mesh baseline at each scale.
#
# Usage:
#   bash run_seed_sweep.sh [N_SEEDS] [--small_run]
#     N_SEEDS     number of graph seeds, 1..N   (default 30)
#     --small_run only 2 message sizes (quick smoke of the whole pipeline)
#
# Outputs (consumed by aggregate_seed_stats.py):
#   integrated jellyfish : output/hx8_1024_jellyfish/g<seed>_w0/<size>
#   integrated mesh      : output/hx8_1024/<size>
#   isolated  jellyfish  : troubleshooting/output/jellyfish_64/g<seed>/<size>
#   isolated  mesh       : troubleshooting/output/mesh_64/<size>

set -o pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

N_SEEDS=30
SMALL_RUN=""
for arg in "$@"; do
    case "$arg" in
        --small_run) SMALL_RUN="--small_run" ;;
        ''|*[!0-9]*) ;;          # ignore non-numeric
        *) N_SEEDS="$arg" ;;
    esac
done

NUM_THREADS=$(nproc)
BOARD=8x8        # local board shape  (64-node Jellyfish board, matches thesis)
GLOBAL=4x4       # global shape       (16 boards -> 1024 nodes)

mkdir -p logs
LOGFILE="logs/seed_sweep_$(date '+%Y-%m-%d_%H-%M-%S').log"

log()  { echo "$@" | tee -a "$LOGFILE"; }
runit() {
    local label="$1"; shift
    log "------------------------------------------------------------"
    log "[$(date '+%H:%M:%S')] $label"
    log "  cmd: $*"
    "$@" >> "$LOGFILE" 2>&1
    local rc=$?
    [ $rc -ne 0 ] && log "[$(date '+%H:%M:%S')] FAILED (exit $rc): $label"
    return 0
}

log "=== Jellyfish multi-seed AllToAll sweep ==="
log "Started $(date) | seeds=1..$N_SEEDS | threads=$NUM_THREADS | small_run='$SMALL_RUN'"
log "Integrated: board=$BOARD global=$GLOBAL (1024 nodes) | Isolated: board=$BOARD (64 nodes)"

# ---------------------------------------------------------------- baselines (deterministic mesh)
runit "Integrated MESH baseline" \
    uv run python launchAllToAll_large.py --board_shape $BOARD --global_shape $GLOBAL \
        --num_threads $NUM_THREADS $SMALL_RUN
runit "Isolated MESH baseline (64-node board)" \
    uv run python troubleshooting/launch_local_topos.py --shape $BOARD --topos mesh \
        --num_threads $NUM_THREADS $SMALL_RUN

# ---------------------------------------------------------------- seed sweep (Jellyfish graph)
for s in $(seq 1 "$N_SEEDS"); do
    runit "Integrated JELLYFISH graph_seed=$s" \
        uv run python launchAllToAll_large.py --board_shape $BOARD --global_shape $GLOBAL \
            --jellyfish --graph_seed "$s" --gateway_seed 0 \
            --num_threads $NUM_THREADS $SMALL_RUN
    runit "Isolated JELLYFISH graph_seed=$s (64-node board)" \
        uv run python troubleshooting/launch_local_topos.py --shape $BOARD --topos jellyfish \
            --graph_seed "$s" --num_threads $NUM_THREADS $SMALL_RUN
done

log "=== Sweep finished $(date) ==="
log "Aggregate with: uv run python aggregate_seed_stats.py"
