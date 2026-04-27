"""
generate_poster_graphs.py — Poster-quality visualizations for MarginMind.

Outputs (300 dpi PNG, saved to poster_graphs/):
  1_confidence_distribution.png   — AI confidence score histogram
  2_pipeline_timeline.png         — processing stage stacked bar per run
  3_time_comparison.png           — manual grading vs MarginMind speed

Usage:
    python generate_poster_graphs.py

Requires:
    pip install matplotlib numpy scipy

If metrics_log.json is missing or empty, realistic sample data is used
automatically so you can preview the charts before running real sessions.
"""

import json
import numpy as np
import matplotlib
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from pathlib import Path

matplotlib.rcParams.update({
    "font.family":  "DejaVu Sans",
    "axes.spines.top":   False,
    "axes.spines.right": False,
})

# ── Paths & constants ──────────────────────────────────────────────────────
METRICS_FILE = Path(__file__).parent / "metrics_log.json"
OUTPUT_DIR   = Path(__file__).parent / "poster_graphs"
OUTPUT_DIR.mkdir(exist_ok=True)

# Palette
C_INDIGO  = "#4F46E5"
C_GREEN   = "#10B981"
C_RED     = "#EF4444"
C_AMBER   = "#F59E0B"
C_BLUE    = "#3B82F6"
C_VIOLET  = "#8B5CF6"
C_GRAY    = "#6B7280"
C_LIGHT   = "#E5E7EB"

# Literature estimate: 12 min per short-answer submission (manual grading)
HUMAN_GRADING_SEC = 720


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
        n_q    = int(rng.integers(5, 11))
        # Most confidence scores cluster high; a tail dips below 0.6
        conf   = list(np.clip(rng.normal(0.79, 0.14, n_q * 3), 0.05, 1.0).round(3))
        scores = list(np.clip(rng.normal(0.73, 0.17, n_q),      0.0,  1.0).round(3))
        upload   = round(float(rng.uniform(0.1, 0.5)),   3)
        extract  = round(float(rng.uniform(1.8, 4.5)),   3)
        ai_eval  = round(float(rng.uniform(10,  35)),    3)
        sessions.append({
            "job_id":           f"sample-{i:03d}",
            "question_count":   n_q,
            "confidence_scores": conf,
            "overall_scores":   scores,
            "timing": {
                "upload_read_s":   upload,
                "extraction_s":    extract,
                "ai_evaluation_s": ai_eval,
                "total_s":         round(upload + extract + ai_eval, 3),
            },
        })
    return sessions


# ── Graph 1: Confidence score distribution ────────────────────────────────

def plot_confidence_distribution(records: list) -> None:
    all_conf = np.array([
        c for r in records for c in r.get("confidence_scores", [])
    ])
    if all_conf.size == 0:
        print("  [skip] No confidence scores to plot.")
        return

    FLAG_THRESH = 0.6
    fig, ax = plt.subplots(figsize=(8, 5))

    _, bins, patches = ax.hist(
        all_conf, bins=20, range=(0, 1),
        color=C_INDIGO, alpha=0.80, edgecolor="white", linewidth=0.6,
    )
    for patch, left in zip(patches, bins[:-1]):
        if left < FLAG_THRESH:
            patch.set_facecolor(C_RED)
            patch.set_alpha(0.75)

    # Smooth KDE overlay
    try:
        from scipy.stats import gaussian_kde
        kde  = gaussian_kde(all_conf, bw_method=0.15)
        xs   = np.linspace(0, 1, 400)
        ys   = kde(xs) * all_conf.size * (bins[1] - bins[0])
        ax.plot(xs, ys, color=C_INDIGO, lw=2.5)
    except ImportError:
        pass  # scipy optional

    ax.axvline(FLAG_THRESH, color=C_RED, linestyle="--", lw=2)

    # Stats box
    pct_flagged = (all_conf < FLAG_THRESH).mean() * 100
    stats_txt = (
        f"n = {all_conf.size}\n"
        f"Mean:   {all_conf.mean():.2f}\n"
        f"Median: {np.median(all_conf):.2f}\n"
        f"Flagged (<{FLAG_THRESH}): {pct_flagged:.1f}%"
    )
    ax.text(
        0.63, 0.97, stats_txt,
        transform=ax.transAxes, va="top", fontsize=9, color="#374151",
        bbox=dict(boxstyle="round,pad=0.45", facecolor="white",
                  edgecolor=C_LIGHT, linewidth=1.2),
    )

    legend_handles = [
        mpatches.Patch(facecolor=C_INDIGO, alpha=0.80, label="High confidence (auto-graded)"),
        mpatches.Patch(facecolor=C_RED,    alpha=0.75, label=f"Flagged for review (< {FLAG_THRESH})"),
        matplotlib.lines.Line2D([0], [0], color=C_RED, linestyle="--", lw=2,
                                label=f"Flag threshold ({FLAG_THRESH})"),
    ]
    ax.legend(handles=legend_handles, fontsize=9, loc="upper left")

    ax.set_xlim(0, 1)
    ax.set_xlabel("Confidence Score", fontsize=12)
    ax.set_ylabel("Number of Evaluations", fontsize=12)
    ax.set_title("AI Evaluation Confidence Distribution", fontsize=14,
                 fontweight="bold", pad=14)

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

    run_labels  = [f"Run {i + 1}" for i in range(len(records))]
    stage_data  = {k: [] for k in STAGE_KEYS}

    for r in records:
        bd = _timing_breakdown(r)
        for k in STAGE_KEYS:
            stage_data[k].append(bd[k])

    x       = np.arange(len(run_labels))
    fig, ax = plt.subplots(figsize=(max(8, len(records) * 1.3), 5))

    bottoms = np.zeros(len(run_labels))
    for key, label, color in zip(STAGE_KEYS, STAGE_LABELS, STAGE_COLORS):
        vals = np.array(stage_data[key])
        ax.bar(x, vals, bottom=bottoms, label=label,
               color=color, width=0.6, edgecolor="white", linewidth=0.5)
        # Label segments wider than ~1 s
        for xi, (v, b) in enumerate(zip(vals, bottoms)):
            if v > 0.8:
                ax.text(xi, b + v / 2, f"{v:.1f}s",
                        ha="center", va="center", fontsize=7.5,
                        color="white", fontweight="bold")
        bottoms += vals

    # Total time label on top of each bar
    totals = np.array([
        r.get("timing", {}).get("total_s",
            sum(_timing_breakdown(r).values())) for r in records
    ])
    for xi, total in enumerate(totals):
        ax.text(xi, totals[xi] + 0.5, f"{total:.1f}s",
                ha="center", va="bottom", fontsize=8.5, color="#374151")

    ax.set_xticks(x)
    ax.set_xticklabels(run_labels, fontsize=10)
    ax.set_ylabel("Time (seconds)", fontsize=12)
    ax.set_title("Processing Pipeline — Time per Stage per Run",
                 fontsize=14, fontweight="bold", pad=14)
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

    avg_ai = np.mean(totals)
    min_ai = np.min(totals)
    max_ai = np.max(totals)

    categories = ["Manual Grading\n(Estimated*)", "MarginMind\n(Measured)"]
    values     = [HUMAN_GRADING_SEC, avg_ai]
    colors     = [C_GRAY, C_INDIGO]

    fig, ax = plt.subplots(figsize=(6, 5.5))

    bars = ax.bar(categories, values, color=colors, width=0.45,
                  edgecolor="white", linewidth=0.5)

    # Error bar on MarginMind bar (min–max range)
    ax.errorbar(
        1, avg_ai,
        yerr=[[avg_ai - min_ai], [max_ai - avg_ai]],
        fmt="none", color="#1E40AF", capsize=6, linewidth=2,
    )

    # Value labels above bars
    for bar, val in zip(bars, values):
        label = f"{val / 60:.1f} min" if val >= 60 else f"{val:.1f} s"
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            bar.get_height() + HUMAN_GRADING_SEC * 0.018,
            label, ha="center", va="bottom",
            fontsize=12, fontweight="bold", color="#111827",
        )

    # Speedup badge
    speedup = HUMAN_GRADING_SEC / avg_ai
    ax.text(
        0.5, 0.95,
        f"{speedup:.0f}× faster",
        transform=ax.transAxes, ha="center", va="top",
        fontsize=15, fontweight="bold", color=C_GREEN,
    )

    ax.set_ylabel("Time per Submission (seconds)", fontsize=12)
    ax.set_ylim(0, HUMAN_GRADING_SEC * 1.25)
    ax.set_title("Grading Time: Manual vs MarginMind",
                 fontsize=14, fontweight="bold", pad=14)

    fig.text(
        0.5, -0.03,
        "* Manual estimate: 12 min/submission (Brookhart & Nitko, 2008; "
        "typical short-answer exam).\n"
        f"  MarginMind avg over {len(totals)} run(s); "
        f"range {min_ai:.1f}–{max_ai:.1f} s.",
        ha="center", fontsize=7.5, color=C_GRAY,
    )

    _save(fig, "3_time_comparison.png")


# ── Helpers ────────────────────────────────────────────────────────────────

def _save(fig: plt.Figure, filename: str) -> None:
    out = OUTPUT_DIR / filename
    fig.savefig(out, dpi=300, bbox_inches="tight")
    plt.close(fig)
    print(f"  Saved: {out}")


# ── Entry point ────────────────────────────────────────────────────────────

if __name__ == "__main__":
    records = load_metrics()

    print("\nGenerating graphs…")
    plot_confidence_distribution(records)
    plot_pipeline_timeline(records)
    plot_time_comparison(records)

    print(f"\nDone. All graphs saved to: {OUTPUT_DIR.resolve()}")
