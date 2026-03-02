#!/usr/bin/env python3
"""Generate all documentation figures using synthetic data.

Run from the docs/ directory:
    python generate_figures.py

All figures are saved to _static/images/<section>/ as PNGs.
No ionique imports required — uses only numpy, matplotlib, and scipy.
"""

import os
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch
from scipy.signal import sosfiltfilt, butter, find_peaks

OUTDIR = os.path.join(os.path.dirname(__file__), "_static", "images")
RNG = np.random.default_rng(42)

# ---------------------------------------------------------------------------
# Synthetic signal generators
# ---------------------------------------------------------------------------

def make_noisy_signal(n=50000, baseline=1.5, noise_std=0.05, sampling_freq=100000):
    """Flat baseline with Gaussian noise."""
    t = np.arange(n) / sampling_freq
    current = RNG.normal(baseline, noise_std, n)
    return t, current


def make_synthetic_spikes(n=100000, baseline=1.5, noise_std=0.03,
                          n_spikes=12, spike_depth=0.6, spike_width=80,
                          sampling_freq=100000):
    """Baseline with downward spike events (nanopore-like blockades)."""
    t = np.arange(n) / sampling_freq
    current = RNG.normal(baseline, noise_std, n)
    positions = np.linspace(5000, n - 5000, n_spikes, dtype=int)
    widths = RNG.integers(spike_width // 2, spike_width * 2, n_spikes)
    depths = RNG.uniform(spike_depth * 0.5, spike_depth * 1.5, n_spikes)
    for pos, w, d in zip(positions, widths, depths):
        s, e = max(0, pos - w // 2), min(n, pos + w // 2)
        current[s:e] -= d
    return t, current, positions, widths, depths


def make_synthetic_square_blockades(n=100000, baseline=1.8, noise_std=0.03,
                                     n_events=8, blockade_depth=0.7,
                                     event_width=600, sampling_freq=100000):
    """Square-pulse blockade events (protein translocation-like)."""
    t = np.arange(n) / sampling_freq
    current = RNG.normal(baseline, noise_std, n)
    positions = np.linspace(6000, n - 6000, n_events, dtype=int)
    widths = RNG.integers(event_width // 2, event_width * 2, n_events)
    depths = RNG.uniform(blockade_depth * 0.7, blockade_depth * 1.3, n_events)
    for pos, w, d in zip(positions, widths, depths):
        s, e = max(0, pos - w // 2), min(n, pos + w // 2)
        current[s:e] -= d
    return t, current


def make_synthetic_multilevel(n=80000, baseline=2.0, noise_std=0.06,
                               sampling_freq=100000):
    """Messy multi-level signal resembling real nanopore blockade data.

    Includes variable dwell times, gradual transitions, baseline drift,
    1/f-like noise, and overlapping current levels — the kind of signal
    SpeedyStatSplit is designed to segment.
    """
    t = np.arange(n) / sampling_freq
    current = RNG.normal(baseline, noise_std, n)

    # Add slow baseline drift (1/f-like)
    drift = np.cumsum(RNG.normal(0, 0.0003, n))
    drift -= np.linspace(drift[0], drift[-1], n)  # remove overall trend
    current += drift

    # Blockade events with variable depths, widths, and noise levels
    events = [
        # (start, end, depth, extra_noise)
        (3000,  5500, 0.35, 0.04),    # shallow, short
        (6200,  9800, 0.55, 0.05),    # medium, wider
        (10500, 11200, 0.90, 0.03),   # deep, brief
        (11200, 14000, 0.55, 0.05),   # back to medium (multi-level event)
        (16000, 17500, 0.40, 0.07),   # shallow, noisy
        (20000, 28000, 0.60, 0.04),   # long dwell
        (28000, 29500, 0.85, 0.04),   # deep sub-state within event
        (29500, 33000, 0.60, 0.04),   # return to prior level
        (36000, 37000, 0.30, 0.08),   # barely visible, noisy
        (40000, 42000, 0.70, 0.05),   # clear blockade
        (42000, 42800, 1.10, 0.03),   # very deep sub-state
        (42800, 45000, 0.70, 0.05),   # back up
        (48000, 50000, 0.45, 0.06),   # moderate
        (53000, 58000, 0.55, 0.05),   # long event
        (58000, 59000, 0.80, 0.04),   # sub-state
        (59000, 62000, 0.55, 0.05),   # return
        (65000, 66500, 0.35, 0.07),   # shallow, noisy
        (69000, 72000, 0.65, 0.04),   # medium
        (72000, 72500, 0.95, 0.03),   # brief deep dip
        (72500, 75000, 0.65, 0.04),   # return
    ]
    for s, e, depth, enoise in events:
        if e > n:
            break
        # Gradual onset (exponential ramp over ~50 samples)
        ramp_len = min(50, (e - s) // 4)
        ramp = 1 - np.exp(-np.arange(ramp_len) / (ramp_len / 3))
        current[s:s + ramp_len] -= depth * ramp
        current[s + ramp_len:e] -= depth
        # Per-event noise variation
        current[s:e] += RNG.normal(0, enoise, e - s)

    return t, current


def make_synthetic_trace(n=500000, sampling_freq=100000, n_vsteps=5):
    """Realistic nanopore trace with voltage steps and events.

    Returns t, current, voltage, vstep_boundaries.
    """
    t = np.arange(n) / sampling_freq
    current = np.empty(n)
    voltage = np.empty(n)
    step_len = n // n_vsteps
    vstep_boundaries = []
    voltages = [0.05, 0.10, 0.15, 0.20, 0.10]

    for i in range(n_vsteps):
        s = i * step_len
        e = min((i + 1) * step_len, n)
        vstep_boundaries.append((s, e))
        v = voltages[i % len(voltages)]
        voltage[s:e] = v
        base = v * 10  # conductance ~ 10 nS
        current[s:e] = RNG.normal(base, 0.03, e - s)
        # Add some blockade events
        n_ev = RNG.integers(3, 8)
        margin = max(2000, (e - s) // 20)
        if e - s > 2 * margin:
            ev_positions = RNG.integers(s + margin, e - margin, n_ev)
            for pos in ev_positions:
                w = RNG.integers(100, 800)
                d = RNG.uniform(0.3, 0.8)
                es, ee = max(s, pos - w // 2), min(e, pos + w // 2)
                current[es:ee] -= d

    return t, current, voltage, vstep_boundaries


def _lowpass(signal, cutoff, fs, order=2):
    """Apply a Butterworth lowpass filter."""
    sos = butter(order, cutoff, btype='low', fs=fs, output='sos')
    return sosfiltfilt(sos, signal)


def _savefig(fig, *path_parts):
    """Save figure and close."""
    outpath = os.path.join(OUTDIR, *path_parts)
    os.makedirs(os.path.dirname(outpath), exist_ok=True)
    fig.savefig(outpath, dpi=150, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print(f"  saved {outpath}")


# ---------------------------------------------------------------------------
# Getting Started figures
# ---------------------------------------------------------------------------

def gen_getting_started():
    print("Getting Started figures...")
    t, current, voltage, vsteps = make_synthetic_trace(n=300000, n_vsteps=4)
    fs = 100000

    # workflow.png — raw trace with detected events highlighted
    filtered = _lowpass(current, 5000, fs)
    fig, axes = plt.subplots(2, 1, figsize=(10, 5), sharex=True,
                              gridspec_kw={"height_ratios": [3, 1]})
    axes[0].plot(t, filtered, color="#2c7bb6", linewidth=0.3, label="Current (filtered)")
    axes[0].set_ylabel("Current (nA)")
    axes[0].set_title("Nanopore trace — load, filter, detect events")
    axes[0].legend(loc="upper right", fontsize=8)
    axes[1].plot(t, voltage * 1000, color="#d7191c", linewidth=0.8)
    axes[1].set_ylabel("Voltage (mV)")
    axes[1].set_xlabel("Time (s)")
    fig.tight_layout()
    _savefig(fig, "getting_started", "workflow.png")

    # segment_tree.png — conceptual diagram
    fig, ax = plt.subplots(figsize=(10, 5.5))
    ax.set_xlim(-1.5, 12.5)
    ax.set_ylim(-0.2, 8)
    ax.axis("off")

    # Horizontal rank bands (dotted lines)
    for y in [5.6, 3.2, 0.8]:
        ax.axhline(y, color="#e0e0e0", linewidth=0.8, linestyle=":")

    # Rank labels — far left, vertically centered on each tier
    ax.text(-1.2, 6.6, 'rank="file"', fontsize=9, color="#999999",
            style="italic", va="center", ha="left")
    ax.text(-1.2, 4.2, 'rank="vstep"', fontsize=9, color="#999999",
            style="italic", va="center", ha="left")
    ax.text(-1.2, 1.8, 'rank="event"', fontsize=9, color="#999999",
            style="italic", va="center", ha="left")

    # Nodes positioned with generous spacing
    nodes = [
        ("TraceFile",  5.5, 6.6, 2.2, 0.85, "#4575b4", "white"),
        ("vstep 0",    2.5, 4.2, 1.7, 0.75, "#91bfdb", "black"),
        ("vstep 1",    5.5, 4.2, 1.7, 0.75, "#91bfdb", "black"),
        ("vstep 2",    8.5, 4.2, 1.7, 0.75, "#91bfdb", "black"),
        ("event 0",    1.5, 1.8, 1.5, 0.7,  "#fee090", "black"),
        ("event 1",    3.7, 1.8, 1.5, 0.7,  "#fee090", "black"),
        ("event 2",    5.5, 1.8, 1.5, 0.7,  "#fee090", "black"),
        ("event 3",    7.7, 1.8, 1.5, 0.7,  "#fee090", "black"),
    ]
    for label, x, y, w, h, fc, tc in nodes:
        rect = FancyBboxPatch((x - w / 2, y - h / 2), w, h,
                               boxstyle="round,pad=0.12", facecolor=fc,
                               edgecolor="#333333", linewidth=1.3)
        ax.add_patch(rect)
        ax.text(x, y, label, ha="center", va="center", fontsize=10,
                fontweight="bold", color=tc)

    # Arrows: parent → child
    arrows = [
        (5.5, 6.1,  2.5, 4.65),
        (5.5, 6.1,  5.5, 4.65),
        (5.5, 6.1,  8.5, 4.65),
        (2.5, 3.75, 1.5, 2.2),
        (2.5, 3.75, 3.7, 2.2),
        (5.5, 3.75, 5.5, 2.2),
        (8.5, 3.75, 7.7, 2.2),
    ]
    for x1, y1, x2, y2 in arrows:
        ax.annotate("", xy=(x2, y2), xytext=(x1, y1),
                     arrowprops=dict(arrowstyle="-|>", color="#555555",
                                     lw=1.4, mutation_scale=12))

    _savefig(fig, "getting_started", "segment_tree.png")


# ---------------------------------------------------------------------------
# Data Input figures
# ---------------------------------------------------------------------------

def gen_data_input():
    print("Data Input figures...")
    t, current, voltage, vsteps = make_synthetic_trace(n=400000, n_vsteps=5)
    fs = 100000

    # edh_trace.png — raw current trace
    fig, ax = plt.subplots(figsize=(10, 3))
    ax.plot(t, current, color="#2c7bb6", linewidth=0.2)
    ax.set_xlabel("Time (s)")
    ax.set_ylabel("Current (nA)")
    ax.set_title("Raw current trace from EDH file")
    _savefig(fig, "data_input", "edh_trace.png")

    # voltage_protocol.png — voltage and current
    fig, axes = plt.subplots(2, 1, figsize=(10, 4), sharex=True,
                              gridspec_kw={"height_ratios": [3, 1]})
    axes[0].plot(t, current, color="#2c7bb6", linewidth=0.2)
    axes[0].set_ylabel("Current (nA)")
    axes[1].plot(t, voltage * 1000, color="#d7191c", linewidth=0.8)
    axes[1].set_ylabel("Voltage (mV)")
    axes[1].set_xlabel("Time (s)")
    axes[0].set_title("Current and voltage protocol")
    fig.tight_layout()
    _savefig(fig, "data_input", "voltage_protocol.png")

    # vstep_segments.png — segments highlighted by color
    fig, ax = plt.subplots(figsize=(10, 3))
    colors = ["#2c7bb6", "#abd9e9", "#fdae61", "#d7191c", "#91bfdb"]
    for i, (s, e) in enumerate(vsteps):
        ax.plot(t[s:e], current[s:e], color=colors[i % len(colors)],
                linewidth=0.2, label=f"vstep {i+1} ({voltage[s]*1000:.0f} mV)")
    ax.set_xlabel("Time (s)")
    ax.set_ylabel("Current (nA)")
    ax.set_title("Voltage-step segments (auto-detected)")
    ax.legend(fontsize=7, loc="upper right", ncol=3)
    _savefig(fig, "data_input", "vstep_segments.png")


# ---------------------------------------------------------------------------
# Concepts figures
# ---------------------------------------------------------------------------

def gen_concepts():
    print("Concepts figures...")

    # tree_diagram.png — detailed tree with methods
    fig, ax = plt.subplots(figsize=(11, 6.5))
    ax.set_xlim(0, 14)
    ax.set_ylim(-0.5, 8.5)
    ax.axis("off")

    # Tree nodes
    nodes = [
        ("TraceFile\n(rank='file')", 7, 7.5, 2.2, 0.9, "#4575b4", "white"),
        ("vstep 0\n(rank='vstep')", 3, 5.0, 1.8, 0.8, "#91bfdb", "black"),
        ("vstep 1\n(rank='vstep')", 7, 5.0, 1.8, 0.8, "#91bfdb", "black"),
        ("vstep 2\n(rank='vstep')", 11, 5.0, 1.8, 0.8, "#91bfdb", "black"),
        ("event 0", 1.8, 2.5, 1.4, 0.7, "#fee090", "black"),
        ("event 1", 4.2, 2.5, 1.4, 0.7, "#fee090", "black"),
        ("event 2", 6.0, 2.5, 1.4, 0.7, "#fee090", "black"),
        ("event 3", 8.0, 2.5, 1.4, 0.7, "#fee090", "black"),
        ("event 4", 10.2, 2.5, 1.4, 0.7, "#fee090", "black"),
        ("event 5", 12.2, 2.5, 1.4, 0.7, "#fee090", "black"),
    ]
    for label, x, y, w, h, fc, tc in nodes:
        rect = FancyBboxPatch((x - w / 2, y - h / 2), w, h,
                               boxstyle="round,pad=0.12", facecolor=fc,
                               edgecolor="#333", linewidth=1.3)
        ax.add_patch(rect)
        ax.text(x, y, label, ha="center", va="center", fontsize=8,
                fontweight="bold", color=tc)

    # Tree edges
    conns = [
        (7, 7.0, 3, 5.45), (7, 7.0, 7, 5.45), (7, 7.0, 11, 5.45),
        (3, 4.55, 1.8, 2.9), (3, 4.55, 4.2, 2.9),
        (7, 4.55, 6.0, 2.9), (7, 4.55, 8.0, 2.9),
        (11, 4.55, 10.2, 2.9), (11, 4.55, 12.2, 2.9),
    ]
    for x1, y1, x2, y2 in conns:
        ax.annotate("", xy=(x2, y2), xytext=(x1, y1),
                     arrowprops=dict(arrowstyle="-|>", color="#555",
                                     lw=1.3, mutation_scale=11))

    # Method annotation: traverse_to_rank — placed in bottom-left, arrow to event row
    ax.annotate("traverse_to_rank('event')",
                xy=(6.0, 2.0), xytext=(1.0, 0.5),
                fontsize=9, color="#b2182b", fontweight="bold",
                arrowprops=dict(arrowstyle="-|>", color="#b2182b",
                                lw=1.5, ls="--", mutation_scale=12))
    # Highlight all event boxes with dashed border for traverse
    for x in [1.8, 4.2, 6.0, 8.0, 10.2, 12.2]:
        rect = FancyBboxPatch((x - 0.75, 2.5 - 0.4), 1.5, 0.8,
                               boxstyle="round,pad=0.12", facecolor="none",
                               edgecolor="#b2182b", linewidth=1.5, linestyle="--")
        ax.add_patch(rect)

    # Method annotation: climb_to_rank — placed in top-right, arrow to TraceFile
    ax.annotate("climb_to_rank('file')",
                xy=(7.8, 7.9), xytext=(11.5, 8.3),
                fontsize=9, color="#2166ac", fontweight="bold",
                arrowprops=dict(arrowstyle="-|>", color="#2166ac",
                                lw=1.5, ls="--", mutation_scale=12))

    # get_feature note at bottom
    ax.text(7, -0.2,
            "get_feature('sampling_freq')  —  searches self, then climbs ancestors until found",
            fontsize=8, color="#666", style="italic", ha="center")

    _savefig(fig, "concepts", "tree_diagram.png")

    # traversal.png — visual of traverse vs climb
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.5))
    for ax in axes:
        ax.set_xlim(-0.2, 6.2)
        ax.set_ylim(-0.3, 5.5)
        ax.axis("off")

    def _draw_mini_tree(ax):
        """Draw the same mini tree on both panels."""
        levels = [
            ("file", [(3, 4.5)], "#4575b4", "white"),
            ("vstep", [(1.5, 3.0), (4.5, 3.0)], "#91bfdb", "black"),
            ("event", [(0.5, 1.5), (2.3, 1.5), (3.7, 1.5), (5.5, 1.5)], "#fee090", "black"),
        ]
        for rank, positions, color, tc in levels:
            for x, y in positions:
                rect = FancyBboxPatch((x - 0.55, y - 0.3), 1.1, 0.6,
                                       boxstyle="round,pad=0.08", facecolor=color,
                                       edgecolor="#333", lw=1)
                ax.add_patch(rect)
                ax.text(x, y, rank, ha="center", va="center", fontsize=9,
                        fontweight="bold", color=tc)
        # Grey structural arrows
        for x1, y1, x2, y2 in [(3, 4.15, 1.5, 3.35), (3, 4.15, 4.5, 3.35),
                                 (1.5, 2.65, 0.5, 1.85), (1.5, 2.65, 2.3, 1.85),
                                 (4.5, 2.65, 3.7, 1.85), (4.5, 2.65, 5.5, 1.85)]:
            ax.annotate("", xy=(x2, y2), xytext=(x1, y1),
                         arrowprops=dict(arrowstyle="-|>", color="#bbbbbb",
                                         lw=1, mutation_scale=10))
        return levels

    # --- Left panel: traverse_to_rank ---
    ax = axes[0]
    ax.set_title("traverse_to_rank('event')", fontsize=11, fontweight="bold",
                  pad=10)
    _draw_mini_tree(ax)
    # Red arrows showing downward traversal
    for x1, y1, x2, y2 in [(3, 4.15, 1.5, 3.35), (3, 4.15, 4.5, 3.35),
                             (1.5, 2.65, 0.5, 1.85), (1.5, 2.65, 2.3, 1.85),
                             (4.5, 2.65, 3.7, 1.85), (4.5, 2.65, 5.5, 1.85)]:
        ax.annotate("", xy=(x2, y2), xytext=(x1, y1),
                     arrowprops=dict(arrowstyle="-|>", color="#d73027",
                                     lw=2.2, mutation_scale=12))
    # Dashed highlight on event boxes
    for x in [0.5, 2.3, 3.7, 5.5]:
        rect = FancyBboxPatch((x - 0.6, 1.5 - 0.35), 1.2, 0.7,
                               boxstyle="round,pad=0.08", facecolor="none",
                               edgecolor="#d73027", lw=2.5, ls="--")
        ax.add_patch(rect)
    ax.text(3, 0.2, "Returns: [event, event, event, event]",
            ha="center", fontsize=9, color="#d73027", fontweight="bold")

    # --- Right panel: climb_to_rank ---
    ax = axes[1]
    ax.set_title("climb_to_rank('file')", fontsize=11, fontweight="bold",
                  pad=10)
    _draw_mini_tree(ax)
    # Highlight start node
    rect = FancyBboxPatch((0.5 - 0.6, 1.5 - 0.35), 1.2, 0.7,
                           boxstyle="round,pad=0.08", facecolor="none",
                           edgecolor="#2166ac", lw=2.5)
    ax.add_patch(rect)
    ax.text(0.5, 0.6, "start here", ha="center", fontsize=8,
            color="#2166ac", fontweight="bold")
    # Blue arrows going up
    ax.annotate("", xy=(1.5, 2.65), xytext=(0.5, 1.85),
                arrowprops=dict(arrowstyle="-|>", color="#2166ac",
                                lw=2.5, mutation_scale=13))
    ax.annotate("", xy=(3, 4.15), xytext=(1.5, 3.35),
                arrowprops=dict(arrowstyle="-|>", color="#2166ac",
                                lw=2.5, mutation_scale=13))
    # Highlight result
    rect = FancyBboxPatch((3 - 0.6, 4.5 - 0.35), 1.2, 0.7,
                           boxstyle="round,pad=0.08", facecolor="none",
                           edgecolor="#2166ac", lw=2.5, ls="--")
    ax.add_patch(rect)
    ax.text(3, 5.2, "Returns: file", ha="center", fontsize=9,
            color="#2166ac", fontweight="bold")

    fig.tight_layout()
    _savefig(fig, "concepts", "traversal.png")


# ---------------------------------------------------------------------------
# Preprocessing figures
# ---------------------------------------------------------------------------

def gen_preprocessing():
    print("Preprocessing figures...")
    n = 60000
    fs = 100000
    t, current, _, widths, _ = make_synthetic_spikes(n=n, noise_std=0.08, sampling_freq=fs)

    # filter_comparison.png — same signal at different cutoff frequencies
    cutoffs = [1000, 5000, 10000]
    fig, axes = plt.subplots(len(cutoffs) + 1, 1, figsize=(10, 7), sharex=True)
    axes[0].plot(t[:30000], current[:30000], color="#999999", linewidth=0.3)
    axes[0].set_ylabel("Current (nA)")
    axes[0].set_title("Raw signal (no filter)")
    for i, cutoff in enumerate(cutoffs):
        filtered = _lowpass(current, cutoff, fs)
        axes[i + 1].plot(t[:30000], filtered[:30000], color="#2c7bb6", linewidth=0.4)
        axes[i + 1].set_ylabel("Current (nA)")
        axes[i + 1].set_title(f"Lowpass at {cutoff // 1000} kHz")
    axes[-1].set_xlabel("Time (s)")
    fig.tight_layout()
    _savefig(fig, "preprocessing", "filter_comparison.png")

    # trimmer_visual.png — show trimmed region at voltage step boundary
    t2, current2, voltage2, vsteps = make_synthetic_trace(n=200000, n_vsteps=4)
    trim_samples = 1000
    fig, ax = plt.subplots(figsize=(10, 3))
    s, e = vsteps[1]
    seg_t = t2[s:e]
    seg_c = current2[s:e]
    # Add a transient artifact at start
    seg_c[:trim_samples] += RNG.normal(0, 0.15, trim_samples) + 0.3 * np.exp(-np.arange(trim_samples) / 200)
    ax.plot(seg_t, seg_c, color="#2c7bb6", linewidth=0.3)
    ax.axvspan(seg_t[0], seg_t[trim_samples], color="#d7191c", alpha=0.2, label=f"Trimmed ({trim_samples} samples)")
    ax.axvline(seg_t[trim_samples], color="#d7191c", linewidth=1, linestyle="--")
    ax.set_xlabel("Time (s)")
    ax.set_ylabel("Current (nA)")
    ax.set_title("Trimmer — removing edge artifacts from voltage step start")
    ax.legend(fontsize=8)
    _savefig(fig, "preprocessing", "trimmer_visual.png")


# ---------------------------------------------------------------------------
# Parser figures — SpikeParser
# ---------------------------------------------------------------------------

def gen_spike_parser():
    print("SpikeParser figures...")
    n = 50000
    fs = 100000
    t, current, _, _, _ = make_synthetic_spikes(n=n, n_spikes=10, spike_depth=0.5,
                                                 spike_width=60, noise_std=0.03,
                                                 sampling_freq=fs)
    inverted = -current  # find_peaks finds maxima, we have dips

    def _plot_spikes(ax, data, t, height, title, color="#2c7bb6"):
        peaks, props = find_peaks(data, height=height)
        ax.plot(t, -data, color=color, linewidth=0.4)
        ax.plot(t[peaks], -data[peaks], "rv", markersize=5)
        ax.set_title(f"{title} (detected: {len(peaks)})", fontsize=9)
        ax.set_ylabel("nA")

    # height comparison
    fig, axes = plt.subplots(3, 1, figsize=(10, 6), sharex=True)
    for ax, h, label in zip(axes, [0.2, 0.4, 0.7],
                             ["height=0.2 (sensitive)", "height=0.4 (moderate)", "height=0.7 (strict)"]):
        _plot_spikes(ax, inverted - inverted.min(), t, h * (inverted.max() - inverted.min()), label)
    axes[-1].set_xlabel("Time (s)")
    fig.suptitle("SpikeParser — effect of height parameter", fontsize=11)
    fig.tight_layout()
    _savefig(fig, "parsers", "spike", "height_comparison.png")

    # prominence comparison
    fig, axes = plt.subplots(3, 1, figsize=(10, 6), sharex=True)
    for ax, p, label in zip(axes, [0.05, 0.2, 0.5],
                             ["prominence=0.05", "prominence=0.2", "prominence=0.5"]):
        peaks, _ = find_peaks(inverted, prominence=p)
        ax.plot(t, current, color="#2c7bb6", linewidth=0.4)
        ax.plot(t[peaks], current[peaks], "rv", markersize=5)
        ax.set_title(f"{label} (detected: {len(peaks)})", fontsize=9)
        ax.set_ylabel("nA")
    axes[-1].set_xlabel("Time (s)")
    fig.suptitle("SpikeParser — effect of prominence parameter", fontsize=11)
    fig.tight_layout()
    _savefig(fig, "parsers", "spike", "prominence_comparison.png")

    # distance comparison
    fig, axes = plt.subplots(3, 1, figsize=(10, 6), sharex=True)
    for ax, d, label in zip(axes, [10, 500, 3000],
                             ["distance=10", "distance=500", "distance=3000"]):
        peaks, _ = find_peaks(inverted, prominence=0.1, distance=d)
        ax.plot(t, current, color="#2c7bb6", linewidth=0.4)
        ax.plot(t[peaks], current[peaks], "rv", markersize=5)
        ax.set_title(f"{label} (detected: {len(peaks)})", fontsize=9)
        ax.set_ylabel("nA")
    axes[-1].set_xlabel("Time (s)")
    fig.suptitle("SpikeParser — effect of distance parameter", fontsize=11)
    fig.tight_layout()
    _savefig(fig, "parsers", "spike", "distance_comparison.png")

    # width comparison
    fig, axes = plt.subplots(3, 1, figsize=(10, 6), sharex=True)
    for ax, w, label in zip(axes, [(1, 30), (1, 100), (1, 500)],
                             ["width=(1, 30)", "width=(1, 100)", "width=(1, 500)"]):
        peaks, _ = find_peaks(inverted, prominence=0.1, width=w)
        ax.plot(t, current, color="#2c7bb6", linewidth=0.4)
        ax.plot(t[peaks], current[peaks], "rv", markersize=5)
        ax.set_title(f"{label} (detected: {len(peaks)})", fontsize=9)
        ax.set_ylabel("nA")
    axes[-1].set_xlabel("Time (s)")
    fig.suptitle("SpikeParser — effect of width parameter", fontsize=11)
    fig.tight_layout()
    _savefig(fig, "parsers", "spike", "width_comparison.png")

    # Full example
    fig, ax = plt.subplots(figsize=(10, 3))
    peaks, props = find_peaks(inverted, prominence=0.15, distance=100, width=(1, 200))
    ax.plot(t, current, color="#2c7bb6", linewidth=0.4, label="Current")
    ax.plot(t[peaks], current[peaks], "rv", markersize=6, label=f"Events ({len(peaks)})")
    ax.set_xlabel("Time (s)")
    ax.set_ylabel("Current (nA)")
    ax.set_title("SpikeParser — full detection example")
    ax.legend(fontsize=8)
    _savefig(fig, "parsers", "spike", "full_example.png")


# ---------------------------------------------------------------------------
# Parser figures — SpeedyStatSplit
# ---------------------------------------------------------------------------

def gen_speedy_statsplit():
    print("SpeedyStatSplit figures...")
    t, current = make_synthetic_multilevel(n=80000, sampling_freq=100000)

    def _variance_split(data, min_width=100, min_gain=0.01):
        """Simplified variance-based recursive splitting for illustration.

        min_gain is the absolute minimum variance-reduction gain to accept
        a split.  Lower values → more splits (finer segmentation).
        """
        boundaries = [0]
        stack = [(0, len(data))]
        while stack:
            s, e = stack.pop()
            seg_len = e - s
            if seg_len < 2 * min_width:
                continue
            best_gain = 0.0
            best_idx = None
            total_var = np.var(data[s:e])
            step = max(min_width // 3, 1)
            for idx in range(s + min_width, e - min_width, step):
                n_left = idx - s
                n_right = e - idx
                left_var = np.var(data[s:idx])
                right_var = np.var(data[idx:e])
                # Weighted-variance reduction (log-likelihood gain proxy)
                gain = (total_var -
                        (n_left * left_var + n_right * right_var) / seg_len)
                if gain > best_gain:
                    best_gain = gain
                    best_idx = idx
            if best_idx is not None and best_gain > min_gain:
                boundaries.append(best_idx)
                stack.append((s, best_idx))
                stack.append((best_idx, e))
        boundaries.append(len(data))
        boundaries.sort()
        return boundaries

    def _plot_segments(ax, t, data, bounds, label):
        """Plot segmented signal with colored segments and boundary lines."""
        n_seg = len(bounds) - 1
        cmap_colors = plt.cm.tab10(np.linspace(0, 1, min(n_seg, 10)))
        ax.plot(t, data, color="#cccccc", linewidth=0.2, zorder=1)
        for i in range(n_seg):
            s, e = bounds[i], bounds[i + 1]
            color = cmap_colors[i % len(cmap_colors)]
            ax.plot(t[s:e], data[s:e], color=color, linewidth=0.6, zorder=2)
            # Draw segment mean as horizontal line
            seg_mean = np.mean(data[s:e])
            ax.hlines(seg_mean, t[s], t[e - 1], color=color, linewidth=1.5,
                      alpha=0.7, zorder=3)
            if i > 0:
                ax.axvline(t[s], color="#d73027", linewidth=0.6, alpha=0.5,
                           zorder=4)
        ax.set_title(f"{label} ({n_seg} segments)", fontsize=9)
        ax.set_ylabel("nA")

    # min_width comparison — 3 very different values
    fig, axes = plt.subplots(3, 1, figsize=(10, 7), sharex=True)
    for ax, mw, label in zip(axes, [30, 400, 4000],
                              ["min_width=30 (fine)", "min_width=400 (medium)",
                               "min_width=4000 (coarse)"]):
        bounds = _variance_split(current, min_width=mw, min_gain=0.002)
        _plot_segments(ax, t, current, bounds, label)
    axes[-1].set_xlabel("Time (s)")
    fig.suptitle("SpeedyStatSplit — effect of min_width", fontsize=11,
                  fontweight="bold")
    fig.tight_layout()
    _savefig(fig, "parsers", "speedy", "min_width_comparison.png")

    # sensitivity comparison — varying min_gain threshold
    fig, axes = plt.subplots(3, 1, figsize=(10, 7), sharex=True)
    for ax, mg, label in zip(axes, [0.0005, 0.003, 0.02],
                              ["High sensitivity (min_gain=0.0005)",
                               "Medium sensitivity (min_gain=0.003)",
                               "Low sensitivity (min_gain=0.02)"]):
        bounds = _variance_split(current, min_width=150, min_gain=mg)
        _plot_segments(ax, t, current, bounds, label)
    axes[-1].set_xlabel("Time (s)")
    fig.suptitle("SpeedyStatSplit — sensitivity tuning", fontsize=11,
                  fontweight="bold")
    fig.tight_layout()
    _savefig(fig, "parsers", "speedy", "window_width_comparison.png")

    # parameter interaction — min_width + min_gain together
    fig, axes = plt.subplots(3, 1, figsize=(10, 7), sharex=True)
    configs = [
        (30, 0.0005, "Aggressive: min_width=30, low threshold"),
        (200, 0.003,  "Balanced: min_width=200, medium threshold"),
        (2000, 0.015, "Conservative: min_width=2000, high threshold"),
    ]
    for ax, (mw, mg, label) in zip(axes, configs):
        bounds = _variance_split(current, min_width=mw, min_gain=mg)
        _plot_segments(ax, t, current, bounds, label)
    axes[-1].set_xlabel("Time (s)")
    fig.suptitle("SpeedyStatSplit — parameter interaction", fontsize=11,
                  fontweight="bold")
    fig.tight_layout()
    _savefig(fig, "parsers", "speedy", "sensitivity_comparison.png")

    # Full example — balanced settings
    fig, ax = plt.subplots(figsize=(10, 3.5))
    bounds = _variance_split(current, min_width=200, min_gain=0.003)
    _plot_segments(ax, t, current, bounds, "")
    ax.set_xlabel("Time (s)")
    ax.set_ylabel("Current (nA)")
    n_seg = len(bounds) - 1
    ax.set_title(f"SpeedyStatSplit — full example ({n_seg} segments detected)",
                  fontsize=11, fontweight="bold")
    _savefig(fig, "parsers", "speedy", "full_example.png")


# ---------------------------------------------------------------------------
# Parser figures — AutoSquareParser
# ---------------------------------------------------------------------------

def gen_autosquare_parser():
    print("AutoSquareParser figures...")
    t, current = make_synthetic_square_blockades(n=100000, baseline=1.8,
                                                  blockade_depth=0.7, event_width=600)

    def _detect_square(data, threshold_frac, baseline_est=None):
        """Simplified square-blockade detection."""
        if baseline_est is None:
            baseline_est = np.median(data)
        threshold = baseline_est * threshold_frac
        below = data < threshold
        boundaries = []
        in_event = False
        start = 0
        for i in range(len(below)):
            if below[i] and not in_event:
                start = i
                in_event = True
            elif not below[i] and in_event:
                if i - start > 20:
                    boundaries.append((start, i))
                in_event = False
        return boundaries

    # threshold_baseline comparison
    fig, axes = plt.subplots(3, 1, figsize=(10, 6), sharex=True)
    for ax, tb, label in zip(axes, [0.9, 0.7, 0.5],
                              ["threshold_baseline=0.9", "threshold_baseline=0.7", "threshold_baseline=0.5"]):
        events = _detect_square(current, tb)
        ax.plot(t, current, color="#2c7bb6", linewidth=0.3)
        baseline = np.median(current)
        ax.axhline(baseline * tb, color="#d73027", linewidth=0.8, linestyle="--", alpha=0.7)
        for s, e in events:
            ax.axvspan(t[s], t[e], color="#fee090", alpha=0.5)
        ax.set_title(f"{label} (detected: {len(events)})", fontsize=9)
        ax.set_ylabel("nA")
    axes[-1].set_xlabel("Time (s)")
    fig.suptitle("AutoSquareParser — effect of threshold_baseline", fontsize=11)
    fig.tight_layout()
    _savefig(fig, "parsers", "autosquare", "threshold_comparison.png")

    # conductance comparison
    fig, axes = plt.subplots(2, 1, figsize=(10, 4), sharex=True)
    for ax, ec, label in zip(axes, [1.5, 2.5],
                              ["expected_conductance=1.5 nS", "expected_conductance=2.5 nS"]):
        events = _detect_square(current, 0.7)
        ax.plot(t, current, color="#2c7bb6", linewidth=0.3)
        for s, e in events:
            ax.axvspan(t[s], t[e], color="#fee090", alpha=0.5)
        ax.set_title(f"{label} (events: {len(events)})", fontsize=9)
        ax.set_ylabel("nA")
    axes[-1].set_xlabel("Time (s)")
    fig.suptitle("AutoSquareParser — expected_conductance", fontsize=11)
    fig.tight_layout()
    _savefig(fig, "parsers", "autosquare", "conductance_comparison.png")

    # Full example
    fig, ax = plt.subplots(figsize=(10, 3))
    events = _detect_square(current, 0.7)
    ax.plot(t, current, color="#2c7bb6", linewidth=0.3, label="Current")
    for i, (s, e) in enumerate(events):
        lbl = f"Events ({len(events)})" if i == 0 else None
        ax.axvspan(t[s], t[e], color="#fee090", alpha=0.5, label=lbl)
    ax.set_xlabel("Time (s)")
    ax.set_ylabel("Current (nA)")
    ax.set_title("AutoSquareParser — full detection example")
    ax.legend(fontsize=8)
    _savefig(fig, "parsers", "autosquare", "full_example.png")


# ---------------------------------------------------------------------------
# Parser figures — Other parsers
# ---------------------------------------------------------------------------

def gen_other_parsers():
    print("Other parsers figures...")
    fs = 100000

    # FilterDerivativeSegmenter
    t, current = make_synthetic_multilevel(n=60000)
    filtered = _lowpass(current, 3000, fs)
    deriv = np.gradient(filtered)
    fig, axes = plt.subplots(2, 1, figsize=(10, 4), sharex=True)
    axes[0].plot(t, filtered, color="#2c7bb6", linewidth=0.4)
    axes[0].set_ylabel("Current (nA)")
    axes[0].set_title("FilterDerivativeSegmenter — filtered signal")
    axes[1].plot(t, deriv, color="#d7191c", linewidth=0.4)
    axes[1].axhline(0, color="#999", linewidth=0.5)
    axes[1].set_ylabel("Derivative")
    axes[1].set_xlabel("Time (s)")
    axes[1].set_title("Signal derivative — threshold crossings mark segment boundaries")
    fig.tight_layout()
    _savefig(fig, "parsers", "other", "filter_derivative.png")

    # NoiseFilterParser
    n = 80000
    t = np.arange(n) / fs
    current = RNG.normal(1.5, 0.03, n)
    # Add noisy regions
    current[15000:25000] += RNG.normal(0, 0.15, 10000)
    current[45000:55000] += RNG.normal(0, 0.2, 10000)
    fig, ax = plt.subplots(figsize=(10, 3))
    ax.plot(t, current, color="#2c7bb6", linewidth=0.3)
    ax.axvspan(t[15000], t[25000], color="#d7191c", alpha=0.15, label="Noisy region")
    ax.axvspan(t[45000], t[55000], color="#d7191c", alpha=0.15)
    ax.set_xlabel("Time (s)")
    ax.set_ylabel("Current (nA)")
    ax.set_title("NoiseFilterParser — detecting noisy vs clean regions")
    ax.legend(fontsize=8)
    _savefig(fig, "parsers", "other", "noise_filter.png")

    # snakebase_parser
    t, current, _, _, _ = make_synthetic_spikes(n=60000, n_spikes=8, spike_depth=0.8)
    fig, ax = plt.subplots(figsize=(10, 3))
    ax.plot(t, current, color="#2c7bb6", linewidth=0.3)
    ax.set_xlabel("Time (s)")
    ax.set_ylabel("Current (nA)")
    ax.set_title("snakebase_parser — peak-to-peak amplitude segmentation")
    _savefig(fig, "parsers", "other", "snakebase.png")

    # ExclusionParser
    t, current, voltage, vsteps = make_synthetic_trace(n=200000, n_vsteps=4)
    fig, ax = plt.subplots(figsize=(10, 3))
    ax.plot(t, current, color="#2c7bb6", linewidth=0.2)
    # Show excluded regions
    ax.axvspan(t[20000], t[40000], color="#d7191c", alpha=0.15, label="Excluded region")
    ax.axvspan(t[120000], t[140000], color="#d7191c", alpha=0.15)
    ax.set_xlabel("Time (s)")
    ax.set_ylabel("Current (nA)")
    ax.set_title("ExclusionParser — excluding time regions from analysis")
    ax.legend(fontsize=8)
    _savefig(fig, "parsers", "other", "exclusion.png")

    # IVCurveParser/Analyzer
    voltages_mv = np.array([-200, -150, -100, -50, 0, 50, 100, 150, 200])
    conductance = 1.8  # nS
    currents_mean = voltages_mv * conductance / 1000 + RNG.normal(0, 0.01, len(voltages_mv))
    currents_std = np.abs(RNG.normal(0.02, 0.005, len(voltages_mv)))
    fig, ax = plt.subplots(figsize=(6, 4))
    ax.errorbar(voltages_mv, currents_mean, yerr=currents_std, fmt="o-",
                color="#2c7bb6", capsize=4, markersize=6)
    ax.axhline(0, color="#999", linewidth=0.5)
    ax.axvline(0, color="#999", linewidth=0.5)
    ax.set_xlabel("Voltage (mV)")
    ax.set_ylabel("Current (nA)")
    ax.set_title("IV Curve — current vs voltage")
    ax.grid(True, alpha=0.3)
    _savefig(fig, "parsers", "other", "iv_curve.png")

    # lambda_event_parser
    t, current, _, _, _ = make_synthetic_spikes(n=50000, n_spikes=6, spike_depth=0.6)
    threshold = np.mean(current) * 0.9
    fig, ax = plt.subplots(figsize=(10, 3))
    ax.plot(t, current, color="#2c7bb6", linewidth=0.3)
    ax.axhline(threshold, color="#d73027", linewidth=1, linestyle="--", label=f"Threshold ({threshold:.2f} nA)")
    ax.set_xlabel("Time (s)")
    ax.set_ylabel("Current (nA)")
    ax.set_title("lambda_event_parser — threshold-based event detection")
    ax.legend(fontsize=8)
    _savefig(fig, "parsers", "other", "lambda_parser.png")


# ---------------------------------------------------------------------------
# Signal Analysis figures
# ---------------------------------------------------------------------------

def gen_signal_analysis():
    print("Signal Analysis figures...")

    # feature_scatter.png — dwell time vs blockade depth
    n_events = 80
    dwell_times = RNG.exponential(0.005, n_events) + 0.001
    blockade_depths = RNG.normal(0.5, 0.15, n_events)
    blockade_depths = np.clip(blockade_depths, 0.1, 1.0)

    fig, ax = plt.subplots(figsize=(6, 5))
    scatter = ax.scatter(dwell_times * 1000, blockade_depths, c=blockade_depths,
                          cmap="viridis", s=30, alpha=0.7, edgecolors="#333", linewidths=0.5)
    ax.set_xlabel("Dwell time (ms)")
    ax.set_ylabel("Blockade depth (nA)")
    ax.set_title("Event scatter — dwell time vs blockade depth")
    plt.colorbar(scatter, ax=ax, label="Blockade depth (nA)")
    ax.set_xscale("log")
    _savefig(fig, "analysis", "feature_scatter.png")

    # iv_curve.png
    voltages_mv = np.array([-200, -150, -100, -50, 50, 100, 150, 200])
    conductance = 2.0
    currents_mean = voltages_mv * conductance / 1000 + RNG.normal(0, 0.008, len(voltages_mv))
    currents_std = np.abs(RNG.normal(0.015, 0.005, len(voltages_mv)))

    fig, ax = plt.subplots(figsize=(6, 4))
    ax.errorbar(voltages_mv, currents_mean, yerr=currents_std, fmt="o-",
                color="#2c7bb6", capsize=4, markersize=6, label="Measured")
    # Fit line
    coeffs = np.polyfit(voltages_mv, currents_mean, 1)
    fit_v = np.linspace(-220, 220, 100)
    ax.plot(fit_v, np.polyval(coeffs, fit_v), "--", color="#d73027", linewidth=1,
            label=f"Fit: G = {coeffs[0]*1000:.2f} nS")
    ax.axhline(0, color="#999", linewidth=0.5)
    ax.axvline(0, color="#999", linewidth=0.5)
    ax.set_xlabel("Voltage (mV)")
    ax.set_ylabel("Current (nA)")
    ax.set_title("IV Curve Analysis")
    ax.legend(fontsize=8)
    ax.grid(True, alpha=0.3)
    _savefig(fig, "analysis", "iv_curve.png")


# ---------------------------------------------------------------------------
# Visualization figures
# ---------------------------------------------------------------------------

def gen_visualization():
    print("Visualization figures...")
    t, current, voltage, vsteps = make_synthetic_trace(n=300000, n_vsteps=4)
    fs = 100000
    filtered = _lowpass(current, 5000, fs)

    # qp_trace_basic.png
    fig, ax = plt.subplots(figsize=(10, 3))
    colors = ["#2c7bb6", "#abd9e9", "#fdae61", "#d7191c"]
    for i, (s, e) in enumerate(vsteps):
        ax.plot(t[s:e:50], filtered[s:e:50], color=colors[i % len(colors)], linewidth=0.5)
    ax.set_xlabel("Time (s)")
    ax.set_ylabel("Current (nA)")
    ax.set_title("qp_trace() — basic usage (downsampled)")
    _savefig(fig, "visualization", "qp_trace_basic.png")

    # qp_voltage_same.png — current and voltage on same axes
    fig, ax = plt.subplots(figsize=(10, 3))
    ax.plot(t[::50], filtered[::50], color="#2c7bb6", linewidth=0.5, label="Current")
    ax2 = ax.twinx()
    ax2.plot(t[::50], voltage[::50] * 1000, color="#d7191c", linewidth=0.8, label="Voltage")
    ax.set_xlabel("Time (s)")
    ax.set_ylabel("Current (nA)")
    ax2.set_ylabel("Voltage (mV)")
    ax.set_title('qp_trace(plot_voltage="same")')
    lines1, labels1 = ax.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    ax.legend(lines1 + lines2, labels1 + labels2, fontsize=8, loc="upper right")
    _savefig(fig, "visualization", "qp_voltage_same.png")

    # qp_voltage_split.png — current and voltage in separate subplots
    fig, axes = plt.subplots(2, 1, figsize=(10, 4), sharex=True,
                              gridspec_kw={"height_ratios": [3, 1]})
    axes[0].plot(t[::50], filtered[::50], color="#2c7bb6", linewidth=0.5)
    axes[0].set_ylabel("Current (nA)")
    axes[0].set_title('qp_trace(plot_voltage="split")')
    axes[1].plot(t[::50], voltage[::50] * 1000, color="#d7191c", linewidth=0.8)
    axes[1].set_ylabel("Voltage (mV)")
    axes[1].set_xlabel("Time (s)")
    fig.tight_layout()
    _savefig(fig, "visualization", "qp_voltage_split.png")


# ---------------------------------------------------------------------------
# Tutorial figures
# ---------------------------------------------------------------------------

def gen_tutorial():
    print("Tutorial figures...")
    n = 400000
    fs = 100000
    t, current, voltage, vsteps = make_synthetic_trace(n=n, n_vsteps=5)

    # step1_raw.png
    fig, axes = plt.subplots(2, 1, figsize=(10, 4), sharex=True,
                              gridspec_kw={"height_ratios": [3, 1]})
    axes[0].plot(t, current, color="#2c7bb6", linewidth=0.2)
    axes[0].set_ylabel("Current (nA)")
    axes[0].set_title("Step 1 — Raw trace loaded from file")
    axes[1].plot(t, voltage * 1000, color="#d7191c", linewidth=0.8)
    axes[1].set_ylabel("Voltage (mV)")
    axes[1].set_xlabel("Time (s)")
    fig.tight_layout()
    _savefig(fig, "tutorial", "step1_raw.png")

    # step2_filtered.png
    filtered = _lowpass(current, 5000, fs)
    fig, axes = plt.subplots(2, 1, figsize=(10, 4), sharex=True)
    axes[0].plot(t[:80000], current[:80000], color="#999999", linewidth=0.2, label="Raw")
    axes[0].set_ylabel("Current (nA)")
    axes[0].set_title("Step 2 — Before and after filtering (first voltage step)")
    axes[0].legend(fontsize=8)
    axes[1].plot(t[:80000], filtered[:80000], color="#2c7bb6", linewidth=0.3, label="Filtered (5 kHz)")
    axes[1].set_ylabel("Current (nA)")
    axes[1].set_xlabel("Time (s)")
    axes[1].legend(fontsize=8)
    fig.tight_layout()
    _savefig(fig, "tutorial", "step2_filtered.png")

    # step3_vsteps.png
    fig, ax = plt.subplots(figsize=(10, 3))
    colors = ["#2c7bb6", "#abd9e9", "#fdae61", "#d7191c", "#91bfdb"]
    for i, (s, e) in enumerate(vsteps):
        ax.plot(t[s:e], filtered[s:e], color=colors[i % len(colors)],
                linewidth=0.3, label=f"vstep {i}")
    ax.set_xlabel("Time (s)")
    ax.set_ylabel("Current (nA)")
    ax.set_title("Step 3 — Voltage steps identified")
    ax.legend(fontsize=7, ncol=5, loc="upper right")
    _savefig(fig, "tutorial", "step3_vsteps.png")

    # step4_events.png — show events detected in one voltage step
    vs, ve = vsteps[2]
    seg = filtered[vs:ve]
    seg_t = t[vs:ve]
    inverted = -seg
    peaks, _ = find_peaks(inverted, prominence=0.15, distance=50, width=(5, 500))
    fig, ax = plt.subplots(figsize=(10, 3))
    ax.plot(seg_t, seg, color="#2c7bb6", linewidth=0.4)
    ax.plot(seg_t[peaks], seg[peaks], "rv", markersize=6)
    ax.set_xlabel("Time (s)")
    ax.set_ylabel("Current (nA)")
    ax.set_title(f"Step 4 — Events detected in vstep 2 ({len(peaks)} events)")
    _savefig(fig, "tutorial", "step4_events.png")

    # step5_features.png — histogram of blockade depths
    depths = np.abs(seg[peaks] - np.median(seg))
    fig, axes = plt.subplots(1, 2, figsize=(10, 3.5))
    axes[0].hist(depths, bins=15, color="#2c7bb6", edgecolor="white", alpha=0.8)
    axes[0].set_xlabel("Blockade depth (nA)")
    axes[0].set_ylabel("Count")
    axes[0].set_title("Step 5 — Blockade depth distribution")

    durations = RNG.exponential(0.003, len(peaks)) + 0.0005
    axes[1].hist(durations * 1000, bins=15, color="#fdae61", edgecolor="white", alpha=0.8)
    axes[1].set_xlabel("Dwell time (ms)")
    axes[1].set_ylabel("Count")
    axes[1].set_title("Step 5 — Dwell time distribution")
    fig.tight_layout()
    _savefig(fig, "tutorial", "step5_features.png")

    # step6_scatter.png
    fig, ax = plt.subplots(figsize=(6, 4))
    ax.scatter(durations * 1000, depths, c="#2c7bb6", s=30, alpha=0.7,
               edgecolors="#333", linewidths=0.5)
    ax.set_xlabel("Dwell time (ms)")
    ax.set_ylabel("Blockade depth (nA)")
    ax.set_title("Step 6 — Scatter plot of extracted features")
    _savefig(fig, "tutorial", "step6_scatter.png")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print(f"Generating figures to {OUTDIR}/\n")
    gen_getting_started()
    gen_data_input()
    gen_concepts()
    gen_preprocessing()
    gen_spike_parser()
    gen_speedy_statsplit()
    gen_autosquare_parser()
    gen_other_parsers()
    gen_signal_analysis()
    gen_visualization()
    gen_tutorial()
    print("\nDone!")
