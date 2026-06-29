#!/bin/bash
# Regenerate the 4 datasets behind the AllToAll throughput-vs-message-size plot
# (board 4x4 x global 8x8 = 1024 nodes -> hx4_1024* output folders).
#
# Runs 4 configs sequentially. A failure in one config does NOT stop the others.
# All output (stdout+stderr) is tee'd to logs/regen_alltoall_YYYY-MM-DD_HH-MM-SS.log
#
# Usage:
#   bash regen_alltoall_plot.sh
#   THREADS=32 bash regen_alltoall_plot.sh      # override thread count
#   PY="python" bash regen_alltoall_plot.sh     # if you've activated the venv
#
# Tip: this is a long run -- launch it inside tmux/screen, or with nohup.

# NOTE: intentionally NO 'set -e' -- one failing run must not abort the rest.
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

# --- config -------------------------------------------------------------
BOARD="4x4"
GLOBAL="8x8"                       # 4x4 * 8x8 = 1024 nodes
THREADS="${THREADS:-$(nproc)}"
PY="${PY:-uv run python}"          # how to invoke python (default: uv)
LAUNCH="launchAllToAll_large.py"

# label : extra args  (label is just for the log/summary)
RUNS=(
    "hx4_1024|"
    "hx4_1024_jellyfish|--jellyfish"
    "hx4_1024_jellyfish_ft1|--jellyfish --ft_nodes 1"
    "hx4_1024_jellyfish_ft2|--jellyfish --ft_nodes 2"
)
# ------------------------------------------------------------------------

mkdir -p logs
LOGFILE="logs/regen_alltoall_$(date '+%Y-%m-%d_%H-%M-%S').log"

# Send everything from here on to both the console and the log file.
exec > >(tee -a "$LOGFILE") 2>&1

echo "=== AllToAll-large plot regeneration ==="
echo "Started at : $(date)"
echo "Board      : $BOARD   Global: $GLOBAL  (1024 nodes)"
echo "Threads    : $THREADS"
echo "Python      : $PY"
echo "Log file    : $LOGFILE"
echo

declare -a SUMMARY=()
overall_rc=0

for entry in "${RUNS[@]}"; do
    label="${entry%%|*}"
    extra="${entry#*|}"

    echo "============================================================"
    echo "[$(date '+%H:%M:%S')] START: $label"
    echo "  args: ${extra:-<none>}"
    echo "============================================================"

    # $extra is intentionally unquoted so multi-word args split correctly.
    $PY "$LAUNCH" \
        --board_shape "$BOARD" \
        --global_shape "$GLOBAL" \
        --num_threads "$THREADS" \
        $extra
    rc=$?

    if [ "$rc" -eq 0 ]; then
        echo "[$(date '+%H:%M:%S')] DONE : $label (exit 0)"
        SUMMARY+=("OK    $label")
    else
        echo "[$(date '+%H:%M:%S')] FAIL : $label (exit $rc)"
        SUMMARY+=("FAIL  $label (exit $rc)")
        overall_rc=1
    fi
    echo
done

echo "======================== SUMMARY ========================"
printf '  %s\n' "${SUMMARY[@]}"
echo "Finished at: $(date)"
echo "Log file   : $LOGFILE"
echo "========================================================="
echo
echo "To rebuild the plot from whatever data now exists, run:"
echo "  $PY parseAndPlotAllToAll.py"

exit "$overall_rc"
