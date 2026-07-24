"""
07_plot_daily_cooling_metrics.py

Create daily cooling HVAC figures.

This script reads:

- outputs/daily_cooling_metrics.csv

It creates two levels of plots:

1. Overall daily behavior by upgrade.
2. Daily behavior by cooling capacity bin.

Output folder:

- outputs/figures/daily_cooling_metrics

Important:
This script does not modify any simulation files.
"""

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


# ---------------------------------------------------------------------------
# User settings
# ---------------------------------------------------------------------------
# Rule: keep variable names lowercase.

analysis_dir = Path("./outputs")
figures_dir = analysis_dir / "figures" / "daily_cooling_metrics"

daily_metrics_file = analysis_dir / "daily_cooling_metrics.csv"

upgrades = ["up00", "up01", "up02"]
upgrade_labels = {
    "up00": "Baseline (up00)",
    "up01": "Upgrade 1 (up01)",
    "up02": "Upgrade 2 (up02)",
}

capacity_bins = [0, 1, 2, 3, 4, 5, float("inf")]
capacity_labels = ["0-1", "1-2", "2-3", "3-4", "4-5", "5+"]

minimum_on_minutes_for_switching_rate = 10


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

def save_figure(filename):
    """
    Save the current matplotlib figure.
    """
    figures_dir.mkdir(parents=True, exist_ok=True)
    output_path = figures_dir / filename
    plt.tight_layout()
    plt.savefig(output_path, dpi=300, bbox_inches="tight")
    plt.close()

    print(f"Saved: {output_path}")


def load_daily_metrics():
    """
    Load daily cooling metrics and add capacity bins.
    """
    if not daily_metrics_file.is_file():
        raise FileNotFoundError(
            f"daily_metrics_file does not exist: {daily_metrics_file}\n"
            "Run 06_build_daily_cooling_metrics.py first."
        )

    data = pd.read_csv(daily_metrics_file)

    numeric_cols = [
        "cooling_capacity_tons",
        "daily_energy_kwh",
        "daily_peak_kw",
        "daily_avg_kw",
        "daily_on_minutes",
        "daily_duty_cycle",
        "daily_switching_events",
        "daily_peak_kw_per_ton",
        "daily_kwh_per_ton",
        "daily_switching_events_per_on_hour",
    ]

    for col in numeric_cols:
        if col in data.columns:
            data[col] = pd.to_numeric(data[col], errors="coerce")

    data = data[data["upgrade"].isin(upgrades)].copy()

    data["capacity_bin"] = pd.cut(
        data["cooling_capacity_tons"],
        bins=capacity_bins,
        labels=capacity_labels,
        right=False,
    )

    data["upgrade_label"] = data["upgrade"].map(upgrade_labels)

    return data


def grouped_daily_table(data, value_col, agg="median"):
    """
    Create a day-by-upgrade table for line plots.
    """
    table = (
        data
        .groupby(["day_index", "upgrade"], observed=False)[value_col]
        .agg(agg)
        .unstack()
        .reindex(columns=upgrades)
    )

    return table


def plot_daily_line(data, value_col, ylabel, title, filename, agg="median"):
    """
    Plot a daily metric as a line plot by upgrade.
    """
    table = grouped_daily_table(data, value_col, agg=agg)

    plt.figure(figsize=(10, 5.5))

    for upgrade in upgrades:
        if upgrade in table.columns:
            plt.plot(
                table.index,
                table[upgrade],
                marker="o",
                linewidth=1.8,
                markersize=3.5,
                label=upgrade_labels[upgrade],
            )

    plt.title(title)
    plt.xlabel("Day of August simulation")
    plt.ylabel(ylabel)
    plt.xticks(range(1, 31, 2))
    plt.grid(True, axis="y", alpha=0.35)
    plt.legend(title="Upgrade")

    save_figure(filename)


def plot_daily_activity_stacked_bar(data):
    """
    Plot active/off/near-never-on day counts by upgrade.
    """
    table = (
        data
        .groupby(["upgrade", "daily_activity_flag"], observed=False)
        .size()
        .unstack(fill_value=0)
        .reindex(upgrades)
    )

    ordered_cols = [
        "active_day",
        "near_never_on_day",
        "near_always_on_day",
        "off_all_day",
    ]

    table = table.reindex(columns=[c for c in ordered_cols if c in table.columns], fill_value=0)

    plt.figure(figsize=(9, 5.5))
    ax = table.plot(kind="bar", stacked=True, ax=plt.gca())

    ax.set_title("Daily cooling activity flags by upgrade")
    ax.set_xlabel("Upgrade")
    ax.set_ylabel("Number of device-days")
    ax.set_xticklabels([upgrade_labels[u] for u in table.index], rotation=0)
    ax.legend(title="Daily activity flag", bbox_to_anchor=(1.02, 1), loc="upper left")
    ax.grid(True, axis="y", alpha=0.35)

    save_figure("01_daily_activity_flags_by_upgrade.png")


def plot_daily_activity_percentage_bar(data):
    """
    Plot daily activity flag percentages by upgrade.
    """
    count_table = (
        data
        .groupby(["upgrade", "daily_activity_flag"], observed=False)
        .size()
        .unstack(fill_value=0)
        .reindex(upgrades)
    )

    ordered_cols = [
        "active_day",
        "near_never_on_day",
        "near_always_on_day",
        "off_all_day",
    ]

    count_table = count_table.reindex(columns=[c for c in ordered_cols if c in count_table.columns], fill_value=0)

    pct_table = count_table.div(count_table.sum(axis=1), axis=0) * 100

    plt.figure(figsize=(9, 5.5))
    ax = pct_table.plot(kind="bar", stacked=True, ax=plt.gca())

    ax.set_title("Daily cooling activity flags by upgrade")
    ax.set_xlabel("Upgrade")
    ax.set_ylabel("Share of device-days (%)")
    ax.set_xticklabels([upgrade_labels[u] for u in pct_table.index], rotation=0)
    ax.legend(title="Daily activity flag", bbox_to_anchor=(1.02, 1), loc="upper left")
    ax.grid(True, axis="y", alpha=0.35)

    save_figure("02_daily_activity_flag_percentages_by_upgrade.png")


def plot_box_by_upgrade(data, value_col, ylabel, title, filename):
    """
    Plot a box plot by upgrade.
    """
    plot_data = [
        data[data["upgrade"] == upgrade][value_col].dropna()
        for upgrade in upgrades
    ]

    plt.figure(figsize=(8.5, 5.5))
    plt.boxplot(plot_data, labels=[upgrade_labels[u] for u in upgrades], showfliers=True)

    plt.title(title)
    plt.xlabel("Upgrade")
    plt.ylabel(ylabel)
    plt.grid(True, axis="y", alpha=0.35)

    save_figure(filename)


def plot_binned_median_bar(data, value_col, ylabel, title, filename):
    """
    Plot median daily metric by capacity bin and upgrade.
    """
    table = (
        data
        .groupby(["capacity_bin", "upgrade"], observed=False)[value_col]
        .median()
        .unstack()
        .reindex(capacity_labels)
        .reindex(columns=upgrades)
    )

    q1 = (
        data
        .groupby(["capacity_bin", "upgrade"], observed=False)[value_col]
        .quantile(0.25)
        .unstack()
        .reindex(capacity_labels)
        .reindex(columns=upgrades)
    )

    q3 = (
        data
        .groupby(["capacity_bin", "upgrade"], observed=False)[value_col]
        .quantile(0.75)
        .unstack()
        .reindex(capacity_labels)
        .reindex(columns=upgrades)
    )

    x = np.arange(len(table.index))
    n_groups = len(upgrades)
    bar_width = 0.72 / n_groups
    offsets = np.linspace(-(n_groups - 1) / 2, (n_groups - 1) / 2, n_groups) * bar_width

    plt.figure(figsize=(11, 5.8))
    ax = plt.gca()

    for i, upgrade in enumerate(upgrades):
        medians = table[upgrade].to_numpy(dtype=float)
        lower_err = medians - q1[upgrade].to_numpy(dtype=float)
        upper_err = q3[upgrade].to_numpy(dtype=float) - medians

        lower_err = np.nan_to_num(lower_err, nan=0.0)
        upper_err = np.nan_to_num(upper_err, nan=0.0)

        ax.bar(
            x + offsets[i],
            medians,
            width=bar_width * 0.92,
            label=upgrade_labels[upgrade],
        )

        ax.errorbar(
            x + offsets[i],
            medians,
            yerr=[lower_err, upper_err],
            fmt="none",
            linewidth=1,
            capsize=3,
        )

    ax.set_title(title)
    ax.set_xlabel("Cooling capacity bin (tons)")
    ax.set_ylabel(ylabel)
    ax.set_xticks(x)
    ax.set_xticklabels(capacity_labels)
    ax.grid(True, axis="y", alpha=0.35)
    ax.legend(title="Upgrade", bbox_to_anchor=(1.02, 1), loc="upper left")

    save_figure(filename)


def save_summary_tables(data):
    """
    Save daily summary tables used by the plots.
    """
    figures_dir.mkdir(parents=True, exist_ok=True)

    daily_activity_counts = (
        data
        .groupby(["upgrade", "daily_activity_flag"], observed=False)
        .size()
        .unstack(fill_value=0)
        .reindex(upgrades)
    )

    daily_activity_percentages = daily_activity_counts.div(
        daily_activity_counts.sum(axis=1),
        axis=0,
    ) * 100

    daily_median_by_upgrade = (
        data
        .groupby("upgrade")
        [[
            "daily_energy_kwh",
            "daily_peak_kw",
            "daily_duty_cycle",
            "daily_switching_events",
            "daily_peak_kw_per_ton",
            "daily_kwh_per_ton",
            "daily_switching_events_per_on_hour",
        ]]
        .median()
        .reindex(upgrades)
    )

    data_switching_stable = data[
        data["daily_on_minutes"] >= minimum_on_minutes_for_switching_rate
    ].copy()

    daily_median_switching_stable = (
        data_switching_stable
        .groupby("upgrade")
        [["daily_switching_events_per_on_hour"]]
        .median()
        .reindex(upgrades)
    )

    binned_daily_medians = (
        data
        .groupby(["capacity_bin", "upgrade"], observed=False)
        [[
            "daily_energy_kwh",
            "daily_peak_kw",
            "daily_duty_cycle",
            "daily_switching_events",
            "daily_peak_kw_per_ton",
            "daily_kwh_per_ton",
        ]]
        .median()
    )

    binned_switching_stable = (
        data_switching_stable
        .groupby(["capacity_bin", "upgrade"], observed=False)
        [["daily_switching_events_per_on_hour"]]
        .median()
    )

    daily_activity_counts.to_csv(figures_dir / "daily_activity_counts_by_upgrade.csv")
    daily_activity_percentages.to_csv(figures_dir / "daily_activity_percentages_by_upgrade.csv")
    daily_median_by_upgrade.to_csv(figures_dir / "daily_median_metrics_by_upgrade.csv")
    daily_median_switching_stable.to_csv(figures_dir / "daily_median_switching_rate_stable_days_by_upgrade.csv")
    binned_daily_medians.to_csv(figures_dir / "binned_daily_median_metrics.csv")
    binned_switching_stable.to_csv(figures_dir / "binned_daily_switching_rate_stable_days.csv")

    print("\nDaily activity counts by upgrade:")
    print(daily_activity_counts)

    print("\nDaily activity percentages by upgrade:")
    print(daily_activity_percentages.round(2))

    print("\nDaily median metrics by upgrade:")
    print(daily_median_by_upgrade)

    print("\nDaily median switching rate on days with at least "
          f"{minimum_on_minutes_for_switching_rate} ON minutes:")
    print(daily_median_switching_stable)

    print("\nBinned daily median metrics:")
    print(binned_daily_medians)

    print("\nBinned daily switching rate on stable ON days:")
    print(binned_switching_stable)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    """
    Create daily cooling metric figures.
    """
    data = load_daily_metrics()

    print("\nDaily cooling rows:")
    print(len(data))

    print("\nDaily rows by upgrade:")
    print(data["upgrade"].value_counts().sort_index())

    save_summary_tables(data)

    active_days = data[data["daily_activity_flag"] == "active_day"].copy()

    switching_stable_days = data[
        (data["daily_activity_flag"] == "active_day")
        & (data["daily_on_minutes"] >= minimum_on_minutes_for_switching_rate)
    ].copy()

    plot_daily_activity_stacked_bar(data)
    plot_daily_activity_percentage_bar(data)

    plot_daily_line(
        data=active_days,
        value_col="daily_energy_kwh",
        ylabel="Median daily cooling energy (kWh)",
        title="Median daily cooling energy by upgrade",
        filename="03_median_daily_energy_by_upgrade.png",
    )

    plot_daily_line(
        data=active_days,
        value_col="daily_peak_kw",
        ylabel="Median daily peak cooling power (kW)",
        title="Median daily peak kW by upgrade",
        filename="04_median_daily_peak_kw_by_upgrade.png",
    )

    plot_daily_line(
        data=active_days,
        value_col="daily_duty_cycle",
        ylabel="Median daily duty cycle",
        title="Median daily cooling duty cycle by upgrade",
        filename="05_median_daily_duty_cycle_by_upgrade.png",
    )

    plot_daily_line(
        data=active_days,
        value_col="daily_switching_events",
        ylabel="Median daily switching events",
        title="Median daily switching events by upgrade",
        filename="06_median_daily_switching_events_by_upgrade.png",
    )

    plot_daily_line(
        data=active_days,
        value_col="daily_peak_kw_per_ton",
        ylabel="Median daily peak kW per ton",
        title="Median daily peak kW per ton by upgrade",
        filename="07_median_daily_peak_kw_per_ton_by_upgrade.png",
    )

    plot_daily_line(
        data=active_days,
        value_col="daily_kwh_per_ton",
        ylabel="Median daily kWh per ton",
        title="Median daily cooling energy per ton by upgrade",
        filename="08_median_daily_kwh_per_ton_by_upgrade.png",
    )

    plot_daily_line(
        data=switching_stable_days,
        value_col="daily_switching_events_per_on_hour",
        ylabel="Median switches per ON-hour",
        title=(
            "Median daily switching rate by upgrade "
            f"(days with at least {minimum_on_minutes_for_switching_rate} ON minutes)"
        ),
        filename="09_median_daily_switching_rate_by_upgrade_stable_days.png",
    )

    plot_box_by_upgrade(
        data=active_days,
        value_col="daily_kwh_per_ton",
        ylabel="Daily cooling energy per ton (kWh/ton)",
        title="Daily cooling energy per ton by upgrade",
        filename="10_daily_kwh_per_ton_boxplot_by_upgrade.png",
    )

    plot_box_by_upgrade(
        data=active_days,
        value_col="daily_peak_kw_per_ton",
        ylabel="Daily peak cooling power per ton (kW/ton)",
        title="Daily peak kW per ton by upgrade",
        filename="11_daily_peak_kw_per_ton_boxplot_by_upgrade.png",
    )

    plot_box_by_upgrade(
        data=switching_stable_days,
        value_col="daily_switching_events_per_on_hour",
        ylabel="Switches per ON-hour",
        title=(
            "Daily switching rate by upgrade "
            f"(days with at least {minimum_on_minutes_for_switching_rate} ON minutes)"
        ),
        filename="12_daily_switching_rate_boxplot_stable_days_by_upgrade.png",
    )

    plot_binned_median_bar(
        data=active_days,
        value_col="daily_peak_kw_per_ton",
        ylabel="Median daily peak kW per ton",
        title="Median daily peak kW per ton by cooling capacity bin",
        filename="13_binned_daily_peak_kw_per_ton.png",
    )

    plot_binned_median_bar(
        data=active_days,
        value_col="daily_kwh_per_ton",
        ylabel="Median daily kWh per ton",
        title="Median daily cooling energy per ton by capacity bin",
        filename="14_binned_daily_kwh_per_ton.png",
    )

    plot_binned_median_bar(
        data=active_days,
        value_col="daily_duty_cycle",
        ylabel="Median daily duty cycle",
        title="Median daily cooling duty cycle by capacity bin",
        filename="15_binned_daily_duty_cycle.png",
    )

    plot_binned_median_bar(
        data=switching_stable_days,
        value_col="daily_switching_events_per_on_hour",
        ylabel="Median switches per ON-hour",
        title=(
            "Median switching rate by capacity bin "
            f"(days with at least {minimum_on_minutes_for_switching_rate} ON minutes)"
        ),
        filename="16_binned_daily_switching_rate_stable_days.png",
    )

    print("\nDone. Figures saved to:")
    print(figures_dir)


if __name__ == "__main__":
    main()
