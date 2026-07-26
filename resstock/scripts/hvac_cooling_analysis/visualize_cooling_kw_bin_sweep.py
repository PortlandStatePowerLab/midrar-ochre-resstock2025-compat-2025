'''
Author: Midrar Adham
Created: Sun Jul 26 2026
'''
"""
09_visualize_cooling_kw_bin_sweep.py

Create intuitive figures for understanding the cooling kW-bin sweep.

This script does not rerun the sweep. It reads the outputs from:

    08_sweep_cooling_kw_bins.py

and creates more interpretable figures.

Main idea:
    The sweep is trying to find kW bins that keep electrically similar devices
    together. A good binning scheme should reduce prediction error when a small
    transformer group has only 2-13 HVAC devices.

Inputs:
    ./outputs/hvac_state_diagnostics.csv
    ./outputs/kw_bin_sweep/cooling_kw_bin_sweep_summary.csv
    ./outputs/kw_bin_sweep/cooling_kw_bin_sweep_groups.csv
    ./outputs/kw_bin_sweep/cooling_kw_bin_sweep_bootstrap.csv
    ./outputs/kw_bin_sweep/cooling_kw_bin_sweep_bootstrap_by_sample_size.csv

Outputs:
    ./outputs/kw_bin_sweep/figures_explained/*.png
"""

from pathlib import Path
import math
import re

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


# ---------------------------------------------------------------------------
# User settings
# ---------------------------------------------------------------------------
# Rule: keep variable names lowercase.

analysis_dir = Path("./outputs")
sweep_dir = analysis_dir / "kw_bin_sweep"
figures_dir = sweep_dir / "figures_explained"

diagnostics_file = analysis_dir / "hvac_state_diagnostics.csv"
summary_file = sweep_dir / "cooling_kw_bin_sweep_summary.csv"
group_file = sweep_dir / "cooling_kw_bin_sweep_groups.csv"
bootstrap_file = sweep_dir / "cooling_kw_bin_sweep_bootstrap.csv"
bootstrap_by_size_file = sweep_dir / "cooling_kw_bin_sweep_bootstrap_by_sample_size.csv"
excluded_large_devices_file = sweep_dir / "cooling_kw_bin_sweep_excluded_large_devices.csv"

upgrades = ["up00", "up01", "up02"]
upgrade_labels = {
    "up00": "Baseline (up00)",
    "up01": "Upgrade 1 (up01)",
    "up02": "Upgrade 2 (up02)",
}

service = "cooling"
active_operation_flag = "include_in_active_operation_plots"

maximum_cooling_capacity_tons = 5.0

# Use a small number of schemes so the plots are understandable.
selected_schemes = [
    "pooled_quantile_8_bins",
    "fixed_0p5_to_3_then_4plus",
    "fixed_1kw_bins",
    "fixed_small_medium_large",
]

best_scheme = "pooled_quantile_8_bins"


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

def save_figure(filename):
    """
    Save the current figure.
    """
    figures_dir.mkdir(parents=True, exist_ok=True)
    output_path = figures_dir / filename
    plt.tight_layout()
    plt.savefig(output_path, dpi=300, bbox_inches="tight")
    plt.close()

    print(f"Saved: {output_path}")


def normalize_bool(series):
    """
    Convert boolean-like values to booleans.
    """
    if series.dtype == bool:
        return series

    return (
        series
        .astype(str)
        .str.strip()
        .str.lower()
        .isin(["true", "1", "yes", "y"])
    )


def read_required_csv(path):
    """
    Read a CSV and give a helpful error if it is missing.
    """
    if not path.is_file():
        raise FileNotFoundError(
            f"Missing required file: {path}\n"
            "Run 08_sweep_cooling_kw_bins.py first."
        )

    return pd.read_csv(path)


def load_primary_devices():
    """
    Load the same primary active cooling population used in the sweep.
    """
    if not diagnostics_file.is_file():
        raise FileNotFoundError(f"Missing diagnostics file: {diagnostics_file}")

    data = pd.read_csv(diagnostics_file)

    data[active_operation_flag] = normalize_bool(data[active_operation_flag])

    devices = data[
        (data["service"] == service)
        & (data["upgrade"].isin(upgrades))
        & (data[active_operation_flag] == True)
    ].copy()

    for col in ["peak_kw", "cooling_capacity_tons"]:
        devices[col] = pd.to_numeric(devices[col], errors="coerce")

    devices = devices.dropna(subset=["peak_kw"]).copy()

    # Match the main sweep QC filter.
    devices = devices[
        (devices["cooling_capacity_tons"].isna())
        | (devices["cooling_capacity_tons"] <= maximum_cooling_capacity_tons)
    ].copy()

    return devices


def parse_edges_from_label_string(label_string):
    """
    Parse bin edges from the summary labels column.

    Example labels string:
        "0-0.6127 | 0.6127-0.8168 | 2.4191+"

    Returns:
        [0.0, 0.6127, 0.8168, ..., inf]
    """
    pieces = str(label_string).split("|")
    edges = []

    for piece in pieces:
        label = piece.strip()

        if label.endswith("+"):
            left = float(label.replace("+", ""))
            if len(edges) == 0:
                edges.append(left)
            elif not np.isclose(edges[-1], left):
                edges.append(left)
            edges.append(float("inf"))
            continue

        match = re.match(r"^\s*([0-9.]+)\s*-\s*([0-9.]+)\s*$", label)
        if match is None:
            continue

        left = float(match.group(1))
        right = float(match.group(2))

        if len(edges) == 0:
            edges.append(left)
        elif not np.isclose(edges[-1], left):
            edges.append(left)

        edges.append(right)

    return edges


def get_scheme_edges(summary, scheme_name):
    """
    Get bin edges for one scheme from the sweep summary file.
    """
    row = summary[summary["scheme_name"] == scheme_name]

    if len(row) == 0:
        raise ValueError(f"Scheme not found in summary file: {scheme_name}")

    labels = row.iloc[0]["labels"]
    edges = parse_edges_from_label_string(labels)

    return edges


def format_edge(edge):
    """
    Format a bin edge for plotting.
    """
    if math.isinf(edge):
        return "+"

    if edge < 10:
        return f"{edge:.2f}".rstrip("0").rstrip(".")

    return f"{edge:g}"


def plot_histogram_with_bin_boundaries(devices, summary, scheme_name):
    """
    Plot observed peak kW distribution with vertical bin boundaries.
    """
    edges = get_scheme_edges(summary, scheme_name)

    plt.figure(figsize=(10, 5.8))

    plt.hist(
        devices["peak_kw"].dropna(),
        bins=50,
        alpha=0.8,
        edgecolor="black",
        linewidth=0.3,
    )

    for edge in edges[1:-1]:
        plt.axvline(edge, linestyle="--", linewidth=1.3, alpha=0.75)

    plt.title(f"Observed cooling peak kW distribution with bin boundaries\n{scheme_name}")
    plt.xlabel("Observed monthly peak cooling electric power (kW)")
    plt.ylabel("Number of active cooling devices")
    plt.grid(True, axis="y", alpha=0.35)

    text = (
        "Dashed lines are bin boundaries. "
        "Quantile bins are closer together where many devices are concentrated."
    )
    plt.figtext(0.01, 0.01, text, ha="left", fontsize=9)

    save_figure(f"01_peak_kw_histogram_with_bins_{scheme_name}.png")


def plot_bin_ruler(summary):
    """
    Plot selected bin schemes as rulers on the same kW axis.
    """
    selected = [scheme for scheme in selected_schemes if scheme in set(summary["scheme_name"])]

    plt.figure(figsize=(12, 0.9 * len(selected) + 2.0))
    ax = plt.gca()

    y_positions = np.arange(len(selected))[::-1]

    max_edge = 0

    parsed_edges = {}
    for scheme in selected:
        edges = get_scheme_edges(summary, scheme)
        parsed_edges[scheme] = edges
        finite_edges = [edge for edge in edges if not math.isinf(edge)]
        if len(finite_edges) > 0:
            max_edge = max(max_edge, max(finite_edges))

    max_x = max(max_edge, 5.0)

    for y, scheme in zip(y_positions, selected):
        edges = parsed_edges[scheme]

        finite_edges = [edge for edge in edges if not math.isinf(edge)]
        plot_edges = finite_edges + [max_x]

        for left, right in zip(plot_edges[:-1], plot_edges[1:]):
            ax.plot([left, right], [y, y], linewidth=8, solid_capstyle="butt")

        for edge in finite_edges:
            ax.plot([edge, edge], [y - 0.18, y + 0.18], color="black", linewidth=1)

        for edge in finite_edges:
            ax.text(edge, y + 0.27, format_edge(edge), ha="center", va="bottom", fontsize=8)

        if math.isinf(edges[-1]):
            ax.text(max_x, y + 0.27, "+", ha="center", va="bottom", fontsize=8)

    ax.set_yticks(y_positions)
    ax.set_yticklabels(selected)
    ax.set_xlim(0, max_x * 1.05)
    ax.set_xlabel("Observed monthly peak cooling electric power (kW)")
    ax.set_title("Bin schemes shown as kW rulers")
    ax.grid(True, axis="x", alpha=0.35)

    text = (
        "A quantile ruler uses uneven kW widths because it tries to place a similar "
        "number of devices in each bin. Fixed rulers use manually chosen kW intervals."
    )
    plt.figtext(0.01, 0.01, text, ha="left", fontsize=9)

    save_figure("02_bin_rulers_selected_schemes.png")


def plot_error_vs_group_size(bootstrap_by_size):
    """
    Plot median prediction error against transformer group size.
    """
    data = bootstrap_by_size[
        bootstrap_by_size["scheme_name"].isin(selected_schemes)
    ].copy()

    plt.figure(figsize=(9.5, 5.8))

    for scheme in selected_schemes:
        subset = data[data["scheme_name"] == scheme].sort_values("sample_size")
        if len(subset) == 0:
            continue

        plt.plot(
            subset["sample_size"],
            subset["median_absolute_percentage_error"],
            marker="o",
            linewidth=2,
            label=scheme,
        )

    plt.title("Prediction error vs transformer group size")
    plt.xlabel("Number of HVAC devices in transformer group")
    plt.ylabel("Median absolute percentage error (%)")
    plt.xticks(sorted(data["sample_size"].dropna().unique()))
    plt.grid(True, axis="y", alpha=0.35)
    plt.legend(title="Bin scheme")

    text = (
        "This is the most transformer-relevant plot. "
        "It shows whether a binning scheme still works when only a few devices are present."
    )
    plt.figtext(0.01, 0.01, text, ha="left", fontsize=9)

    save_figure("03_prediction_error_vs_group_size.png")


def plot_error_band_vs_group_size(bootstrap_by_size):
    """
    Plot median and p90 error for the best scheme.
    """
    data = bootstrap_by_size[
        bootstrap_by_size["scheme_name"] == best_scheme
    ].sort_values("sample_size").copy()

    plt.figure(figsize=(8.8, 5.6))

    plt.plot(
        data["sample_size"],
        data["median_absolute_percentage_error"],
        marker="o",
        linewidth=2,
        label="Median error",
    )

    plt.plot(
        data["sample_size"],
        data["p90_absolute_percentage_error"],
        marker="o",
        linewidth=2,
        label="90th percentile error",
    )

    plt.fill_between(
        data["sample_size"],
        data["median_absolute_percentage_error"],
        data["p90_absolute_percentage_error"],
        alpha=0.2,
    )

    plt.title(f"Best scheme error range by transformer group size\n{best_scheme}")
    plt.xlabel("Number of HVAC devices in transformer group")
    plt.ylabel("Absolute percentage error (%)")
    plt.xticks(sorted(data["sample_size"].dropna().unique()))
    plt.grid(True, axis="y", alpha=0.35)
    plt.legend()

    save_figure("04_best_scheme_error_band_vs_group_size.png")


def plot_within_bin_spread(devices, summary, scheme_name):
    """
    Plot the distribution of device peak kW inside each bin.
    """
    edges = get_scheme_edges(summary, scheme_name)
    labels = []

    for left, right in zip(edges[:-1], edges[1:]):
        if math.isinf(right):
            labels.append(f"{left:g}+")
        else:
            labels.append(f"{left:g}-{right:g}")

    data = devices.copy()
    data["kw_bin"] = pd.cut(
        data["peak_kw"],
        bins=edges,
        labels=labels,
        right=False,
        include_lowest=True,
    )

    plot_data = [
        data[data["kw_bin"].astype(str) == label]["peak_kw"].dropna()
        for label in labels
    ]

    plt.figure(figsize=(11, 5.8))
    plt.boxplot(plot_data, labels=labels, showfliers=True)

    plt.title(f"Within-bin peak-kW spread\n{scheme_name}")
    plt.xlabel("Observed peak kW bin")
    plt.ylabel("Device observed monthly peak cooling kW")
    plt.xticks(rotation=30, ha="right")
    plt.grid(True, axis="y", alpha=0.35)

    text = (
        "Shorter boxes mean devices inside the bin are more electrically similar. "
        "That is what we want for small transformer groups."
    )
    plt.figtext(0.01, 0.01, text, ha="left", fontsize=9)

    save_figure(f"05_within_bin_peak_kw_spread_{scheme_name}.png")


def plot_group_count_heatmap(group_summary, scheme_name):
    """
    Plot number of devices in each upgrade/bin group.
    """
    data = group_summary[group_summary["scheme_name"] == scheme_name].copy()

    table = (
        data
        .pivot_table(
            index="kw_bin",
            columns="upgrade",
            values="n_devices",
            aggfunc="sum",
            fill_value=0,
            observed=False,
        )
        .reindex(columns=upgrades)
    )

    plt.figure(figsize=(8.8, 5.8))
    image = plt.imshow(table.values, aspect="auto")

    plt.title(f"Device counts by kW bin and upgrade\n{scheme_name}")
    plt.xlabel("Upgrade")
    plt.ylabel("Observed peak kW bin")
    plt.xticks(range(len(upgrades)), [upgrade_labels[u] for u in upgrades], rotation=0)
    plt.yticks(range(len(table.index)), table.index)

    for row_index in range(table.shape[0]):
        for col_index in range(table.shape[1]):
            value = int(table.iloc[row_index, col_index])
            plt.text(col_index, row_index, str(value), ha="center", va="center")

    plt.colorbar(image, label="Number of active cooling devices")

    text = (
        "This plot checks whether each bin has enough devices in each upgrade. "
        "Very small counts are less reliable for transformer sampling."
    )
    plt.figtext(0.01, 0.01, text, ha="left", fontsize=9)

    save_figure(f"06_group_counts_heatmap_{scheme_name}.png")


def make_plain_language_summary(summary, bootstrap_by_size):
    """
    Save a small text summary explaining the main idea.
    """
    best_row = summary[summary["scheme_name"] == best_scheme].iloc[0]

    best_by_size = bootstrap_by_size[
        bootstrap_by_size["scheme_name"] == best_scheme
    ].sort_values("sample_size").copy()

    lines = []

    lines.append("# Plain-language interpretation of the kW-bin sweep")
    lines.append("")
    lines.append("The sweep tests different ways to group cooling devices by observed electrical kW.")
    lines.append("")
    lines.append("A good binning scheme should do two things:")
    lines.append("")
    lines.append("1. Put electrically similar devices in the same bin.")
    lines.append("2. Keep enough devices in each bin so small transformer groups can be represented.")
    lines.append("")
    lines.append(f"The best scheme in the current sweep is `{best_scheme}`.")
    lines.append("")
    lines.append("Its bin labels are:")
    lines.append("")
    lines.append(f"```text\n{best_row['labels']}\n```")
    lines.append("")
    lines.append("This is a pooled quantile scheme. That means all active cooling devices from up00, up01, and up02 were pooled together, sorted by observed peak kW, and split into eight similarly populated groups.")
    lines.append("")
    lines.append("The bin edges look unusual because they come from the data distribution, not from manually chosen round numbers.")
    lines.append("")
    lines.append("Prediction error for the best scheme by transformer group size:")
    lines.append("")
    lines.append("```text")
    for _, row in best_by_size.iterrows():
        lines.append(
            f"{int(row['sample_size']):>2} devices: "
            f"median error = {row['median_absolute_percentage_error']:.2f}%, "
            f"p90 error = {row['p90_absolute_percentage_error']:.2f}%"
        )
    lines.append("```")
    lines.append("")
    lines.append("The most important figure is `03_prediction_error_vs_group_size.png` because it directly connects the binning method to the transformer problem.")
    lines.append("")

    output_path = figures_dir / "plain_language_summary.md"
    output_path.write_text("\n".join(lines))

    print(f"Saved: {output_path}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    """
    Create intuitive kW-bin sweep visualizations.
    """
    figures_dir.mkdir(parents=True, exist_ok=True)

    devices = load_primary_devices()
    summary = read_required_csv(summary_file)
    group_summary = read_required_csv(group_file)
    bootstrap_by_size = read_required_csv(bootstrap_by_size_file)

    print("\nPrimary active cooling devices used for visualization:")
    print(len(devices))

    print("\nSelected schemes:")
    for scheme in selected_schemes:
        if scheme in set(summary["scheme_name"]):
            print(f"  - {scheme}")

    plot_histogram_with_bin_boundaries(devices, summary, best_scheme)
    plot_bin_ruler(summary)
    plot_error_vs_group_size(bootstrap_by_size)
    plot_error_band_vs_group_size(bootstrap_by_size)
    plot_within_bin_spread(devices, summary, best_scheme)
    plot_within_bin_spread(devices, summary, "fixed_0p5_to_3_then_4plus")
    plot_group_count_heatmap(group_summary, best_scheme)
    make_plain_language_summary(summary, bootstrap_by_size)

    print("\nDone. Explained figures saved to:")
    print(figures_dir)


if __name__ == "__main__":
    main()
