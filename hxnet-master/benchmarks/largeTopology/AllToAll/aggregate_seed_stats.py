"""
Aggregate the multi-seed AllToAll sweep into the statistics the thesis committee
asked for: mean throughput over many seeds, standard deviation, min/max, 95%
confidence interval, and the best/worst seed, for each message size and topology.

This phase reports the variation due to JELLYFISH GRAPH GENERATION (the graph
seed). Gateway selection is the deterministic border set here; gateway-selection
variation is a later phase (needs the ft_nodes>0 routing fix).

Throughput metric (identical to parseAndPlotAllToAll.py and thesis Sec 4.4.1):
    per node i:  T_i = S*(N-1) / t_i           [bytes/ns]
    reported  :  T   = min_i T_i  * 8          [Gb/s]   (slowest node governs)

Reads (produced by run_seed_sweep.sh):
    integrated jellyfish : output/hx8_1024_jellyfish/g<seed>_w0/<size>
    integrated mesh      : output/hx8_1024/<size>
    isolated  jellyfish  : troubleshooting/output/jellyfish_64/g<seed>/<size>
    isolated  mesh       : troubleshooting/output/mesh_64/<size>

Writes:
    seed_stats.csv                              full per-(scale,topo,size) table
    plots/img/seed_stats_<scale>.png  (+ pdf)   mean line + 95% CI band vs mesh

Usage:  uv run python aggregate_seed_stats.py
"""

import os
import re
import glob
import math
import csv
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

try:
    from scipy import stats as _scipy_stats
except Exception:                       # scipy optional -> hardcoded t-table below
    _scipy_stats = None

# Two-sided t_0.975 critical values by degrees of freedom (for 95% CIs without scipy).
_T975 = {1: 12.706, 2: 4.303, 3: 3.182, 4: 2.776, 5: 2.571, 6: 2.447, 7: 2.365,
         8: 2.306, 9: 2.262, 10: 2.228, 11: 2.201, 12: 2.179, 13: 2.160, 14: 2.145,
         15: 2.131, 16: 2.120, 17: 2.110, 18: 2.101, 19: 2.093, 20: 2.086, 21: 2.080,
         22: 2.074, 23: 2.069, 24: 2.064, 25: 2.060, 26: 2.056, 27: 2.052, 28: 2.048,
         29: 2.045, 30: 2.042, 40: 2.021, 60: 2.000, 120: 1.980}


def _t_crit(df):
    """Two-sided 95% t critical value for df degrees of freedom."""
    if _scipy_stats is not None:
        return _scipy_stats.t.ppf(0.975, df)
    if df in _T975:
        return _T975[df]
    # nearest tabulated df not exceeding ours (slightly conservative); 1.96 asymptote
    candidates = [k for k in _T975 if k <= df]
    return _T975[max(candidates)] if candidates else 1.96

SCRIPT_DIR = Path(__file__).resolve().parent
SAVE_IMG = SCRIPT_DIR / "plots" / "img"
SAVE_PDF = SCRIPT_DIR / "plots" / "pdf"
CSV_OUT = SCRIPT_DIR / "seed_stats.csv"

_STATS_RE = re.compile(r"STATS (\d+) (\d+) EMBER (\d+) (\d+) (\d+) (\d+)")
_NODES_RE = re.compile(r"EMBER: numNodes=(\d+)")
_MOTIF_RE = re.compile(r"AllPingPong messageSize=(\d+)'")


def throughput_gbps(path):
    """min_i S*(N-1)/t_i * 8, or None if the run did not complete."""
    n_nodes = 1
    payload = None
    min_bw = math.inf
    try:
        text = open(path).read()
    except IOError:
        return None
    if "Simulation is complete" not in text or "STATS " not in text:
        return None
    for line in text.splitlines():
        m = _NODES_RE.search(line)
        if m:
            n_nodes = int(m.group(1))
        m = _MOTIF_RE.search(line)
        if m:
            payload = int(m.group(1)) * (n_nodes - 1)
        m = _STATS_RE.search(line)
        if m and payload:
            t = int(m.group(5))
            if t > 0 and payload / t < min_bw:
                min_bw = payload / t
    if min_bw is math.inf:
        return None
    return min_bw * 8.0


def collect_seeded(base, seed_glob):
    """{size: {seed: throughput}} from <base>/<seed_glob>/<size> directories."""
    out = {}
    for seed_dir in sorted(glob.glob(str(base / seed_glob))):
        m = re.search(r"g(\d+)", os.path.basename(seed_dir))
        if not m:
            continue
        seed = int(m.group(1))
        for f in os.listdir(seed_dir):
            if not f.isdigit():
                continue
            bw = throughput_gbps(os.path.join(seed_dir, f))
            if bw is None:
                continue
            out.setdefault(int(f), {})[seed] = bw
    return out


def collect_single(base):
    """{size: throughput} from <base>/<size> files (deterministic mesh)."""
    out = {}
    if not base.is_dir():
        return out
    for f in os.listdir(base):
        if not f.isdigit():
            continue
        bw = throughput_gbps(base / f)
        if bw is not None:
            out[int(f)] = bw
    return out


def summarize(seed_to_bw):
    """mean, sample std, min, max, 95% CI, best/worst seed for one message size."""
    items = sorted(seed_to_bw.items())
    seeds = [s for s, _ in items]
    vals = [v for _, v in items]
    n = len(vals)
    mean = sum(vals) / n
    if n > 1:
        var = sum((v - mean) ** 2 for v in vals) / (n - 1)
        std = math.sqrt(var)
        se = std / math.sqrt(n)
        half = _t_crit(n - 1) * se
    else:
        std = 0.0
        half = 0.0
    vmin, vmax = min(vals), max(vals)
    best_seed = seeds[vals.index(vmax)]
    worst_seed = seeds[vals.index(vmin)]
    return dict(n=n, mean=mean, std=std, min=vmin, max=vmax,
                ci_lo=mean - half, ci_hi=mean + half,
                best_seed=best_seed, worst_seed=worst_seed)


def bytes_label(b):
    for unit, div in (("MB", 1 << 20), ("KB", 1 << 10)):
        if b >= div:
            return "%d%s" % (b // div, unit)
    return "%dB" % b


def main():
    out_dir = SCRIPT_DIR / "output"
    tr_out = SCRIPT_DIR / "troubleshooting" / "output"

    # scale -> (jellyfish seeded dict, mesh single dict, node count)
    datasets = {
        "integrated_1024": (
            collect_seeded(out_dir / "hx8_1024_jellyfish", "g*_w*"),
            collect_single(out_dir / "hx8_1024"),
            1024,
        ),
        "isolated_64": (
            collect_seeded(tr_out / "jellyfish_64", "g*"),
            collect_single(tr_out / "mesh_64"),
            64,
        ),
    }

    rows = []
    for scale, (jf, mesh, nodes) in datasets.items():
        for size in sorted(jf):
            st = summarize(jf[size])
            rows.append(dict(scale=scale, topo="jellyfish", variation="graph_seed",
                             size=size, **st))
        for size in sorted(mesh):
            rows.append(dict(scale=scale, topo="mesh", variation="none", size=size,
                             n=1, mean=mesh[size], std=0.0, min=mesh[size],
                             max=mesh[size], ci_lo=mesh[size], ci_hi=mesh[size],
                             best_seed=-1, worst_seed=-1))

    # ---- CSV
    fields = ["scale", "topo", "variation", "size", "n", "mean", "std", "min",
              "max", "ci_lo", "ci_hi", "best_seed", "worst_seed"]
    with open(CSV_OUT, "w", newline="") as fp:
        w = csv.DictWriter(fp, fieldnames=fields)
        w.writeheader()
        for r in rows:
            w.writerow({k: (round(r[k], 4) if isinstance(r[k], float) else r[k])
                        for k in fields})
    print("Wrote %s (%d rows)" % (CSV_OUT, len(rows)))

    # ---- console summary
    for scale, (jf, mesh, nodes) in datasets.items():
        print("\n=== %s (%d nodes) ===" % (scale, nodes))
        for size in sorted(jf):
            st = summarize(jf[size])
            m = ("  mesh=%.1f" % mesh[size]) if size in mesh else ""
            print("  %-5s n=%2d  mean=%6.2f  std=%5.2f  min=%6.2f(seed%d)  "
                  "max=%6.2f(seed%d)  95%%CI=[%.2f,%.2f]%s"
                  % (bytes_label(size), st["n"], st["mean"], st["std"],
                     st["min"], st["worst_seed"], st["max"], st["best_seed"],
                     st["ci_lo"], st["ci_hi"], m))

    # ---- plots: mean line + 95% CI band (jellyfish) vs deterministic mesh
    SAVE_IMG.mkdir(parents=True, exist_ok=True)
    SAVE_PDF.mkdir(parents=True, exist_ok=True)
    for scale, (jf, mesh, nodes) in datasets.items():
        if not jf:
            continue
        sizes = sorted(jf)
        means = [summarize(jf[s])["mean"] for s in sizes]
        lo = [summarize(jf[s])["ci_lo"] for s in sizes]
        hi = [summarize(jf[s])["ci_hi"] for s in sizes]
        mins = [summarize(jf[s])["min"] for s in sizes]
        maxs = [summarize(jf[s])["max"] for s in sizes]
        n_seeds = max(summarize(jf[s])["n"] for s in sizes)

        fig, ax = plt.subplots()
        ax.fill_between(sizes, mins, maxs, alpha=0.15, color="C0", label="min-max")
        ax.fill_between(sizes, lo, hi, alpha=0.35, color="C0", label="95% CI")
        ax.plot(sizes, means, "-o", color="C0",
                label="Jellyfish mean (%d seeds)" % n_seeds)
        if mesh:
            msizes = sorted(set(mesh) & set(sizes)) or sorted(mesh)
            ax.plot(msizes, [mesh[s] for s in msizes], "-s", color="C3",
                    label="Mesh (deterministic)")
        ax.set_xscale("log", base=2)
        ax.set_xticks(sizes)
        ax.set_xticklabels([bytes_label(s) for s in sizes], rotation=45)
        ax.set_xlabel("Message size")
        ax.set_ylabel("Throughput (Gb/s)")
        ax.set_title("AllToAll throughput over %d graph seeds - %s (%d nodes)"
                     % (n_seeds, scale, nodes))
        ax.legend()
        fig.tight_layout()
        for d, ext in ((SAVE_IMG, "png"), (SAVE_PDF, "pdf")):
            fig.savefig(d / ("seed_stats_%s.%s" % (scale, ext)))
        plt.close(fig)
        print("Wrote plots/img/seed_stats_%s.png" % scale)


if __name__ == "__main__":
    main()
