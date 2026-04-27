"""
generate_poster_graphs.py — Poster-quality visualizations for MarginMind.

All axis limits, tick density, bin counts, and figure widths scale
automatically with however many test runs are in metrics_log.json.

Outputs (300 dpi PNG, saved to poster_graphs/):
  1_confidence_distribution.png
  2_pipeline_timeline.png
  3_time_comparison.png

Usage:
    python generate_poster_graphs.py

Requires:
    pip install matplotlib numpy scipy
"""

import json
import numpy as np
import matplotlib
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import matplotlib.ticker as mticker
from pathlib import Path

matplotlib.rcParams.update({
    "font.family":       "DejaVu Sans",
    "axes.spines.top":   False,
    "axes.spines.right": False,
})

# ── Paths ──────────────────────────────────────────────────────────────────
METRICS_FILE = Path(__file__).parent / "metrics_log.json"
OUTPUT_DIR   = Path(__file__).parent / "poster_graphs"
OUTPUT_DIR.mkdir(exist_ok=True)

# Palette
C_INDIGO = "#4F46E5"
C_GREEN  = "#10B981"
C_RED    = "#EF4444"
C_AMBER  = "#F59E0B"
C_VIOLET = "#8B5CF6"
C_GRAY   = "#6B7280"
C_LIGHT  = "#E5E7EB"

# Literature baseline: 12 min per short-answer submission
HUMAN_GRADING_SEC = 720

# Pipeline display cap: never show more than this many individual bars
MAX_PIPELINE_BARS = 10


# ── Data loading ───────────────────────────────────────────────────────────

def load_metrics() -> list:
    if METRICS_FILE.exists():
        try:
            with open(METRICS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            if data:
                print(f"Loaded {len(data)} evaluation record(s) from {METRICS_FILE.name}")
                return data
        except Exception as e:
            print(f"Could not read {METRICS_FILE.name}: {e}")
    print("No real data found — using representative sample data.")
    return _sample_data()


def _sample_data() -> list:
    """Realistic synthetic data for 8 grading sessions."""
    rng = np.random.default_rng(42)
    sessions = []
    for i in range(8):
        n_q   = int(rng.integers(5, 11))
        conf  = list(np.clip(rng.normal(0.79, 0.14, n_q * 3), 0.05, 1.0).round(3))
        scores = list(np.clip(rng.normal(0.73, 0.17, n_q), 0.0, 1.0).round(3))
        up  = round(float(rng.uniform(0.1, 0.5)), 3)
        ex  = round(float(rng.uniform(1.8, 4.5)), 3)
        ai  = round(float(rng.uniform(10, 35)),   3)
        sessions.append({
            "job_id":            f"sample-{i:03d}",
            "question_count":    n_q,
            "confidence_scores": conf,
            "overall_scores":    scores,
            "timing": {
                "upload_read_s":   up,
                "extraction_s":    ex,
                "ai_evaluation_s": ai,
                "total_s":         round(up + ex + ai, 3),
            },
        })
    return sessions


# ── Helpers ────────────────────────────────────────────────────────────────

def _fmt_time(seconds: float) -> str:
    """Return a human-readable time label (s / min / hr)."""
    if seconds >= 3600:
        return f"{seconds / 3600:.1f} hr"
    if seconds >= 60:
        return f"{seconds / 60:.1f} min"
    return f"{seconds:.1f} s"


def _smart_ylim(ax, data_max: float, padding_frac: float = 0.25) -> float:
    """Set y-axis upper limit to data_max * (1 + padding), return the limit."""
    ylim = data_max * (1 + padding_frac)
    ax.set_ylim(0, ylim)
    return ylim


def _save(fig: plt.Figure, filename: str) -> None:
    out = OUTPUT_DIR / filename
    fig.savefig(out, dpi=300, bbox_inches="tight")
    plt.close(fig)
    print(f"  Saved: {out}")


# ── Graph 1: Confidence score distribution ────────────────────────────────

def plot_confidence_distribution(records: list) -> None:
    all_conf = np.array([
        c for r in records for c in r.get("confidence_scores", [])
    ])
    if all_conf.size == 0:
        print("  [skip] No confidence scores to plot.")
        return

    n          = all_conf.size
    FLAG_THRESH = 0.6

    # ── Dynamic x-axis range ───────────────────────────────────────────
    # If real data clusters tightly (range < 0.35), zoom in so bars are
    # readable instead of squashed at one edge of a 0–1 axis.
    data_min  = float(all_conf.min())
    data_max  = float(all_conf.max())
    data_span = data_max - data_min

    if data_span < 0.35:
        pad    = max(0.05, data_span * 0.3)
        x_lo   = max(0.0, data_min - pad)
        x_hi   = min(1.0, data_max + pad)
    else:
        x_lo, x_hi = 0.0, 1.0

    # ── Dynamic bin count ──────────────────────────────────────────────
    # ~1 bin per 15 observations, capped between 10 and 30
    n_bins = int(np.clip(n // 15, 10, 30))

    # ── Dynamic y-axis label ───────────────────────────────────────────
    # Show percentage when n is large (>100) so the number stays readable
    use_pct = n > 100
    weights = (np.ones(n) / n * 100) if use_pct else None
    y_label = "% of Evaluations" if use_pct else "Number of Evaluations"

    fig, ax = plt.subplots(figsize=(8, 5))

    _, bins, patches = ax.hist(
        all_conf, bins=n_bins, range=(x_lo, x_hi),
        weights=weights,
        color=C_INDIGO, alpha=0.80, edgecolor="white", linewidth=0.6,
    )
    for patch, left in zip(patches, bins[:-1]):
        if left < FLAG_THRESH:
            patch.set_facecolor(C_RED)
            patch.set_alpha(0.75)

    # KDE overlay scaled to match histogram y-units
    try:
        from scipy.stats import gaussian_kde
        kde = gaussian_kde(all_conf, bw_method=0.15)
        xs  = np.linspace(x_lo, x_hi, 400)
        bin_w = (x_hi - x_lo) / n_bins
        scale = (100 if use_pct else n) * bin_w
        ax.plot(xs, kde(xs) * scale, color=C_INDIGO, lw=2.5)
    except ImportError:
        pass

    # Flag threshold line (only if visible in current x range)
    if x_lo < FLAG_THRESH < x_hi:
        ax.axvline(FLAG_THRESH, color=C_RED, linestyle="--", lw=2)

    # ── Stats box ──────────────────────────────────────────────────────
    pct_flagged = (all_conf < FLAG_THRESH).mean() * 100
    stats_txt = (
        f"n = {n} evaluations\n"
        f"Runs: {len(records)}\n"
        f"Mean:   {all_conf.mean():.3f}\n"
        f"Median: {np.median(all_conf):.3f}\n"
        f"Flagged (<{FLAG_THRESH}): {pct_flagged:.1f}%"
    )
    # Place stats box on whichever side has more empty space
    stats_x = 0.03 if all_conf.mean() > 0.7 else 0.63
    ax.text(
        stats_x, 0.97, stats_txt,
        transform=ax.transAxes, va="top", fontsize=9, color="#374151",
        bbox=dict(boxstyle="round,pad=0.45", facecolor="white",
                  edgecolor=C_LIGHT, linewidth=1.2),
    )

    legend_handles = [
        mpatches.Patch(facecolor=C_INDIGO, alpha=0.80,
                       label="High confidence (auto-graded)"),
        mpatches.Patch(facecolor=C_RED, alpha=0.75,
                       label=f"Flagged for review (< {FLAG_THRESH})"),
        matplotlib.lines.Line2D([0], [0], color=C_RED, linestyle="--",
                                lw=2, label=f"Flag threshold ({FLAG_THRESH})"),
    ]
    legend_loc = "upper left" if all_conf.mean() <= 0.7 else "upper right"
    ax.legend(handles=legend_handles, fontsize=9, loc=legend_loc)

    ax.set_xlim(x_lo, x_hi)
    ax.xaxis.set_major_locator(mticker.MaxNLocator(nbins=8, prune="both"))
    ax.yaxis.set_major_locator(mticker.MaxNLocator(nbins=6, integer=not use_pct))
    ax.set_xlabel("Confidence Score", fontsize=12)
    ax.set_ylabel(y_label, fontsize=12)
    ax.set_title(
        f"AI Evaluation Confidence Distribution  ({len(records)} runs, {n} evaluations)",
        fontsize=13, fontweight="bold", pad=14,
    )

    _save(fig, "1_confidence_distribution.png")


# ── Graph 2: Processing pipeline stacked bar ──────────────────────────────

STAGE_KEYS   = ["upload_read_s", "extraction_s", "ai_evaluation_s"]
STAGE_LABELS = ["Upload & Read", "Text Extraction", "AI Evaluation (Gemini)"]
STAGE_COLORS = [C_VIOLET, C_GREEN, C_AMBER]


def _timing_breakdown(record: dict) -> dict:
    t = record.get("timing", {})
    return {
        "upload_read_s":   t.get("upload_read_s",   0),
        "extraction_s":    t.get("extraction_s",    0),
        "ai_evaluation_s": t.get("ai_evaluation_s", 0),
    }


def plot_pipeline_timeline(records: list) -> None:
    if not records:
        print("  [skip] No records for pipeline chart.")
        return

    total_runs = len(records)

    # ── Cap visible bars ───────────────────────────────────────────────
    # When runs > MAX_PIPELINE_BARS, show only the most recent ones
    if total_runs > MAX_PIPELINE_BARS:
        visible   = records[-MAX_PIPELINE_BARS:]
        subtitle  = f"Last {MAX_PIPELINE_BARS} of {total_runs} runs"
        start_idx = total_runs - MAX_PIPELINE_BARS + 1
        run_labels = [f"Run {start_idx + i}" for i in range(len(visible))]
    else:
        visible    = records
        subtitle   = f"{total_runs} run{'s' if total_runs != 1 else ''}"
        run_labels = [f"Run {i + 1}" for i in range(total_runs)]

    n = len(visible)

    stage_data = {k: [] for k in STAGE_KEYS}
    for r in visible:
        bd = _timing_breakdown(r)
        for k in STAGE_KEYS:
            stage_data[k].append(bd[k])

    totals = np.array([
        r.get("timing", {}).get("total_s", sum(_timing_breakdown(r).values()))
        for r in visible
    ])

    # ── Dynamic figure width ───────────────────────────────────────────
    bar_width = 0.6
    fig_w = max(7, n * 1.2)
    fig, ax = plt.subplots(figsize=(fig_w, 5))

    x       = np.arange(n)
    bottoms = np.zeros(n)

    for key, label, color in zip(STAGE_KEYS, STAGE_LABELS, STAGE_COLORS):
        vals = np.array(stage_data[key])
        ax.bar(x, vals, bottom=bottoms, label=label,
               color=color, width=bar_width, edgecolor="white", linewidth=0.5)

        # ── Dynamic segment label threshold ───────────────────────────
        # Label a segment when it is > 8% of the tallest bar
        label_threshold = totals.max() * 0.08 if totals.max() > 0 else 0
        for xi, (v, b) in enumerate(zip(vals, bottoms)):
            if v > label_threshold:
                ax.text(xi, b + v / 2, f"{v:.1f}s",
                        ha="center", va="center", fontsize=7.5,
                        color="white", fontweight="bold")
        bottoms += vals

    # Total time label on top of each bar
    for xi, total in enumerate(totals):
        ax.text(xi, total + totals.max() * 0.02, f"{total:.1f}s",
                ha="center", va="bottom", fontsize=8.5, color="#374151")

    # ── Dynamic y-axis ─────────────────────────────────────────────────
    y_max = totals.max() * 1.20 if totals.max() > 0 else 10
    ax.set_ylim(0, y_max)
    ax.yaxis.set_major_locator(mticker.MaxNLocator(nbins=6, integer=True))

    # Rotate x labels when bars are many or labels are long
    rotate = n > 6
    ax.set_xticks(x)
    ax.set_xticklabels(run_labels, fontsize=9,
                       rotation=30 if rotate else 0,
                       ha="right" if rotate else "center")

    ax.set_ylabel("Time (seconds)", fontsize=12)
    ax.set_title(
        f"Processing Pipeline — Time per Stage  ({subtitle})",
        fontsize=13, fontweight="bold", pad=14,
    )
    ax.legend(fontsize=9, loc="upper right")

    _save(fig, "2_pipeline_timeline.png")


# ── Graph 3: Manual vs MarginMind time comparison ─────────────────────────

def plot_time_comparison(records: list) -> None:
    totals = [
        r["timing"]["total_s"]
        for r in records
        if isinstance(r.get("timing", {}).get("total_s"), (int, float))
    ]
    if not totals:
        print("  [skip] No timing data for time-comparison chart.")
        return

    avg_ai = float(np.mean(totals))
    min_ai = float(np.min(totals))
    max_ai = float(np.max(totals))
    n_runs = len(totals)

    # ── Dynamic y-axis ─────────────────────────────────────────────────
    # Scale to whichever is taller: human baseline or the AI max
    data_top = max(HUMAN_GRADING_SEC, max_ai)
    y_max    = data_top * 1.28
    offset   = data_top * 0.022   # label gap above bar, proportional

    # ── Smart unit for y-axis ticks ────────────────────────────────────
    # Stay in seconds (the natural unit). If human baseline is >> AI,
    # the AI bar is tiny — add a zoom inset instead of rescaling.
    show_inset = (HUMAN_GRADING_SEC / avg_ai) > 15

    categories = ["Manual Grading\n(Estimated*)", "MarginMind\n(Measured)"]
    values     = [HUMAN_GRADING_SEC, avg_ai]
    colors     = [C_GRAY, C_INDIGO]

    fig, ax = plt.subplots(figsize=(6, 5.5))

    bars = ax.bar(categories, values, color=colors, width=0.45,
                  edgecolor="white", linewidth=0.5)

    # Error bar (min–max spread) on MarginMind bar
    if max_ai > min_ai:
        ax.errorbar(
            1, avg_ai,
            yerr=[[avg_ai - min_ai], [max_ai - avg_ai]],
            fmt="none", color="#1E40AF", capsize=6, linewidth=2,
        )

    # Value labels above each bar
    for bar, val in zip(bars, values):
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            bar.get_height() + offset,
            _fmt_time(val),
            ha="center", va="bottom",
            fontsize=12, fontweight="bold", color="#111827",
        )

    # Speedup badge
    speedup = HUMAN_GRADING_SEC / avg_ai
    ax.text(
        0.5, 0.96,
        f"{speedup:.0f}x faster",
        transform=ax.transAxes, ha="center", va="top",
        fontsize=15, fontweight="bold", color=C_GREEN,
    )

    # ── Zoom inset when AI bar is too small to read ────────────────────
    if show_inset:
        from mpl_toolkits.axes_grid1.inset_locator import inset_axes
        ax_ins = inset_axes(ax, width="35%", height="30%", loc="center right",
                            bbox_to_anchor=(0.98, 0.0, 1, 1),
                            bbox_transform=ax.transAxes, borderpad=0)
        ax_ins.bar([0], [avg_ai], color=C_INDIGO, width=0.6, edgecolor="white")
        if max_ai > min_ai:
            ax_ins.errorbar(0, avg_ai,
                            yerr=[[avg_ai - min_ai], [max_ai - avg_ai]],
                            fmt="none", color="#1E40AF", capsize=4, linewidth=1.5)
        ins_top = max_ai * 1.5 if max_ai > 0 else 5
        ax_ins.set_ylim(0, ins_top)
        ax_ins.set_xticks([0])
        ax_ins.set_xticklabels(["MarginMind"], fontsize=7)
        ax_ins.yaxis.set_major_locator(mticker.MaxNLocator(nbins=4, integer=True))
        ax_ins.tick_params(labelsize=7)
        ax_ins.set_title("Zoomed", fontsize=7, pad=3)
        ax_ins.spines["top"].set_visible(False)
        ax_ins.spines["right"].set_visible(False)

    ax.set_ylim(0, y_max)
    ax.yaxis.set_major_locator(mticker.MaxNLocator(nbins=7, integer=True))
    ax.set_ylabel("Time per Submission (seconds)", fontsize=12)
    ax.set_title("Grading Time: Manual vs MarginMind",
                 fontsize=14, fontweight="bold", pad=14)

    fig.text(
        0.5, -0.04,
        "* Manual estimate: 12 min/submission (Brookhart & Nitko, 2008).\n"
        f"  MarginMind avg over {n_runs} run(s); "
        f"range {_fmt_time(min_ai)}–{_fmt_time(max_ai)}.",
        ha="center", fontsize=7.5, color=C_GRAY,
    )

    _save(fig, "3_time_comparison.png")


# ── Entry point ────────────────────────────────────────────────────────────

if __name__ == "__main__":
    records = load_metrics()

    print("\nGenerating graphs...")
    plot_confidence_distribution(records)
    plot_pipeline_timeline(records)
    plot_time_comparison(records)

    print(f"\nDone. All graphs saved to: {OUTPUT_DIR.resolve()}")
