'''
Author: Midrar Adham
Created: Thu Jul 23 2026
'''
"""
04_plot_cooling_hvac_analysis.py

Create cooling-only HVAC analysis plots.

This script reads:

- outputs/hvac_analysis/hvac_state_diagnostics.csv
- outputs/hvac_analysis/canonical_electric_hvac_devices.csv

It focuses only on cooling for the current August simulation study.

Output folder:

outputs/hvac_analysis/figures/cooling

Important:
This script does not modify any simulation files.
"""

from pathlib import Path
import pandas as pd
import matplotlib.pyplot as plt


# ---------------------------------------------------------------------------
# User settings
# ---------------------------------------------------------------------------
# Rule: keep variable names lowercase.

analysis_dir = Path("./outputs/")
figures_dir = analysis_dir / "figures" / "cooling"

diagnostics_file = analysis_dir / "hvac_state_diagnostics.csv"
canonical_file = analysis_dir / "canonical_electric_hvac_devices.csv"

upgrades = ["up00", "up01", "up02"]
service = "cooling"

# Use device population for count plots.
device_population_flag = "include_in_device_population"

# Use active operation rows for operation plots.
active_operation_flag = "include_in_active_operation_plots"

# Use OLS candidate rows for later model-focused plots.
ols_candidate_flag = "include_in_ols_candidate_pool"


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

def save_figure(filename):
    """
    Save the current matplotlib figure with consistent settings.
    """
    figures_dir.mkdir(parents=True, exist_ok=True)
    output_path = figures_dir / filename
    plt.tight_layout()
    plt.savefig(output_path, dpi=300, bbox_inches="tight")
    plt.close()

    print(f"Saved: {output_path}")


def prepare_cooling_diagnostics(diagnostics):
    """
    Keep only cooling rows for the selected upgrades.
    """
    cooling = diagnostics[
        (diagnostics["service"] == service)
        & (diagnostics["upgrade"].isin(upgrades))
    ].copy()

    return cooling


def plot_device_population(cooling):
    """
    Plot number of electric cooling-capable devices by upgrade.
    """
    counts = (
        cooling[cooling[device_population_flag] == True]
        .groupby("upgrade")
        .size()
        .reindex(upgrades, fill_value=0)
    )

    plt.figure(figsize=(7, 4))
    counts.plot(kind="bar")
    plt.title("Electric Cooling Device Population by Upgrade")
    plt.xlabel("Upgrade")
    plt.ylabel("Number of building-upgrade cases")
    plt.xticks(rotation=0)

    for index, value in enumerate(counts.values):
        plt.text(index, value, str(int(value)), ha="center", va="bottom")

    save_figure("01_cooling_device_population_by_upgrade.png")


def plot_active_operation_population(cooling):
    """
    Plot number of active cooling devices by upgrade.

    Active means the device had a complete time-series, had a cooling column,
    had cooling metadata, and was not near-never-on.
    """
    counts = (
        cooling[cooling[active_operation_flag] == True]
        .groupby("upgrade")
        .size()
        .reindex(upgrades, fill_value=0)
    )

    plt.figure(figsize=(7, 4))
    counts.plot(kind="bar")
    plt.title("Active Cooling Operation Population by Upgrade")
    plt.xlabel("Upgrade")
    plt.ylabel("Number of active cooling cases")
    plt.xticks(rotation=0)

    for index, value in enumerate(counts.values):
        plt.text(index, value, str(int(value)), ha="center", va="bottom")

    save_figure("02_cooling_active_operation_population_by_upgrade.png")


def plot_diagnostic_flags(cooling):
    """
    Plot diagnostic flag counts for cooling rows.
    """
    flag_counts = (
        cooling
        .groupby(["upgrade", "diagnostic_flag"])
        .size()
        .unstack(fill_value=0)
        .reindex(upgrades)
    )

    plt.figure(figsize=(9, 5))
    flag_counts.plot(kind="bar", stacked=True, ax=plt.gca())
    plt.title("Cooling Diagnostic Flags by Upgrade")
    plt.xlabel("Upgrade")
    plt.ylabel("Number of cooling rows")
    plt.xticks(rotation=0)
    plt.legend(title="Diagnostic flag", bbox_to_anchor=(1.02, 1), loc="upper left")

    save_figure("03_cooling_diagnostic_flags_by_upgrade.png")


def plot_boxplot_by_upgrade(cooling, column, ylabel, title, filename, use_active_rows=True):
    """
    Create a box plot for one cooling metric by upgrade.
    """
    flag = active_operation_flag if use_active_rows else device_population_flag
    data = cooling[cooling[flag] == True].copy()

    grouped_values = [
        data[data["upgrade"] == upgrade][column].dropna().values
        for upgrade in upgrades
    ]

    plt.figure(figsize=(7, 4))
    plt.boxplot(grouped_values, labels=upgrades, showfliers=True)
    plt.title(title)
    plt.xlabel("Upgrade")
    plt.ylabel(ylabel)

    save_figure(filename)


def plot_scatter_capacity_vs_peak(cooling):
    """
    Plot cooling capacity versus observed peak electric kW.
    """
    data = cooling[cooling[active_operation_flag] == True].copy()
    data = data.dropna(subset=["cooling_capacity_tons", "peak_kw"])

    plt.figure(figsize=(7, 5))

    for upgrade in upgrades:
        subset = data[data["upgrade"] == upgrade]
        plt.scatter(
            subset["cooling_capacity_tons"],
            subset["peak_kw"],
            label=upgrade,
            alpha=0.6,
            s=18,
        )

    plt.title("Cooling Capacity vs Observed Peak Electric Power")
    plt.xlabel("Cooling capacity (tons)")
    plt.ylabel("Observed peak cooling electric power (kW)")
    plt.legend(title="Upgrade")

    save_figure("08_cooling_capacity_vs_peak_kw.png")


def plot_scatter_duty_cycle_vs_energy(cooling):
    """
    Plot duty cycle versus total cooling energy.
    """
    data = cooling[cooling[active_operation_flag] == True].copy()

    plt.figure(figsize=(7, 5))

    for upgrade in upgrades:
        subset = data[data["upgrade"] == upgrade]
        plt.scatter(
            subset["duty_cycle"],
            subset["total_energy_kwh"],
            label=upgrade,
            alpha=0.6,
            s=18,
        )

    plt.title("Cooling Duty Cycle vs Monthly Cooling Energy")
    plt.xlabel("Cooling duty cycle")
    plt.ylabel("Monthly cooling energy (kWh)")
    plt.legend(title="Upgrade")

    save_figure("09_cooling_duty_cycle_vs_energy.png")


def plot_device_type_counts(cooling):
    """
    Plot active cooling rows by upgrade and device type.
    """
    data = cooling[cooling[active_operation_flag] == True].copy()

    counts = (
        data
        .groupby(["upgrade", "device_type"])
        .size()
        .unstack(fill_value=0)
        .reindex(upgrades)
    )

    plt.figure(figsize=(9, 5))
    counts.plot(kind="bar", stacked=True, ax=plt.gca())
    plt.title("Active Cooling Devices by Upgrade and Device Type")
    plt.xlabel("Upgrade")
    plt.ylabel("Number of active cooling cases")
    plt.xticks(rotation=0)
    plt.legend(title="Device type", bbox_to_anchor=(1.02, 1), loc="upper left")

    save_figure("10_cooling_active_device_type_counts.png")


def save_cooling_summary_tables(cooling):
    """
    Save compact summary tables used by the plots.
    """
    figures_dir.mkdir(parents=True, exist_ok=True)

    count_summary = (
        cooling
        .groupby("upgrade")
        .agg(
            total_rows=("building_id", "count"),
            device_population=(device_population_flag, "sum"),
            active_operation=(active_operation_flag, "sum"),
            ols_candidates=(ols_candidate_flag, "sum"),
        )
        .reset_index()
    )

    active = cooling[cooling[active_operation_flag] == True].copy()

    metric_summary = (
        active
        .groupby("upgrade")
        .agg(
            n_active=("building_id", "count"),
            mean_duty_cycle=("duty_cycle", "mean"),
            median_duty_cycle=("duty_cycle", "median"),
            mean_total_energy_kwh=("total_energy_kwh", "mean"),
            median_total_energy_kwh=("total_energy_kwh", "median"),
            mean_peak_kw=("peak_kw", "mean"),
            median_peak_kw=("peak_kw", "median"),
            mean_switching_events=("n_switching_events", "mean"),
            median_switching_events=("n_switching_events", "median"),
        )
        .reset_index()
    )

    count_summary_path = figures_dir / "cooling_count_summary.csv"
    metric_summary_path = figures_dir / "cooling_metric_summary.csv"

    count_summary.to_csv(count_summary_path, index=False)
    metric_summary.to_csv(metric_summary_path, index=False)

    print(f"Saved: {count_summary_path}")
    print(f"Saved: {metric_summary_path}")

    print("\nCooling count summary:")
    print(count_summary)

    print("\nCooling metric summary for active operation rows:")
    print(metric_summary)


# ---------------------------------------------------------------------------
# Main script
# ---------------------------------------------------------------------------

def main():
    """
    Create all cooling HVAC analysis plots.
    """
    if not diagnostics_file.is_file():
        raise FileNotFoundError(
            f"diagnostics_file does not exist: {diagnostics_file}\n"
            "Run 03_build_hvac_state_diagnostics.py first."
        )

    if not canonical_file.is_file():
        raise FileNotFoundError(
            f"canonical_file does not exist: {canonical_file}\n"
            "Run 02b_build_canonical_electric_hvac_devices.py first."
        )

    diagnostics = pd.read_csv(diagnostics_file)
    cooling = prepare_cooling_diagnostics(diagnostics)

    print("\nCooling rows:")
    print(len(cooling))

    print("\nCooling rows by upgrade:")
    print(cooling["upgrade"].value_counts().sort_index())

    print("\nDevice population rows by upgrade:")
    print(
        cooling
        .groupby("upgrade")[device_population_flag]
        .sum()
        .reindex(upgrades, fill_value=0)
    )

    print("\nActive operation rows by upgrade:")
    print(
        cooling
        .groupby("upgrade")[active_operation_flag]
        .sum()
        .reindex(upgrades, fill_value=0)
    )

    save_cooling_summary_tables(cooling)

    plot_device_population(cooling)
    plot_active_operation_population(cooling)
    plot_diagnostic_flags(cooling)

    plot_boxplot_by_upgrade(
        cooling=cooling,
        column="duty_cycle",
        ylabel="Duty cycle",
        title="Cooling Duty Cycle by Upgrade",
        filename="04_cooling_duty_cycle_by_upgrade.png",
    )

    plot_boxplot_by_upgrade(
        cooling=cooling,
        column="total_energy_kwh",
        ylabel="Monthly cooling energy (kWh)",
        title="Monthly Cooling Energy by Upgrade",
        filename="05_cooling_total_energy_by_upgrade.png",
    )

    plot_boxplot_by_upgrade(
        cooling=cooling,
        column="peak_kw",
        ylabel="Observed peak cooling electric power (kW)",
        title="Observed Peak Cooling Electric Power by Upgrade",
        filename="06_cooling_peak_kw_by_upgrade.png",
    )

    plot_boxplot_by_upgrade(
        cooling=cooling,
        column="n_switching_events",
        ylabel="Number of switching events",
        title="Cooling Switching Events by Upgrade",
        filename="07_cooling_switching_events_by_upgrade.png",
    )

    plot_scatter_capacity_vs_peak(cooling)
    plot_scatter_duty_cycle_vs_energy(cooling)
    plot_device_type_counts(cooling)

    print("\nDone. Cooling figures saved to:")
    print(figures_dir)


if __name__ == "__main__":
    main()
