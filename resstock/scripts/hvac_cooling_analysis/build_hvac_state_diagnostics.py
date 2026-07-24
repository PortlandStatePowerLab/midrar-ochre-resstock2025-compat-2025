'''
Author: Midrar Adham
Created: Thu Jul 23 2026
'''
"""
03_build_hvac_state_diagnostics.py

Build month-long HVAC state diagnostics from OCHRE Parquet results.

This script reads:

- outputs/ochre_result_inventory.csv
- outputs/canonical_electric_hvac_devices.csv

Then it reads each available OCHRE time-series file:

- simulation_results/ochre.parquet

and computes heating and cooling state diagnostics using a simple ON/OFF
threshold.

Output:

outputs/hvac_state_diagnostics.csv

Important:
This script does not modify any simulation files.
"""

from pathlib import Path
import pandas as pd


# ---------------------------------------------------------------------------
# User settings
# ---------------------------------------------------------------------------
# Rule: keep variable names lowercase.

analysis_dir = Path("./outputs/")

inventory_file = analysis_dir / "ochre_result_inventory.csv"
canonical_file = analysis_dir / "canonical_electric_hvac_devices.csv"
output_file = analysis_dir / "hvac_state_diagnostics.csv"

upgrades = ["up00", "up01", "up02"]

heating_power_col = "HVAC Heating Electric Power (kW)"
cooling_power_col = "HVAC Cooling Electric Power (kW)"

service_power_cols = {
    "heating": heating_power_col,
    "cooling": cooling_power_col,
}

on_threshold_kw = 0.3
time_resolution_minutes = 1
time_resolution_hours = time_resolution_minutes / 60

# Your current August run saved 30 days of one-minute results.
expected_rows = 30 * 24 * 60

near_never_on_duty_threshold = 0.01
near_never_off_duty_threshold = 0.99
near_always_on_duty_threshold = 0.97
low_switching_threshold = 2


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

def normalize_text(value):
    """
    Normalize text for comparisons.
    """
    if pd.isna(value):
        return ""

    return str(value).strip().lower()


def read_timeseries(timeseries_file, power_col):
    """
    Read only the power column needed for one service.

    The scanner already stored the preferred time-series path. In your current
    workflow this should be ochre.parquet, but CSV is supported as a fallback.
    """
    timeseries_path = Path(timeseries_file)

    if not timeseries_path.is_file():
        raise FileNotFoundError(f"Missing time-series file: {timeseries_path}")

    if timeseries_path.suffix.lower() == ".parquet":
        return pd.read_parquet(timeseries_path, columns=[power_col])

    if timeseries_path.suffix.lower() == ".csv":
        return pd.read_csv(timeseries_path, usecols=[power_col])

    raise ValueError(f"Unsupported time-series format: {timeseries_path}")


def count_events(is_on):
    """
    Count ON events, OFF events, and switching events.

    An ON event is a contiguous period where the HVAC power is above threshold.
    An OFF event is a contiguous period where the HVAC power is at or below
    threshold.
    """
    if len(is_on) == 0:
        return 0, 0, 0, [], []

    switches = is_on.iloc[1:].to_numpy() != is_on.iloc[:-1].to_numpy()
    n_switching_events = int(switches.sum())

    event_id = switches.cumsum()
    event_id = pd.Series([0] + list(event_id), index=is_on.index)

    event_lengths = is_on.groupby(event_id).size()
    event_states = is_on.groupby(event_id).first()

    on_durations = event_lengths[event_states == True].tolist()
    off_durations = event_lengths[event_states == False].tolist()

    n_on_events = len(on_durations)
    n_off_events = len(off_durations)

    return n_on_events, n_off_events, n_switching_events, on_durations, off_durations


def mean_or_zero(values):
    """
    Return the mean of a list, or zero if the list is empty.
    """
    if len(values) == 0:
        return 0.0

    return float(sum(values) / len(values))


def max_or_zero(values):
    """
    Return the max of a list, or zero if the list is empty.
    """
    if len(values) == 0:
        return 0.0

    return float(max(values))


def diagnostic_flag(row):
    """
    Assign a simple diagnostic flag.

    These flags are not permanent exclusions. They are meant to help us decide
    what to inspect before plotting, binning, and OLS.
    """
    if row["read_status"] != "ok":
        return row["read_status"]

    if row["n_rows"] == 0:
        return "empty_timeseries"

    if row["duty_cycle"] <= near_never_on_duty_threshold:
        return "near_never_on"

    if row["duty_cycle"] >= near_never_off_duty_threshold:
        return "near_never_off"

    if row["duty_cycle"] >= near_always_on_duty_threshold:
        return "near_always_on_qc"

    if row["n_switching_events"] < low_switching_threshold:
        return "low_switching_qc"

    return "normal"


def summarize_power(power_series):
    """
    Compute state diagnostics for one building, one upgrade, and one service.
    """
    power_kw = pd.to_numeric(power_series, errors="coerce").fillna(0.0)

    # Negative HVAC power is not physically meaningful for these state flags.
    # Clipping protects the event logic from tiny negative numerical artifacts.
    power_kw = power_kw.clip(lower=0.0)

    is_on = power_kw > on_threshold_kw

    n_rows = len(power_kw)
    total_minutes = n_rows * time_resolution_minutes
    total_hours = n_rows * time_resolution_hours

    total_on_minutes = int(is_on.sum() * time_resolution_minutes)
    total_off_minutes = int(total_minutes - total_on_minutes)

    duty_cycle = total_on_minutes / total_minutes if total_minutes > 0 else 0.0

    n_on_events, n_off_events, n_switching_events, on_durations, off_durations = count_events(is_on)

    total_energy_kwh = float(power_kw.sum() * time_resolution_hours)
    avg_kw = float(power_kw.mean()) if n_rows > 0 else 0.0
    peak_kw = float(power_kw.max()) if n_rows > 0 else 0.0

    return {
        "n_rows": n_rows,
        "total_minutes": total_minutes,
        "total_hours": total_hours,
        "total_on_minutes": total_on_minutes,
        "total_off_minutes": total_off_minutes,
        "duty_cycle": duty_cycle,
        "n_on_events": n_on_events,
        "n_off_events": n_off_events,
        "n_switching_events": n_switching_events,
        "mean_on_duration_minutes": mean_or_zero(on_durations),
        "max_on_duration_minutes": max_or_zero(on_durations),
        "mean_off_duration_minutes": mean_or_zero(off_durations),
        "max_off_duration_minutes": max_or_zero(off_durations),
        "total_energy_kwh": total_energy_kwh,
        "avg_kw": avg_kw,
        "peak_kw": peak_kw,
    }


def service_has_metadata(canonical_subset, service):
    """
    Check whether the canonical metadata table says this building has a device
    that can provide this service.
    """
    if len(canonical_subset) == 0:
        return False

    service_types = canonical_subset["service_type"].fillna("").str.lower()

    if service == "heating":
        return service_types.isin(["heating", "heating_and_cooling"]).any()

    if service == "cooling":
        return service_types.isin(["cooling", "heating_and_cooling"]).any()

    return False


def representative_device_info(canonical_subset, service):
    """
    Pull useful device metadata for the diagnostics row.

    If more than one matching device exists, this currently keeps the first one.
    That is okay for the first diagnostics pass. We can refine this later if
    some homes have multiple HVAC systems.
    """
    if len(canonical_subset) == 0:
        return {}

    service_types = canonical_subset["service_type"].fillna("").str.lower()

    if service == "heating":
        matching = canonical_subset[
            service_types.isin(["heating", "heating_and_cooling"])
        ].copy()
    elif service == "cooling":
        matching = canonical_subset[
            service_types.isin(["cooling", "heating_and_cooling"])
        ].copy()
    else:
        matching = canonical_subset.copy()

    if len(matching) == 0:
        return {}

    item = matching.iloc[0]

    return {
        "element_type": item.get("element_type"),
        "equipment_type": item.get("equipment_type"),
        "fuel": item.get("fuel"),
        "service_type_from_metadata": item.get("service_type"),
        "device_type": item.get("device_type"),
        "analysis_class": item.get("analysis_class"),
        "heating_capacity_tons": item.get("heating_capacity_tons"),
        "cooling_capacity_tons": item.get("cooling_capacity_tons"),
        "representative_capacity_kw_thermal": item.get("representative_capacity_kw_thermal"),
        "backup_fuel": item.get("backup_fuel"),
        "backup_system_type": item.get("backup_system_type"),
        "backup_heating_capacity_tons": item.get("backup_heating_capacity_tons"),
        "compressor_type": item.get("compressor_type"),
    }


def build_one_diagnostic_row(inventory_row, canonical_subset, service):
    """
    Build one diagnostic row for one building-upgrade-service combination.
    """
    building_id = str(inventory_row["building_id"])
    upgrade = str(inventory_row["upgrade"])
    power_col = service_power_cols[service]

    has_metadata_device = service_has_metadata(canonical_subset, service)
    has_power_col = bool(inventory_row[f"has_{service}_col"])

    base_row = {
        "building_id": building_id,
        "upgrade": upgrade,
        "service": service,
        "power_col": power_col,
        "timeseries_file": inventory_row.get("timeseries_file"),
        "timeseries_format": inventory_row.get("timeseries_format"),
        "has_timeseries_file": bool(inventory_row.get("has_timeseries_file")),
        "has_power_col": has_power_col,
        "has_metadata_device": has_metadata_device,
        "expected_rows": expected_rows,
        "on_threshold_kw": on_threshold_kw,
    }

    base_row.update(representative_device_info(canonical_subset, service))

    if not base_row["has_timeseries_file"]:
        base_row.update({
            "read_status": "missing_timeseries_file",
            "read_error": None,
        })
        return base_row

    if not has_power_col:
        base_row.update({
            "read_status": "missing_power_column",
            "read_error": None,
        })
        return base_row

    try:
        timeseries = read_timeseries(inventory_row["timeseries_file"], power_col)
        summary = summarize_power(timeseries[power_col])
        base_row.update(summary)
        base_row.update({
            "read_status": "ok",
            "read_error": None,
        })

    except Exception as error:
        base_row.update({
            "read_status": "timeseries_read_error",
            "read_error": str(error),
        })

    return base_row


def add_inclusion_flags(diagnostics):
    """
    Add separate inclusion flags for different analysis purposes.

    The difference matters:

    include_in_device_population:
        Use this to count electric HVAC devices that exist and have complete
        time-series output, even if they barely operated in August.

    include_in_active_operation_plots:
        Use this for duty-cycle, cycling, event, energy, and OLS-oriented plots.
        This excludes near-never-on devices because their event statistics are
        mostly zeros and can dominate the visual interpretation.

    include_in_ols_candidate_pool:
        A stricter first-pass flag for possible OLS/binning use. This keeps only
        normal rows with enough switching behavior.
    """
    diagnostics["is_complete_month"] = (
        (diagnostics["read_status"] == "ok")
        & (diagnostics["n_rows"] >= expected_rows)
    )

    diagnostics["include_in_device_population"] = (
        (diagnostics["read_status"] == "ok")
        & (diagnostics["has_metadata_device"] == True)
        & (diagnostics["has_power_col"] == True)
        & (diagnostics["is_complete_month"] == True)
    )

    diagnostics["include_in_active_operation_plots"] = (
        (diagnostics["include_in_device_population"] == True)
        & (~diagnostics["diagnostic_flag"].isin([
            "near_never_on",
            "empty_timeseries",
            "missing_timeseries_file",
            "missing_power_column",
            "timeseries_read_error",
        ]))
    )

    diagnostics["include_in_ols_candidate_pool"] = (
        (diagnostics["include_in_device_population"] == True)
        & (diagnostics["diagnostic_flag"] == "normal")
    )

    # Backward-compatible alias for earlier plotting code. From now on, prefer
    # the more explicit flag names above.
    diagnostics["include_in_plotting"] = diagnostics["include_in_active_operation_plots"]

    return diagnostics


# ---------------------------------------------------------------------------
# Main script
# ---------------------------------------------------------------------------

def main():
    """
    Build diagnostics for heating and cooling across all selected upgrades.
    """
    if not inventory_file.is_file():
        raise FileNotFoundError(
            f"inventory_file does not exist: {inventory_file}\n"
            "Run 01_scan_ochre_results.py first."
        )

    if not canonical_file.is_file():
        raise FileNotFoundError(
            f"canonical_file does not exist: {canonical_file}\n"
            "Run 02b_build_canonical_electric_hvac_devices.py first."
        )

    inventory = pd.read_csv(inventory_file)
    canonical = pd.read_csv(canonical_file)

    inventory = inventory[inventory["upgrade"].isin(upgrades)].copy()
    canonical = canonical[canonical["upgrade"].isin(upgrades)].copy()

    rows = []

    for _, inventory_row in inventory.iterrows():
        building_id = str(inventory_row["building_id"])
        upgrade = str(inventory_row["upgrade"])

        canonical_subset = canonical[
            (canonical["building_id"].astype(str) == building_id)
            & (canonical["upgrade"].astype(str) == upgrade)
        ].copy()

        for service in ["heating", "cooling"]:
            rows.append(build_one_diagnostic_row(inventory_row, canonical_subset, service))

    diagnostics = pd.DataFrame(rows)

    numeric_defaults = {
        "n_rows": 0,
        "total_minutes": 0,
        "total_hours": 0,
        "total_on_minutes": 0,
        "total_off_minutes": 0,
        "duty_cycle": 0.0,
        "n_on_events": 0,
        "n_off_events": 0,
        "n_switching_events": 0,
        "mean_on_duration_minutes": 0.0,
        "max_on_duration_minutes": 0.0,
        "mean_off_duration_minutes": 0.0,
        "max_off_duration_minutes": 0.0,
        "total_energy_kwh": 0.0,
        "avg_kw": 0.0,
        "peak_kw": 0.0,
    }

    for col, default in numeric_defaults.items():
        if col not in diagnostics.columns:
            diagnostics[col] = default

        diagnostics[col] = diagnostics[col].fillna(default)

    diagnostics["diagnostic_flag"] = diagnostics.apply(diagnostic_flag, axis=1)
    diagnostics = add_inclusion_flags(diagnostics)

    diagnostics.to_csv(output_file, index=False)

    print("\nSaved HVAC state diagnostics:")
    print(output_file)

    print("\nTotal diagnostic rows:")
    print(len(diagnostics))

    print("\nRows by upgrade and service:")
    print(
        diagnostics
        .groupby(["upgrade", "service"])
        .size()
        .unstack(fill_value=0)
    )

    print("\nRead status by upgrade and service:")
    print(
        diagnostics
        .groupby(["upgrade", "service", "read_status"])
        .size()
        .unstack(fill_value=0)
    )

    print("\nDiagnostic flags by upgrade and service:")
    print(
        diagnostics
        .groupby(["upgrade", "service", "diagnostic_flag"])
        .size()
        .unstack(fill_value=0)
    )

    print("\nDevice population rows by upgrade and service:")
    print(
        diagnostics
        .groupby(["upgrade", "service"])["include_in_device_population"]
        .sum()
        .unstack(fill_value=0)
    )

    print("\nActive operation plot rows by upgrade and service:")
    print(
        diagnostics
        .groupby(["upgrade", "service"])["include_in_active_operation_plots"]
        .sum()
        .unstack(fill_value=0)
    )

    print("\nOLS candidate rows by upgrade and service:")
    print(
        diagnostics
        .groupby(["upgrade", "service"])["include_in_ols_candidate_pool"]
        .sum()
        .unstack(fill_value=0)
    )

    print("\nEnergy and peak summaries for active operation rows:")
    active = diagnostics[diagnostics["include_in_active_operation_plots"] == True].copy()
    if len(active) > 0:
        print(
            active
            .groupby(["upgrade", "service"])
            [["total_energy_kwh", "peak_kw", "duty_cycle", "n_switching_events"]]
            .describe()
        )
    else:
        print("No active operation rows yet.")

    print("\nPreview:")
    preview_cols = [
        "building_id",
        "upgrade",
        "service",
        "device_type",
        "fuel",
        "has_metadata_device",
        "has_power_col",
        "read_status",
        "n_rows",
        "duty_cycle",
        "n_on_events",
        "n_switching_events",
        "total_energy_kwh",
        "peak_kw",
        "diagnostic_flag",
        "include_in_device_population",
        "include_in_active_operation_plots",
        "include_in_ols_candidate_pool",
    ]
    available_preview_cols = [col for col in preview_cols if col in diagnostics.columns]
    print(diagnostics[available_preview_cols].head(30))


if __name__ == "__main__":
    main()