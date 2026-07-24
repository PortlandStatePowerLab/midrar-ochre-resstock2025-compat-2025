'''
Author: MidrarAdham
Created: Fri Jul 24 2026
'''
"""
08_sweep_cooling_kw_bins.py

Sweep electrical kW bin definitions for active cooling HVAC devices.

Goal:
    Find kW bins that are useful for transformer-level OLS/Bayesian aggregation.

Motivation:
    The OLS/Bayesian setup has difficulty predicting kW for small groups.
    In the transformer study, the largest 75 kVA transformer case has about
    13 houses/HVAC devices, and smaller transformers may have fewer devices.

    Therefore, this script tests multiple realistic group sizes rather than
    only testing 10 devices.

Inputs:
    ./outputs/hvac_state_diagnostics.csv
    ./outputs/daily_cooling_metrics.csv

Outputs:
    ./outputs/kw_bin_sweep/cooling_kw_bin_sweep_summary.csv
    ./outputs/kw_bin_sweep/cooling_kw_bin_sweep_groups.csv
    ./outputs/kw_bin_sweep/cooling_kw_bin_sweep_bootstrap.csv
    ./outputs/kw_bin_sweep/cooling_kw_bin_sweep_excluded_large_devices.csv
    ./outputs/kw_bin_sweep/figures/*.png

Important:
    This is not the final OLS model. It is a bin-quality diagnostic.
    It uses observed peak cooling kW as the binning variable and tests
    how stable those bins are when sampled in realistic transformer-size groups.
"""

from pathlib import Path
import math

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


# ---------------------------------------------------------------------------
# User settings
# ---------------------------------------------------------------------------
# Rule: keep variable names lowercase.

analysis_dir = Path("./outputs")
output_dir = analysis_dir / "kw_bin_sweep"
figures_dir = output_dir / "figures"

diagnostics_file = analysis_dir / "hvac_state_diagnostics.csv"
daily_metrics_file = analysis_dir / "daily_cooling_metrics.csv"

upgrades = ["up00", "up01", "up02"]
service = "cooling"
active_operation_flag = "include_in_active_operation_plots"

# Main binning variable.
# This is observed monthly peak cooling electric power.
bin_variable = "peak_kw"

# Main QC filter.
# Devices above this size are kept in a separate excluded-device CSV, but are
# removed from the main kW-bin sweep because they are unusually large for
# residential cooling systems and can dominate small transformer samples.
maximum_cooling_capacity_tons = 5.0
exclude_large_capacity_devices = True

# Transformer-level sample sizes.
# These represent small groups of HVAC devices connected to a transformer.
# The largest case is 13 devices for the 75 kVA transformer.
sample_sizes = [2, 3, 4, 5, 6, 8, 10, 13]

bootstrap_repetitions = 500
random_seed = 42

minimum_devices_per_group = 5
preferred_devices_per_group = 13

# This is only for the daily switching-rate summary attached to the bin table.
# It is separate from the transformer-level sample_sizes above.
minimum_daily_on_minutes_for_switching_rate = 10


# ---------------------------------------------------------------------------
# Candidate bin schemes
# ---------------------------------------------------------------------------

fixed_bin_schemes = {
    "fixed_0p25_to_2_then_3plus": [0, 0.25, 0.5, 0.75, 1, 1.5, 2, 3, float("inf")],
    "fixed_0p5_to_3_then_4plus": [0, 0.5, 1, 1.5, 2, 2.5, 3, 4, float("inf")],
    "fixed_0p5_to_2_then_wide": [0, 0.5, 1, 1.5, 2, 3, 4, float("inf")],
    "fixed_0p5_1_2_3_5plus": [0, 0.5, 1, 2, 3, 5, float("inf")],
    "fixed_1kw_bins": [0, 1, 2, 3, 4, 5, float("inf")],
    "fixed_small_medium_large": [0, 1, 2, 4, float("inf")],
}


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

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


def make_bin_labels(edges):
    """
    Convert numeric bin edges into readable labels.
    """
    labels = []

    for left, right in zip(edges[:-1], edges[1:]):
        if math.isinf(right):
            labels.append(f"{left:g}+")
        else:
            labels.append(f"{left:g}-{right:g}")

    return labels


def load_device_table():
    """
    Load active cooling device-level diagnostics and apply QC filters.
    """
    if not diagnostics_file.is_file():
        raise FileNotFoundError(f"Missing diagnostics file: {diagnostics_file}")

    diagnostics = pd.read_csv(diagnostics_file)

    diagnostics[active_operation_flag] = normalize_bool(diagnostics[active_operation_flag])

    devices_raw = diagnostics[
        (diagnostics["service"] == service)
        & (diagnostics["upgrade"].isin(upgrades))
        & (diagnostics[active_operation_flag] == True)
    ].copy()

    numeric_cols = [
        "peak_kw",
        "avg_kw",
        "total_energy_kwh",
        "duty_cycle",
        "n_switching_events",
        "cooling_capacity_tons",
    ]

    for col in numeric_cols:
        devices_raw[col] = pd.to_numeric(devices_raw[col], errors="coerce")

    devices_raw = devices_raw.dropna(subset=[bin_variable]).copy()

    devices_raw["device_key"] = (
        devices_raw["building_id"].astype(str)
        + "__"
        + devices_raw["upgrade"].astype(str)
    )

    if exclude_large_capacity_devices:
        excluded_large_devices = devices_raw[
            devices_raw["cooling_capacity_tons"] > maximum_cooling_capacity_tons
        ].copy()

        devices = devices_raw[
            (devices_raw["cooling_capacity_tons"].isna())
            | (devices_raw["cooling_capacity_tons"] <= maximum_cooling_capacity_tons)
        ].copy()
    else:
        excluded_large_devices = pd.DataFrame()
        devices = devices_raw.copy()

    return devices, devices_raw, excluded_large_devices


def load_daily_summary():
    """
    Load daily metrics and collapse them to one row per device.
    """
    if not daily_metrics_file.is_file():
        print(f"Daily metrics file not found: {daily_metrics_file}")
        print("The sweep will run using monthly diagnostics only.")
        return pd.DataFrame()

    daily = pd.read_csv(daily_metrics_file)

    numeric_cols = [
        "daily_energy_kwh",
        "daily_peak_kw",
        "daily_duty_cycle",
        "daily_switching_events",
        "daily_peak_kw_per_ton",
        "daily_kwh_per_ton",
        "daily_switching_events_per_on_hour",
        "daily_on_minutes",
    ]

    for col in numeric_cols:
        daily[col] = pd.to_numeric(daily[col], errors="coerce")

    daily = daily[daily["upgrade"].isin(upgrades)].copy()

    daily["device_key"] = (
        daily["building_id"].astype(str)
        + "__"
        + daily["upgrade"].astype(str)
    )

    daily["is_active_day"] = daily["daily_activity_flag"] == "active_day"
    daily["is_stable_on_day"] = (
        daily["is_active_day"]
        & (daily["daily_on_minutes"] >= minimum_daily_on_minutes_for_switching_rate)
    )

    stable = daily[daily["is_stable_on_day"]].copy()

    summary = (
        daily
        .groupby("device_key", observed=False)
        .agg(
            daily_rows=("day_index", "count"),
            active_day_share=("is_active_day", "mean"),
            median_daily_energy_kwh=("daily_energy_kwh", "median"),
            median_daily_peak_kw=("daily_peak_kw", "median"),
            median_daily_duty_cycle=("daily_duty_cycle", "median"),
            median_daily_kwh_per_ton=("daily_kwh_per_ton", "median"),
            median_daily_peak_kw_per_ton=("daily_peak_kw_per_ton", "median"),
        )
        .reset_index()
    )

    if len(stable) > 0:
        stable_summary = (
            stable
            .groupby("device_key", observed=False)
            .agg(
                stable_on_day_count=("day_index", "count"),
                median_switches_per_on_hour_10min=("daily_switching_events_per_on_hour", "median"),
            )
            .reset_index()
        )

        summary = summary.merge(stable_summary, on="device_key", how="left")
    else:
        summary["stable_on_day_count"] = 0
        summary["median_switches_per_on_hour_10min"] = np.nan

    summary["stable_on_day_count"] = summary["stable_on_day_count"].fillna(0)

    return summary


def make_quantile_bin_schemes(devices):
    """
    Create pooled quantile bin schemes using observed peak kW.

    Quantile bins are calculated after the >5 ton QC filter, so the quantiles
    reflect the primary analysis population.
    """
    schemes = {}

    values = devices[bin_variable].dropna()

    for n_bins in [3, 4, 5, 6, 7, 8]:
        quantiles = np.linspace(0, 1, n_bins + 1)
        edges = values.quantile(quantiles).to_numpy()
        edges[0] = 0
        edges[-1] = float("inf")
        edges = np.unique(np.round(edges, 4))

        if len(edges) >= 3:
            schemes[f"pooled_quantile_{n_bins}_bins"] = list(edges)

    return schemes


def assign_bins(devices, edges):
    """
    Assign kW bins to devices.
    """
    labels = make_bin_labels(edges)

    output = devices.copy()
    output["kw_bin"] = pd.cut(
        output[bin_variable],
        bins=edges,
        labels=labels,
        right=False,
        include_lowest=True,
    )

    return output, labels


def summarize_groups(devices_with_bins, scheme_name, labels):
    """
    Summarize each upgrade and bin group.
    """
    rows = []

    for upgrade in upgrades:
        upgrade_devices = devices_with_bins[devices_with_bins["upgrade"] == upgrade].copy()

        for label in labels:
            group = upgrade_devices[upgrade_devices["kw_bin"].astype(str) == label].copy()

            n_devices = len(group)

            if n_devices == 0:
                rows.append({
                    "scheme_name": scheme_name,
                    "upgrade": upgrade,
                    "kw_bin": label,
                    "n_devices": 0,
                    "mean_peak_kw": np.nan,
                    "median_peak_kw": np.nan,
                    "std_peak_kw": np.nan,
                    "cv_peak_kw": np.nan,
                    "median_total_energy_kwh": np.nan,
                    "median_duty_cycle": np.nan,
                    "median_switching_events": np.nan,
                    "median_cooling_capacity_tons": np.nan,
                    "active_day_share": np.nan,
                    "median_daily_kwh_per_ton": np.nan,
                    "median_daily_peak_kw_per_ton": np.nan,
                    "median_switches_per_on_hour_10min": np.nan,
                    "has_minimum_devices": False,
                    "has_preferred_devices": False,
                })
                continue

            mean_peak_kw = group["peak_kw"].mean()
            std_peak_kw = group["peak_kw"].std(ddof=1)
            cv_peak_kw = std_peak_kw / mean_peak_kw if mean_peak_kw > 0 else np.nan

            rows.append({
                "scheme_name": scheme_name,
                "upgrade": upgrade,
                "kw_bin": label,
                "n_devices": n_devices,
                "mean_peak_kw": mean_peak_kw,
                "median_peak_kw": group["peak_kw"].median(),
                "std_peak_kw": std_peak_kw,
                "cv_peak_kw": cv_peak_kw,
                "median_total_energy_kwh": group["total_energy_kwh"].median(),
                "median_duty_cycle": group["duty_cycle"].median(),
                "median_switching_events": group["n_switching_events"].median(),
                "median_cooling_capacity_tons": group["cooling_capacity_tons"].median(),
                "active_day_share": group["active_day_share"].median() if "active_day_share" in group else np.nan,
                "median_daily_kwh_per_ton": group["median_daily_kwh_per_ton"].median() if "median_daily_kwh_per_ton" in group else np.nan,
                "median_daily_peak_kw_per_ton": group["median_daily_peak_kw_per_ton"].median() if "median_daily_peak_kw_per_ton" in group else np.nan,
                "median_switches_per_on_hour_10min": group["median_switches_per_on_hour_10min"].median() if "median_switches_per_on_hour_10min" in group else np.nan,
                "has_minimum_devices": n_devices >= minimum_devices_per_group,
                "has_preferred_devices": n_devices >= preferred_devices_per_group,
            })

    return pd.DataFrame(rows)


def bootstrap_group_prediction_errors(devices_with_bins, scheme_name, labels, rng):
    """
    Bootstrap transformer-size group prediction errors.

    For each upgrade-bin group and each sample size, sample devices and compare:

        actual aggregate peak kW = sum(sampled device peak_kw)
        predicted aggregate peak kW = sample_size * group median peak_kw

    This is a simple bin-quality proxy:
        if devices inside a bin are electrically similar, this error should be low.
    """
    rows = []

    for upgrade in upgrades:
        upgrade_devices = devices_with_bins[devices_with_bins["upgrade"] == upgrade].copy()

        for label in labels:
            group = upgrade_devices[upgrade_devices["kw_bin"].astype(str) == label].copy()
            group = group.dropna(subset=["peak_kw"])

            n_devices = len(group)

            if n_devices < min(sample_sizes):
                continue

            peak_values = group["peak_kw"].to_numpy(dtype=float)
            representative_peak_kw = float(np.median(peak_values))

            for sample_size in sample_sizes:
                if n_devices < sample_size:
                    continue

                for repetition in range(bootstrap_repetitions):
                    sample = rng.choice(peak_values, size=sample_size, replace=False)

                    actual_kw = float(np.sum(sample))
                    predicted_kw = float(sample_size * representative_peak_kw)

                    absolute_error_kw = abs(predicted_kw - actual_kw)
                    signed_error_kw = predicted_kw - actual_kw

                    if actual_kw > 0:
                        absolute_percentage_error = absolute_error_kw / actual_kw * 100
                    else:
                        absolute_percentage_error = np.nan

                    rows.append({
                        "scheme_name": scheme_name,
                        "upgrade": upgrade,
                        "kw_bin": label,
                        "sample_size": sample_size,
                        "repetition": repetition,
                        "n_devices_in_bin": n_devices,
                        "representative_peak_kw": representative_peak_kw,
                        "actual_kw": actual_kw,
                        "predicted_kw": predicted_kw,
                        "signed_error_kw": signed_error_kw,
                        "absolute_error_kw": absolute_error_kw,
                        "absolute_percentage_error": absolute_percentage_error,
                    })

    return pd.DataFrame(rows)


def summarize_scheme(group_summary, bootstrap_summary, scheme_name, labels):
    """
    Build one summary row for one bin scheme.
    """
    valid_groups = group_summary[group_summary["n_devices"] > 0].copy()
    minimum_groups = group_summary[group_summary["has_minimum_devices"] == True].copy()
    preferred_groups = group_summary[group_summary["has_preferred_devices"] == True].copy()

    total_devices = valid_groups["n_devices"].sum()
    devices_in_minimum_groups = minimum_groups["n_devices"].sum()
    devices_in_preferred_groups = preferred_groups["n_devices"].sum()

    coverage_minimum = devices_in_minimum_groups / total_devices if total_devices > 0 else np.nan
    coverage_preferred = devices_in_preferred_groups / total_devices if total_devices > 0 else np.nan

    weighted_cv = np.average(
        valid_groups["cv_peak_kw"].fillna(0),
        weights=valid_groups["n_devices"],
    ) if total_devices > 0 else np.nan

    weak_group_count = int((valid_groups["n_devices"] < preferred_devices_per_group).sum())
    empty_group_count = int((group_summary["n_devices"] == 0).sum())

    if len(bootstrap_summary) > 0:
        by_size = (
            bootstrap_summary
            .groupby("sample_size", observed=False)["absolute_percentage_error"]
            .median()
        )

        # Smaller transformer groups matter more because that is where the
        # OLS/Bayesian setup struggles most.
        sample_weight_map = {
            2: 3.0,
            3: 3.0,
            4: 2.5,
            5: 2.5,
            6: 2.0,
            8: 1.5,
            10: 1.0,
            13: 1.0,
        }

        weighted_mape_values = []
        weighted_mape_weights = []

        for sample_size, value in by_size.items():
            if pd.notna(value):
                weighted_mape_values.append(value)
                weighted_mape_weights.append(sample_weight_map.get(int(sample_size), 1.0))

        weighted_small_group_mape = (
            np.average(weighted_mape_values, weights=weighted_mape_weights)
            if len(weighted_mape_values) > 0
            else np.nan
        )

        median_mape_by_size = {
            f"median_mape_n{int(sample_size)}": value
            for sample_size, value in by_size.items()
        }

        p90_small_sample_mape = bootstrap_summary["absolute_percentage_error"].quantile(0.90)
        median_small_sample_mae_kw = bootstrap_summary["absolute_error_kw"].median()
    else:
        weighted_small_group_mape = np.nan
        median_mape_by_size = {}
        p90_small_sample_mape = np.nan
        median_small_sample_mae_kw = np.nan

    # Lower score is better.
    # The score combines:
    #   - small-group prediction error, weighted toward smaller groups
    #   - within-bin peak kW variation
    #   - penalty for bins that do not have enough devices
    #   - penalty for empty bins
    score = (
        weighted_small_group_mape
        + 20 * weighted_cv
        + 20 * (1 - coverage_minimum)
        + 10 * (1 - coverage_preferred)
        + empty_group_count
    )

    row = {
        "scheme_name": scheme_name,
        "n_bins": len(labels),
        "labels": " | ".join(labels),
        "total_devices": total_devices,
        "nonempty_group_count": len(valid_groups),
        "empty_group_count": empty_group_count,
        "weak_group_count_below_preferred": weak_group_count,
        "coverage_minimum_groups": coverage_minimum,
        "coverage_preferred_groups": coverage_preferred,
        "weighted_cv_peak_kw": weighted_cv,
        "weighted_small_group_mape_percent": weighted_small_group_mape,
        "p90_small_group_mape_percent": p90_small_sample_mape,
        "median_small_group_mae_kw": median_small_sample_mae_kw,
        "score_lower_is_better": score,
    }

    row.update(median_mape_by_size)

    return row


def summarize_bootstrap_by_sample_size(bootstrap_summary):
    """
    Summarize bootstrap errors by scheme and sample size.
    """
    if len(bootstrap_summary) == 0:
        return pd.DataFrame()

    summary = (
        bootstrap_summary
        .groupby(["scheme_name", "sample_size"], observed=False)
        .agg(
            median_absolute_percentage_error=("absolute_percentage_error", "median"),
            p75_absolute_percentage_error=("absolute_percentage_error", lambda x: x.quantile(0.75)),
            p90_absolute_percentage_error=("absolute_percentage_error", lambda x: x.quantile(0.90)),
            median_absolute_error_kw=("absolute_error_kw", "median"),
            n_bootstrap_rows=("absolute_percentage_error", "count"),
        )
        .reset_index()
    )

    return summary


def summarize_excluded_large_devices(excluded_large_devices):
    """
    Save and summarize devices excluded by the >5 ton filter.
    """
    output_path = output_dir / "cooling_kw_bin_sweep_excluded_large_devices.csv"

    excluded_large_devices.to_csv(output_path, index=False)

    if len(excluded_large_devices) == 0:
        print("\nNo devices excluded by the >5 ton filter.")
        return

    print("\nDevices excluded by the >5 ton filter:")
    print(len(excluded_large_devices))

    print("\nExcluded devices by upgrade:")
    print(excluded_large_devices["upgrade"].value_counts().sort_index())

    cols = [
        "cooling_capacity_tons",
        "peak_kw",
        "total_energy_kwh",
        "duty_cycle",
        "n_switching_events",
    ]

    print("\nExcluded-device summary by upgrade:")
    print(excluded_large_devices.groupby("upgrade")[cols].describe())


def plot_summary_bar(summary, value_col, ylabel, title, filename):
    """
    Plot a horizontal bar chart ranking bin schemes.
    """
    plot_data = summary.sort_values(value_col, ascending=True).copy()

    plt.figure(figsize=(10, max(5, 0.35 * len(plot_data))))
    plt.barh(plot_data["scheme_name"], plot_data[value_col])
    plt.gca().invert_yaxis()
    plt.title(title)
    plt.xlabel(ylabel)
    plt.ylabel("Bin scheme")
    plt.grid(True, axis="x", alpha=0.35)

    save_figure(filename)


def plot_best_scheme_group_counts(group_summary, best_scheme):
    """
    Plot device counts by kW bin and upgrade for the best scheme.
    """
    subset = group_summary[group_summary["scheme_name"] == best_scheme].copy()

    table = (
        subset
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

    plt.figure(figsize=(10, 5.5))
    ax = table.plot(kind="bar", ax=plt.gca())

    ax.set_title(f"Device counts by kW bin for best scheme: {best_scheme}")
    ax.set_xlabel("Observed monthly peak cooling kW bin")
    ax.set_ylabel("Number of active cooling devices")
    ax.grid(True, axis="y", alpha=0.35)
    ax.legend(title="Upgrade")

    save_figure("04_best_scheme_device_counts_by_kw_bin.png")


def plot_best_scheme_mape_by_sample_size(bootstrap_by_size, best_scheme):
    """
    Plot prediction error by transformer-size group for the best scheme.
    """
    subset = bootstrap_by_size[bootstrap_by_size["scheme_name"] == best_scheme].copy()

    plt.figure(figsize=(8.5, 5.2))
    plt.plot(
        subset["sample_size"],
        subset["median_absolute_percentage_error"],
        marker="o",
        linewidth=2,
        label="Median error",
    )
    plt.plot(
        subset["sample_size"],
        subset["p90_absolute_percentage_error"],
        marker="o",
        linewidth=2,
        label="90th percentile error",
    )

    plt.title(f"Small-group prediction error by group size: {best_scheme}")
    plt.xlabel("Number of devices in transformer group")
    plt.ylabel("Absolute percentage error (%)")
    plt.xticks(sample_sizes)
    plt.grid(True, axis="y", alpha=0.35)
    plt.legend()

    save_figure("05_best_scheme_error_by_group_size.png")


def plot_best_scheme_mape_by_group(bootstrap_summary, best_scheme):
    """
    Plot median small-group MAPE by upgrade and kW bin.

    Uses all sample sizes together. The detailed sample-size table is saved
    separately.
    """
    subset = bootstrap_summary[bootstrap_summary["scheme_name"] == best_scheme].copy()

    table = (
        subset
        .groupby(["kw_bin", "upgrade"], observed=False)["absolute_percentage_error"]
        .median()
        .unstack()
        .reindex(columns=upgrades)
    )

    plt.figure(figsize=(10, 5.5))
    ax = table.plot(kind="bar", ax=plt.gca())

    ax.set_title(f"Median prediction error by kW bin: {best_scheme}")
    ax.set_xlabel("Observed monthly peak cooling kW bin")
    ax.set_ylabel("Median absolute percentage error (%)")
    ax.grid(True, axis="y", alpha=0.35)
    ax.legend(title="Upgrade")

    save_figure("06_best_scheme_small_group_mape_by_kw_bin.png")


def save_figure(filename):
    """
    Save current figure.
    """
    figures_dir.mkdir(parents=True, exist_ok=True)
    output_path = figures_dir / filename
    plt.tight_layout()
    plt.savefig(output_path, dpi=300, bbox_inches="tight")
    plt.close()
    print(f"Saved: {output_path}")


# ---------------------------------------------------------------------------
# Main script
# ---------------------------------------------------------------------------

def main():
    """
    Run kW-bin sweep.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    figures_dir.mkdir(parents=True, exist_ok=True)

    rng = np.random.default_rng(random_seed)

    devices, devices_raw, excluded_large_devices = load_device_table()
    daily_summary = load_daily_summary()

    if len(daily_summary) > 0:
        devices = devices.merge(daily_summary, on="device_key", how="left")
        if len(excluded_large_devices) > 0:
            excluded_large_devices = excluded_large_devices.merge(daily_summary, on="device_key", how="left")

    print("\nRaw active cooling devices before >5 ton filter:")
    print(len(devices_raw))

    print("\nRaw devices by upgrade:")
    print(devices_raw["upgrade"].value_counts().sort_index())

    if exclude_large_capacity_devices:
        print("\nPrimary analysis excludes devices with cooling_capacity_tons > "
              f"{maximum_cooling_capacity_tons:g}.")

    summarize_excluded_large_devices(excluded_large_devices)

    print("\nActive cooling devices used in main sweep:")
    print(len(devices))

    print("\nDevices used in main sweep by upgrade:")
    print(devices["upgrade"].value_counts().sort_index())

    quantile_bin_schemes = make_quantile_bin_schemes(devices)

    bin_schemes = {}
    bin_schemes.update(fixed_bin_schemes)
    bin_schemes.update(quantile_bin_schemes)

    all_group_summaries = []
    all_bootstrap_summaries = []
    all_scheme_summaries = []

    for scheme_name, edges in bin_schemes.items():
        devices_with_bins, labels = assign_bins(devices, edges)

        group_summary = summarize_groups(
            devices_with_bins=devices_with_bins,
            scheme_name=scheme_name,
            labels=labels,
        )

        bootstrap_summary = bootstrap_group_prediction_errors(
            devices_with_bins=devices_with_bins,
            scheme_name=scheme_name,
            labels=labels,
            rng=rng,
        )

        scheme_summary = summarize_scheme(
            group_summary=group_summary,
            bootstrap_summary=bootstrap_summary,
            scheme_name=scheme_name,
            labels=labels,
        )

        all_group_summaries.append(group_summary)
        all_bootstrap_summaries.append(bootstrap_summary)
        all_scheme_summaries.append(scheme_summary)

    group_summary = pd.concat(all_group_summaries, ignore_index=True)
    bootstrap_summary = pd.concat(all_bootstrap_summaries, ignore_index=True)
    bootstrap_by_size = summarize_bootstrap_by_sample_size(bootstrap_summary)
    scheme_summary = pd.DataFrame(all_scheme_summaries)

    scheme_summary = scheme_summary.sort_values("score_lower_is_better").reset_index(drop=True)

    group_summary.to_csv(output_dir / "cooling_kw_bin_sweep_groups.csv", index=False)
    bootstrap_summary.to_csv(output_dir / "cooling_kw_bin_sweep_bootstrap.csv", index=False)
    bootstrap_by_size.to_csv(output_dir / "cooling_kw_bin_sweep_bootstrap_by_sample_size.csv", index=False)
    scheme_summary.to_csv(output_dir / "cooling_kw_bin_sweep_summary.csv", index=False)

    print("\nTop bin schemes by score:")
    cols = [
        "scheme_name",
        "n_bins",
        "coverage_minimum_groups",
        "coverage_preferred_groups",
        "weighted_cv_peak_kw",
        "weighted_small_group_mape_percent",
        "p90_small_group_mape_percent",
        "score_lower_is_better",
    ]

    available_cols = [col for col in cols if col in scheme_summary.columns]
    print(scheme_summary[available_cols].head(10))

    best_scheme = scheme_summary.iloc[0]["scheme_name"]

    print("\nBest scheme:")
    print(best_scheme)

    print("\nBest scheme labels:")
    print(scheme_summary.iloc[0]["labels"])

    plot_summary_bar(
        summary=scheme_summary,
        value_col="score_lower_is_better",
        ylabel="Score, lower is better",
        title="Cooling kW-bin sweep score",
        filename="01_kw_bin_scheme_score.png",
    )

    plot_summary_bar(
        summary=scheme_summary,
        value_col="weighted_small_group_mape_percent",
        ylabel="Weighted small-group MAPE (%)",
        title="Small-transformer prediction error by kW-bin scheme",
        filename="02_kw_bin_scheme_small_group_mape.png",
    )

    plot_summary_bar(
        summary=scheme_summary,
        value_col="weighted_cv_peak_kw",
        ylabel="Weighted within-bin CV of peak kW",
        title="Within-bin peak-kW variation by bin scheme",
        filename="03_kw_bin_scheme_within_bin_cv.png",
    )

    plot_best_scheme_group_counts(group_summary, best_scheme)
    plot_best_scheme_mape_by_sample_size(bootstrap_by_size, best_scheme)
    plot_best_scheme_mape_by_group(bootstrap_summary, best_scheme)

    print("\nSaved outputs to:")
    print(output_dir)


if __name__ == "__main__":
    main()