#!/bin/bash
# Run all large topology jellyfish benchmarks sequentially.
# Usage: bash run_all_jellyfish.sh [--small_run]
#
# Logs go to logs/run_all_YYYY-MM-DD_HH-MM-SS.log
# Each simulation that fails is logged but does not stop the script.

set -o pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

SMALL_RUN=""
if [[ "$1" == "--small_run" ]]; then
    SMALL_RUN="--small_run"
fi

NUM_THREADS=$(nproc)
echo "Using $NUM_THREADS threads (all available cores)"

mkdir -p logs
LOGFILE="logs/run_all_$(date '+%Y-%m-%d_%H-%M-%S').log"

echo "=== Jellyfish benchmark suite ===" | tee "$LOGFILE"
echo "Started at $(date)" | tee -a "$LOGFILE"
echo "Log file: $LOGFILE" | tee -a "$LOGFILE"
echo "" | tee -a "$LOGFILE"

run() {
    local label="$1"
    local workdir="$2"
    shift 2
    echo "============================================================" | tee -a "$LOGFILE"
    echo "[$(date '+%H:%M:%S')] START: $label" | tee -a "$LOGFILE"
    echo "  dir: $workdir" | tee -a "$LOGFILE"
    echo "  cmd: $*" | tee -a "$LOGFILE"
    echo "============================================================" | tee -a "$LOGFILE"

    (cd "$workdir" && "$@") >> "$LOGFILE" 2>&1
    local rc=$?

    if [ $rc -ne 0 ]; then
        echo "[$(date '+%H:%M:%S')] FAILED (exit $rc): $label" | tee -a "$LOGFILE"
    else
        echo "[$(date '+%H:%M:%S')] DONE: $label" | tee -a "$LOGFILE"
    fi
    echo "" | tee -a "$LOGFILE"
}

# --- AllToAll ---
run "AllToAll - Mesh" "$SCRIPT_DIR/AllToAll" \
    uv run python launchAllToAll_large.py --num_threads $NUM_THREADS $SMALL_RUN

run "AllToAll - Jellyfish (border gateways)" "$SCRIPT_DIR/AllToAll" \
    uv run python launchAllToAll_large.py --jellyfish $SMALL_RUN

run "AllToAll - Jellyfish ft_nodes=1" "$SCRIPT_DIR/AllToAll" \
    uv run python launchAllToAll_large.py --jellyfish --ft_nodes 1 $SMALL_RUN

run "AllToAll - Jellyfish ft_nodes=2" "$SCRIPT_DIR/AllToAll" \
    uv run python launchAllToAll_large.py --jellyfish --ft_nodes 2 $SMALL_RUN

# --- AllReduce ---
run "AllReduce - Mesh" "$SCRIPT_DIR/AllReduce" \
    uv run python launchAllReduce.py --num_threads $NUM_THREADS $SMALL_RUN

run "AllReduce - Jellyfish (border gateways)" "$SCRIPT_DIR/AllReduce" \
    uv run python launchAllReduce.py --jellyfish $SMALL_RUN

run "AllReduce - Jellyfish ft_nodes=1" "$SCRIPT_DIR/AllReduce" \
    uv run python launchAllReduce.py --jellyfish --ft_nodes 1 $SMALL_RUN

run "AllReduce - Jellyfish ft_nodes=2" "$SCRIPT_DIR/AllReduce" \
    uv run python launchAllReduce.py --jellyfish --ft_nodes 2 $SMALL_RUN

# --- Random Permutation ---
run "RandomPerm - Mesh" "$SCRIPT_DIR/RandomPermutation" \
    uv run python launchRandomPerm.py --num_threads $NUM_THREADS

run "RandomPerm - Jellyfish (border gateways)" "$SCRIPT_DIR/RandomPermutation" \
    uv run python launchRandomPerm.py --num_threads $NUM_THREADS --jellyfish

run "RandomPerm - Jellyfish ft_nodes=1" "$SCRIPT_DIR/RandomPermutation" \
    uv run python launchRandomPerm.py --num_threads $NUM_THREADS --jellyfish --ft_nodes 1

run "RandomPerm - Jellyfish ft_nodes=2" "$SCRIPT_DIR/RandomPermutation" \
    uv run python launchRandomPerm.py --num_threads $NUM_THREADS --jellyfish --ft_nodes 2

echo "============================================================" | tee -a "$LOGFILE"
echo "All benchmarks finished at $(date)" | tee -a "$LOGFILE"
echo "Log saved to: $LOGFILE" | tee -a "$LOGFILE"
