'''
Author: Midrar Adham
Created: Thu Jul 23 2026
'''
"""
05_plot_cooling_capacity_bins.py

Compare active cooling HVAC devices by cooling capacity bins and electrical kW.

This script reads:
    outputs/hvac_analysis/hvac_state_diagnostics.csv

It focuses only on active cooling rows from the August simulation.

Output folder:
    outputs/hvac_analysis/figures/cooling_capacity_bins

Important:
    This script does not modify any simulation files.
"""

from pathlib import Path

import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import numpy as np
import pandas as pd
import seaborn as sns
from matplotlib.colors import LinearSegmentedColormap
from scipy import stats


# ---------------------------------------------------------------------------
# User settings
# ---------------------------------------------------------------------------
# Rule: keep variable names lowercase.

analysis_dir = Path("./outputs")
figures_dir = analysis_dir / "figures" / "cooling_capacity_bins"

diagnostics_file = analysis_dir / "hvac_state_diagnostics.csv"

upgrades = ["up00", "up01", "up02"]
upgrade_labels = {"up00": "Baseline (up00)", "up01": "Upgrade 1 (up01)", "up02": "Upgrade 2 (up02)"}

service = "cooling"
active_operation_flag = "include_in_active_operation_plots"

capacity_bins = [0, 1, 2, 3, 4, 5, float("inf")]
capacity_labels = ["0–1", "1–2", "2–3", "3–4", "4–5", "5+"]

peak_kw_bins = [0, 1, 2, 3, 4, 5, float("inf")]
peak_kw_labels = ["0–1", "1–2", "2–3", "3–4", "4–5", "5+"]


# ---------------------------------------------------------------------------
# Visual style
# ---------------------------------------------------------------------------

surface_color = "#f8f8f6"
ink_primary = "#1a1a18"
ink_secondary = "#4a4946"
ink_muted = "#8a8884"
grid_color = "#e5e4dd"
axis_color = "#c8c7be"
annotation_color = "#6b6965"

upgrade_colors = {
    "up00": "#2a78d6",
    "up01": "#eb6834",
    "up02": "#1baf7a",
}
upgrade_palette = [upgrade_colors[u] for u in upgrades]

sequential_blue = LinearSegmentedColormap.from_list(
    "sequential_blue",
    [surface_color, "#cde2fb", "#6da7ec", "#2a78d6", "#184f95"],
)

sns.set_theme(style="whitegrid", font="sans-serif")

plt.rcParams.update(
    {
        "figure.facecolor": surface_color,
        "axes.facecolor": surface_color,
        "savefig.facecolor": surface_color,
        "font.family": "sans-serif",
        "font.size": 11,
        "text.color": ink_primary,
        "axes.edgecolor": axis_color,
        "axes.labelcolor": ink_secondary,
        "axes.titlecolor": ink_primary,
        "axes.titlesize": 13,
        "axes.titleweight": "semibold",
        "axes.labelsize": 11,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "axes.grid": True,
        "axes.grid.axis": "y",
        "axes.axisbelow": True,
        "grid.color": grid_color,
        "grid.linewidth": 0.7,
        "xtick.color": ink_muted,
        "ytick.color": ink_muted,
        "xtick.labelsize": 10,
        "ytick.labelsize": 10,
        "legend.frameon": True,
        "legend.framealpha": 0.92,
        "legend.edgecolor": grid_color,
        "legend.fontsize": 10,
        "legend.title_fontsize": 10,
    }
)


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

def save_figure(filename, tight_layout=True, layout_rect=None):
    figures_dir.mkdir(parents=True, exist_ok=True)
    output_path = figures_dir / filename
    if tight_layout:
        plt.tight_layout(rect=layout_rect)
    plt.savefig(output_path, dpi=300, bbox_inches="tight")
    plt.close()
    print(f"Saved: {output_path}")


def load_active_cooling_rows():
    if not diagnostics_file.is_file():
        raise FileNotFoundError(
            f"diagnostics_file does not exist: {diagnostics_file}\n"
            "Run 03_build_hvac_state_diagnostics.py first."
        )

    diagnostics = pd.read_csv(diagnostics_file)

    cooling = diagnostics[
        (diagnostics["service"] == service)
        & (diagnostics["upgrade"].isin(upgrades))
        & (diagnostics[active_operation_flag] == True)
    ].copy()

    for col in ["cooling_capacity_tons", "peak_kw", "total_energy_kwh", "duty_cycle", "n_switching_events"]:
        cooling[col] = pd.to_numeric(cooling[col], errors="coerce")

    cooling = cooling.dropna(subset=["cooling_capacity_tons", "peak_kw"]).copy()

    cooling["capacity_bin"] = pd.cut(
        cooling["cooling_capacity_tons"],
        bins=capacity_bins,
        labels=capacity_labels,
        right=False,
    )

    cooling["peak_kw_bin"] = pd.cut(
        cooling["peak_kw"],
        bins=peak_kw_bins,
        labels=peak_kw_labels,
        right=False,
    )

    # Friendly upgrade labels for display
    cooling["upgrade_label"] = cooling["upgrade"].map(upgrade_labels)

    return cooling


def grouped_median_table(data, value_col):
    table = (
        data
        .groupby(["capacity_bin", "upgrade"], observed=False)[value_col]
        .median()
        .unstack(fill_value=float("nan"))
        .reindex(capacity_labels)
    )
    return table.reindex(columns=upgrades)


def grouped_count_table(data, row_col):
    labels = capacity_labels if row_col == "capacity_bin" else peak_kw_labels
    table = (
        data
        .groupby([row_col, "upgrade"], observed=False)
        .size()
        .unstack(fill_value=0)
        .reindex(labels)
    )
    return table.reindex(columns=upgrades, fill_value=0)


def annotate_bar_values(ax, fmt="{:.0f}", threshold=0, tops=None):
    """
    Add value labels above each bar. Bars at or below threshold are skipped.
    """
    y_span = ax.get_ylim()[1] - ax.get_ylim()[0]
    bar_container_index = 0
    for container in ax.containers:
        # Errorbar containers do not contain rectangular bar patches.
        if not hasattr(container, "patches"):
            continue
        for patch_index, patch in enumerate(container.patches):
            if patch is None or not hasattr(patch, "get_height"):
                continue
            h = patch.get_height()
            if h > threshold:
                label_top = h
                if tops is not None:
                    candidate = tops[bar_container_index][patch_index]
                    if np.isfinite(candidate):
                        label_top = max(h, candidate)
                ax.text(
                    patch.get_x() + patch.get_width() / 2,
                    label_top + y_span * 0.018,
                    fmt.format(h),
                    ha="center",
                    va="bottom",
                    fontsize=8.5,
                    color=ink_secondary,
                )
        bar_container_index += 1


def labels_with_totals(table):
    """
    Annotate the total count across all upgrades per bin as a subtle footnote
    along the x-axis.
    """
    return [
        f"{label}\n$n={int(total):,}$"
        for label, total in table.sum(axis=1).items()
    ]


def style_grouped_bar(ax):
    ax.axhline(0, color=axis_color, linewidth=1)
    for container in ax.containers:
        for patch in container:
            if patch is not None and hasattr(patch, "set_edgecolor"):
                patch.set_edgecolor(surface_color)
                patch.set_linewidth(1.2)
    ax.yaxis.set_major_locator(mticker.MaxNLocator(nbins=6, integer=True))
    ax.spines["left"].set_linewidth(0.8)
    ax.spines["bottom"].set_linewidth(0.8)


# ---------------------------------------------------------------------------
# Plot functions
# ---------------------------------------------------------------------------

def plot_grouped_bar(table, title, xlabel, ylabel, filename, annotate=True, fmt="{:.0f}"):
    """
    Grouped bar chart with per-bar value labels and per-bin totals.
    """
    fig, ax = plt.subplots(figsize=(11, 6.2))

    x = np.arange(len(table))
    n_groups = len(table.columns)
    bar_width = 0.65 / n_groups
    offsets = np.linspace(-(n_groups - 1) / 2, (n_groups - 1) / 2, n_groups) * bar_width

    for i, col in enumerate(table.columns):
        bars = ax.bar(
            x + offsets[i],
            table[col],
            width=bar_width * 0.92,
            color=upgrade_colors[col],
            label=upgrade_labels[col],
            edgecolor=surface_color,
            linewidth=1.2,
        )

    style_grouped_bar(ax)

    # Expand y-limit slightly to make room for labels
    ax.set_ylim(bottom=0, top=ax.get_ylim()[1] * 1.20)
    if annotate:
        annotate_bar_values(ax, fmt=fmt)

    ax.set_title(title)
    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    ax.set_xticks(x)
    ax.set_xticklabels(labels_with_totals(table), rotation=0, linespacing=1.5)
    ax.legend(title="Upgrade", loc="upper left", bbox_to_anchor=(1.01, 1), borderaxespad=0)

    save_figure(filename)


def plot_median_metric_by_capacity(data, value_col, ylabel, title, filename, fmt="{:.2f}"):
    """
    Grouped bar chart of median metric by capacity bin, with:
    - per-bar value labels
    - error whiskers (IQR)
    - count annotations
    """
    table = grouped_median_table(data, value_col)

    # Compute IQR for whiskers
    q1 = (
        data.groupby(["capacity_bin", "upgrade"], observed=False)[value_col]
        .quantile(0.25).unstack().reindex(capacity_labels).reindex(columns=upgrades)
    )
    q3 = (
        data.groupby(["capacity_bin", "upgrade"], observed=False)[value_col]
        .quantile(0.75).unstack().reindex(capacity_labels).reindex(columns=upgrades)
    )

    fig, ax = plt.subplots(figsize=(11, 6.4))

    x = np.arange(len(table))
    n_groups = len(table.columns)
    bar_width = 0.65 / n_groups
    offsets = np.linspace(-(n_groups - 1) / 2, (n_groups - 1) / 2, n_groups) * bar_width

    annotation_tops = []
    for i, col in enumerate(table.columns):
        medians = table[col].values.astype(float)
        lower_err = np.where(
            np.isnan(medians), np.nan, medians - q1[col].values.astype(float)
        )
        upper_err = np.where(
            np.isnan(medians), np.nan, q3[col].values.astype(float) - medians
        )
        annotation_tops.append(q3[col].values.astype(float))

        ax.bar(
            x + offsets[i],
            medians,
            width=bar_width * 0.92,
            color=upgrade_colors[col],
            label=upgrade_labels[col],
            edgecolor=surface_color,
            linewidth=1.2,
        )
        ax.errorbar(
            x + offsets[i],
            medians,
            yerr=[np.nan_to_num(lower_err), np.nan_to_num(upper_err)],
            fmt="none",
            color=ink_secondary,
            linewidth=1.1,
            capsize=3.5,
            capthick=1.1,
            zorder=5,
        )

    style_grouped_bar(ax)
    finite_q3 = q3.to_numpy(dtype=float)
    top_value = np.nanmax(finite_q3) if np.isfinite(finite_q3).any() else 1
    ax.set_ylim(bottom=0, top=max(top_value * 1.20, 0.01))
    annotate_bar_values(ax, fmt=fmt, threshold=0, tops=annotation_tops)

    ax.set_title(title)
    ax.set_xlabel("Cooling capacity bin (tons)")
    ax.set_ylabel(ylabel)
    ax.set_xticks(x)
    count_table = grouped_count_table(data, "capacity_bin")
    ax.set_xticklabels(labels_with_totals(count_table), rotation=0, linespacing=1.5)
    ax.legend(title="Upgrade", loc="upper left", bbox_to_anchor=(1.01, 1), borderaxespad=0)

    # Footnote
    fig.text(
        0.01, 0.015,
        "Whiskers show interquartile range (Q1-Q3). Bar height = median.",
        fontsize=8.5,
        color=ink_muted,
    )

    save_figure(filename, layout_rect=(0, 0.055, 1, 1))


def plot_capacity_vs_peak_scatter_by_bin(data):
    """
    Scatter of capacity vs. peak kW with:
    - per-upgrade OLS trendlines
    - vertical bin boundaries
    - Pearson r annotation
    - rug plot on both axes
    """
    fig, ax = plt.subplots(figsize=(10.5, 6.2))
    correlation_lines = []

    for upgrade in upgrades:
        subset = data[data["upgrade"] == upgrade].dropna(subset=["cooling_capacity_tons", "peak_kw"])
        x_vals = subset["cooling_capacity_tons"].values
        y_vals = subset["peak_kw"].values

        ax.scatter(
            x_vals,
            y_vals,
            label=upgrade_labels[upgrade],
            color=upgrade_colors[upgrade],
            alpha=0.45,
            s=20,
            linewidths=0,
            zorder=3,
        )

        # OLS trendline
        if len(x_vals) > 2:
            slope, intercept, r_value, p_value, _ = stats.linregress(x_vals, y_vals)
            x_fit = np.linspace(x_vals.min(), x_vals.max(), 200)
            y_fit = slope * x_fit + intercept
            ax.plot(
                x_fit, y_fit,
                color=upgrade_colors[upgrade],
                linewidth=1.8,
                linestyle="--",
                alpha=0.85,
                zorder=4,
            )
            correlation_lines.append((upgrade, r_value))

    # Vertical capacity bin boundaries
    for boundary in capacity_bins[1:-1]:
        ax.axvline(
            boundary,
            color=axis_color,
            linestyle=":",
            linewidth=1,
            zorder=1,
        )
        ax.text(
            boundary + 0.04,
            0.98,
            f"{boundary}t",
            transform=ax.get_xaxis_transform(),
            fontsize=8,
            color=ink_muted,
            va="top",
        )

    ax.set_title("Cooling capacity vs. observed peak kW, with OLS trendlines")
    ax.set_xlabel("Cooling capacity (tons)")
    ax.set_ylabel("Observed peak cooling electric power (kW)")
    ax.legend(
        title="Upgrade", loc="upper left",
        bbox_to_anchor=(1.01, 1), borderaxespad=0,
    )
    if correlation_lines:
        correlation_text = "\n".join(
            f"{upgrade_labels[u]}: r={r:.2f}" for u, r in correlation_lines
        )
        ax.text(
            1.01, 0.02, correlation_text,
            transform=ax.transAxes, ha="left", va="bottom",
            fontsize=8.5, color=ink_secondary,
            bbox={"boxstyle": "round,pad=0.45", "facecolor": surface_color,
                  "edgecolor": grid_color, "alpha": 0.94},
        )

    # Sample size footnote
    n_total = len(data.dropna(subset=["cooling_capacity_tons", "peak_kw"]))
    fig.text(
        0.01, 0.015,
        f"n={n_total} active cooling cases. Dashed lines = OLS fit per upgrade. Dotted verticals = capacity bin boundaries.",
        fontsize=8.5,
        color=ink_muted,
    )

    save_figure("07_capacity_vs_peak_kw_with_capacity_bins.png", layout_rect=(0, 0.055, 1, 1))


def plot_capacity_peak_heatmap(data, upgrade):
    """
    Heatmap of capacity-bin × peak-kW-bin counts with:
    - seaborn heatmap
    - cell annotations (count + % of upgrade total)
    - marginal totals, each in its own panel so nothing overlaps the
      heatmap, the colorbar, or the tick labels
    """
    subset = data[data["upgrade"] == upgrade].copy()

    table = (
        subset
        .groupby(["capacity_bin", "peak_kw_bin"], observed=False)
        .size()
        .unstack(fill_value=0)
        .reindex(capacity_labels)
        .reindex(columns=peak_kw_labels)
    )

    grand_total = table.values.sum()
    pct_table = (table / grand_total * 100).round(1) if grand_total > 0 else table * 0

    # Build annotation strings: "N\n(X%)"
    annot = np.where(
        table.values > 0,
        np.vectorize(lambda n, p: f"{n}\n({p:.1f}%)")(table.values, pct_table.values),
        "",
    )

    n_rows, n_cols = table.shape

    fig = plt.figure(figsize=(12, 7.5))
    gs = fig.add_gridspec(
        2, 3,
        width_ratios=[n_cols, 1.3, 0.32],
        height_ratios=[n_rows, 1.05],
        left=0.09, right=0.90, top=0.90, bottom=0.15,
        wspace=0.06, hspace=0.14,
    )

    ax = fig.add_subplot(gs[0, 0])
    ax_row_totals = fig.add_subplot(gs[0, 1], sharey=ax)
    cax = fig.add_subplot(gs[0, 2])
    ax_col_totals = fig.add_subplot(gs[1, 0], sharex=ax)

    sns.heatmap(
        table,
        ax=ax,
        cmap=sequential_blue,
        annot=annot,
        fmt="",
        linewidths=2,
        linecolor=surface_color,
        cbar_ax=cax,
        cbar_kws={"label": "Count"},
        annot_kws={"fontsize": 9.5, "color": ink_primary},
    )
    ax.tick_params(axis="both", which="both", length=0)
    ax.set_xlabel("")
    ax.set_ylabel("Cooling capacity bin (tons)", labelpad=10)

    # Row totals panel (its own axes, so it never collides with the colorbar)
    row_totals = table.sum(axis=1)
    ax_row_totals.axis("off")
    ax_row_totals.set_xlim(0, 1)
    ax_row_totals.set_title("Row\ntotal", fontsize=9.5, color=ink_muted, pad=10)
    for i, total in enumerate(row_totals.values):
        ax_row_totals.text(
            0.12, i + 0.5, f"{int(total):,}",
            va="center", ha="left", fontsize=10, color=ink_secondary,
        )

    # Column totals panel (its own axes, below the heatmap).
    # Note: axis("off") would also hide the xlabel set below (it hides the
    # whole xaxis, not just ticks), so spines/ticks are hidden individually.
    col_totals = table.sum(axis=0)
    ax_col_totals.set_ylim(0, 1)
    ax_col_totals.set_yticks([])
    ax_col_totals.tick_params(axis="x", length=0, labelbottom=False)
    for spine in ax_col_totals.spines.values():
        spine.set_visible(False)
    for j, total in enumerate(col_totals.values):
        ax_col_totals.text(
            j + 0.5, 0.55, f"{int(total):,}",
            va="center", ha="center", fontsize=10, color=ink_secondary,
        )
    ax_col_totals.set_title("Column total", fontsize=9.5, color=ink_muted, loc="left", pad=6)
    ax_col_totals.set_xlabel(
        "Observed peak cooling electric power bin (kW)",
        labelpad=10,
        color=ink_secondary,
        fontsize=11,
    )

    fig.suptitle(
        f"Cooling capacity bin × peak kW bin  |  {upgrade_labels[upgrade]}",
        fontsize=14,
        fontweight="semibold",
        color=ink_primary,
        x=0.09,
        ha="left",
    )

    fig.text(
        0.09, 0.03,
        f"n={int(grand_total)} active cooling cases. Cell shows count and share of upgrade total.",
        fontsize=9,
        color=ink_muted,
    )

    save_figure(f"08_capacity_peak_kw_bin_heatmap_{upgrade}.png", tight_layout=False)


# ---------------------------------------------------------------------------
# Summary tables
# ---------------------------------------------------------------------------

def save_summary_tables(data):
    figures_dir.mkdir(parents=True, exist_ok=True)

    capacity_count_table = grouped_count_table(data, "capacity_bin")
    peak_kw_count_table = grouped_count_table(data, "peak_kw_bin")
    median_peak_kw_table = grouped_median_table(data, "peak_kw")
    median_energy_table = grouped_median_table(data, "total_energy_kwh")
    median_duty_table = grouped_median_table(data, "duty_cycle")
    median_switching_table = grouped_median_table(data, "n_switching_events")

    capacity_count_table.to_csv(figures_dir / "capacity_bin_counts_by_upgrade.csv")
    peak_kw_count_table.to_csv(figures_dir / "peak_kw_bin_counts_by_upgrade.csv")
    median_peak_kw_table.to_csv(figures_dir / "median_peak_kw_by_capacity_bin.csv")
    median_energy_table.to_csv(figures_dir / "median_energy_by_capacity_bin.csv")
    median_duty_table.to_csv(figures_dir / "median_duty_cycle_by_capacity_bin.csv")
    median_switching_table.to_csv(figures_dir / "median_switching_events_by_capacity_bin.csv")

    print("\nCapacity bin counts by upgrade:")
    print(capacity_count_table)
    print("\nPeak kW bin counts by upgrade:")
    print(peak_kw_count_table)
    print("\nMedian peak kW by capacity bin:")
    print(median_peak_kw_table)
    print("\nMedian monthly cooling energy by capacity bin:")
    print(median_energy_table)
    print("\nMedian cooling duty cycle by capacity bin:")
    print(median_duty_table)
    print("\nMedian switching events by capacity bin:")
    print(median_switching_table)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    """
    Create cooling capacity-bin and electrical-kW comparison figures.
    """
    data = load_active_cooling_rows()

    print("\nActive cooling rows with capacity and peak kW:")
    print(len(data))
    print("\nRows by upgrade:")
    print(data["upgrade"].value_counts().sort_index())

    save_summary_tables(data)

    capacity_count_table = grouped_count_table(data, "capacity_bin")
    peak_kw_count_table = grouped_count_table(data, "peak_kw_bin")

    plot_grouped_bar(
        table=capacity_count_table,
        title="Active cooling case counts by capacity bin",
        xlabel="Cooling capacity bin (tons)",
        ylabel="Number of active cooling cases",
        filename="01_capacity_bin_counts_by_upgrade.png",
    )

    plot_grouped_bar(
        table=peak_kw_count_table,
        title="Active cooling case counts by observed peak kW bin",
        xlabel="Observed peak cooling electric power bin (kW)",
        ylabel="Number of active cooling cases",
        filename="02_peak_kw_bin_counts_by_upgrade.png",
    )

    plot_median_metric_by_capacity(
        data=data,
        value_col="peak_kw",
        ylabel="Median observed peak cooling power (kW)",
        title="Median peak kW by cooling capacity bin",
        filename="03_median_peak_kw_by_capacity_bin.png",
        fmt="{:.2f}",
    )

    plot_median_metric_by_capacity(
        data=data,
        value_col="total_energy_kwh",
        ylabel="Median monthly cooling energy (kWh)",
        title="Median monthly cooling energy by capacity bin",
        filename="04_median_energy_by_capacity_bin.png",
        fmt="{:.0f}",
    )

    plot_median_metric_by_capacity(
        data=data,
        value_col="duty_cycle",
        ylabel="Median cooling duty cycle",
        title="Median cooling duty cycle by capacity bin",
        filename="05_median_duty_cycle_by_capacity_bin.png",
        fmt="{:.2f}",
    )

    plot_median_metric_by_capacity(
        data=data,
        value_col="n_switching_events",
        ylabel="Median number of switching events",
        title="Median switching events by cooling capacity bin",
        filename="06_median_switching_events_by_capacity_bin.png",
        fmt="{:.0f}",
    )

    plot_capacity_vs_peak_scatter_by_bin(data)

    for upgrade in upgrades:
        plot_capacity_peak_heatmap(data, upgrade)

    print("\nDone. Figures saved to:")
    print(figures_dir)


if __name__ == "__main__":
    main()
