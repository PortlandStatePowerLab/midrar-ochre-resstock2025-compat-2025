'''
Author: MidrarAdham
Created: Fri Jul 24 2026
'''
"""
06_build_daily_cooling_metrics.py

Build daily cooling HVAC metrics from OCHRE Parquet results.

This script reads:

- outputs/hvac_state_diagnostics.csv

Then it reads each active cooling device's OCHRE time-series file and splits
the 30-day August simulation into daily chunks.

Output:

- outputs/daily_cooling_metrics.csv
- outputs/daily_cooling_metric_failures.csv

Important:
This script does not modify any simulation files.
"""

from pathlib import Path
import pandas as pd


# ---------------------------------------------------------------------------
# User settings
# ---------------------------------------------------------------------------
# Rule: keep variable names lowercase.

analysis_dir = Path("./outputs")

diagnostics_file = analysis_dir / "hvac_state_diagnostics.csv"
output_file = analysis_dir / "daily_cooling_metrics.csv"
failure_file = analysis_dir / "daily_cooling_metric_failures.csv"

upgrades = ["up00", "up01", "up02"]

cooling_power_col = "HVAC Cooling Electric Power (kW)"
service = "cooling"

active_operation_flag = "include_in_active_operation_plots"

on_threshold_kw = 0.3
time_resolution_minutes = 1
time_resolution_hours = time_resolution_minutes / 60

minutes_per_day = 24 * 60
expected_days = 30
expected_rows = expected_days * minutes_per_day


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

def normalize_bool(series):
    """
    Convert boolean-like values to real booleans.

    This protects the script from CSV columns that were saved as strings such
    as "True", "False", "true", or "false".
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


def read_cooling_power(timeseries_file):
    """
    Read only the cooling power column from the OCHRE time-series file.

    Your current workflow uses ochre.parquet. CSV is supported as a fallback.
    """
    timeseries_path = Path(timeseries_file)

    if not timeseries_path.is_file():
        raise FileNotFoundError(f"Missing time-series file: {timeseries_path}")

    if timeseries_path.suffix.lower() == ".parquet":
        data = pd.read_parquet(timeseries_path, columns=[cooling_power_col])

    elif timeseries_path.suffix.lower() == ".csv":
        data = pd.read_csv(timeseries_path, usecols=[cooling_power_col])

    else:
        raise ValueError(f"Unsupported time-series format: {timeseries_path}")

    power_kw = pd.to_numeric(data[cooling_power_col], errors="coerce").fillna(0.0)
    power_kw = power_kw.clip(lower=0.0)

    return power_kw


def count_switching_events(is_on):
    """
    Count state changes between adjacent time steps.

    A switch is either:
    - OFF to ON
    - ON to OFF
    """
    if len(is_on) <= 1:
        return 0

    switches = is_on.iloc[1:].to_numpy() != is_on.iloc[:-1].to_numpy()

    return int(switches.sum())


def summarize_daily_power(power_kw, day_index, row):
    """
    Compute daily cooling metrics for one building, one upgrade, and one day.
    """
    start = day_index * minutes_per_day
    end = start + minutes_per_day

    daily_power_kw = power_kw.iloc[start:end].copy()
    daily_power_kw = daily_power_kw.reset_index(drop=True)

    is_on = daily_power_kw > on_threshold_kw

    n_rows = len(daily_power_kw)
    daily_minutes = n_rows * time_resolution_minutes
    daily_hours = n_rows * time_resolution_hours

    daily_on_minutes = int(is_on.sum() * time_resolution_minutes)
    daily_off_minutes = int(daily_minutes - daily_on_minutes)

    daily_duty_cycle = daily_on_minutes / daily_minutes if daily_minutes > 0 else 0.0

    daily_energy_kwh = float(daily_power_kw.sum() * time_resolution_hours)
    daily_peak_kw = float(daily_power_kw.max()) if n_rows > 0 else 0.0
    daily_avg_kw = float(daily_power_kw.mean()) if n_rows > 0 else 0.0

    daily_switching_events = count_switching_events(is_on)

    cooling_capacity_tons = row.get("cooling_capacity_tons")
    if pd.notna(cooling_capacity_tons) and float(cooling_capacity_tons) > 0:
        cooling_capacity_tons = float(cooling_capacity_tons)
        daily_peak_kw_per_ton = daily_peak_kw / cooling_capacity_tons
        daily_kwh_per_ton = daily_energy_kwh / cooling_capacity_tons
    else:
        cooling_capacity_tons = None
        daily_peak_kw_per_ton = None
        daily_kwh_per_ton = None

    daily_on_hours = daily_on_minutes / 60
    if daily_on_hours > 0:
        daily_switching_events_per_on_hour = daily_switching_events / daily_on_hours
    else:
        daily_switching_events_per_on_hour = None

    return {
        "building_id": str(row["building_id"]),
        "upgrade": row["upgrade"],
        "service": service,
        "day_index": day_index + 1,
        "day_start_row": start,
        "day_end_row_exclusive": end,
        "n_rows": n_rows,
        "cooling_capacity_tons": cooling_capacity_tons,
        "device_type": row.get("device_type"),
        "equipment_type": row.get("equipment_type"),
        "daily_energy_kwh": daily_energy_kwh,
        "daily_peak_kw": daily_peak_kw,
        "daily_avg_kw": daily_avg_kw,
        "daily_on_minutes": daily_on_minutes,
        "daily_off_minutes": daily_off_minutes,
        "daily_duty_cycle": daily_duty_cycle,
        "daily_switching_events": daily_switching_events,
        "daily_peak_kw_per_ton": daily_peak_kw_per_ton,
        "daily_kwh_per_ton": daily_kwh_per_ton,
        "daily_switching_events_per_on_hour": daily_switching_events_per_on_hour,
        "on_threshold_kw": on_threshold_kw,
        "timeseries_file": row.get("timeseries_file"),
    }


def build_daily_rows_for_device(row):
    """
    Build daily metrics for one active cooling device.
    """
    power_kw = read_cooling_power(row["timeseries_file"])

    available_days = len(power_kw) // minutes_per_day
    n_days = min(available_days, expected_days)

    rows = []

    for day_index in range(n_days):
        rows.append(summarize_daily_power(power_kw, day_index, row))

    return rows


def assign_daily_activity_flag(row):
    """
    Label whether the device had meaningful cooling operation on that day.
    """
    if row["daily_duty_cycle"] <= 0:
        return "off_all_day"

    if row["daily_duty_cycle"] <= 0.01:
        return "near_never_on_day"

    if row["daily_duty_cycle"] >= 0.99:
        return "near_always_on_day"

    return "active_day"


def print_filter_debug(diagnostics):
    """
    Print filter counts so empty outputs are easy to diagnose.
    """
    print("\nDiagnostics file:")
    print(diagnostics_file)

    print("\nTotal diagnostics rows:")
    print(len(diagnostics))

    print("\nColumns available:")
    print(list(diagnostics.columns))

    print("\nRows by service:")
    print(diagnostics["service"].value_counts(dropna=False))

    print("\nRows by upgrade:")
    print(diagnostics["upgrade"].value_counts(dropna=False).sort_index())

    print("\nActive operation flag values:")
    print(diagnostics[active_operation_flag].value_counts(dropna=False))

    cooling_all = diagnostics[
        (diagnostics["service"] == service)
        & (diagnostics["upgrade"].isin(upgrades))
    ].copy()

    print("\nCooling rows before active filter:")
    print(len(cooling_all))

    if len(cooling_all) > 0:
        print("\nCooling active flag values:")
        print(cooling_all[active_operation_flag].value_counts(dropna=False))

        print("\nCooling rows by read_status:")
        print(cooling_all["read_status"].value_counts(dropna=False))

        print("\nCooling rows by diagnostic_flag:")
        print(cooling_all["diagnostic_flag"].value_counts(dropna=False))


# ---------------------------------------------------------------------------
# Main script
# ---------------------------------------------------------------------------

def main():
    """
    Build daily cooling metrics for all active cooling devices.
    """
    if not diagnostics_file.is_file():
        raise FileNotFoundError(
            f"diagnostics_file does not exist: {diagnostics_file}\\n"
            "Check analysis_dir at the top of this script."
        )

    diagnostics = pd.read_csv(diagnostics_file)

    if active_operation_flag not in diagnostics.columns:
        raise KeyError(
            f"Missing required column: {active_operation_flag}\\n"
            "Run the updated 03_build_hvac_state_diagnostics.py first."
        )

    print_filter_debug(diagnostics)

    diagnostics[active_operation_flag] = normalize_bool(diagnostics[active_operation_flag])

    cooling = diagnostics[
        (diagnostics["service"] == service)
        & (diagnostics["upgrade"].isin(upgrades))
        & (diagnostics[active_operation_flag] == True)
    ].copy()

    cooling["cooling_capacity_tons"] = pd.to_numeric(
        cooling["cooling_capacity_tons"],
        errors="coerce",
    )

    cooling = cooling.dropna(subset=["timeseries_file"]).copy()

    print("\nActive cooling devices to process:")
    print(len(cooling))

    if len(cooling) == 0:
        print(
            "\nNo active cooling devices were selected. Most likely causes are:\\n"
            "1. The script is reading the wrong hvac_state_diagnostics.csv file.\\n"
            "2. The include_in_active_operation_plots column is not True for cooling rows.\\n"
            "3. The service labels are not exactly 'cooling'.\\n"
            "Check the debug tables printed above."
        )
        empty = pd.DataFrame()
        output_file.parent.mkdir(parents=True, exist_ok=True)
        empty.to_csv(output_file, index=False)
        empty.to_csv(failure_file, index=False)
        return

    print("\nDevices by upgrade:")
    print(cooling["upgrade"].value_counts().sort_index())

    rows = []
    failures = []

    for index, row in cooling.iterrows():
        try:
            rows.extend(build_daily_rows_for_device(row))

        except Exception as error:
            failures.append({
                "building_id": str(row["building_id"]),
                "upgrade": row["upgrade"],
                "timeseries_file": row.get("timeseries_file"),
                "error": str(error),
            })

    daily_metrics = pd.DataFrame(rows)

    if len(daily_metrics) > 0:
        daily_metrics["daily_activity_flag"] = daily_metrics.apply(
            assign_daily_activity_flag,
            axis=1,
        )

    output_file.parent.mkdir(parents=True, exist_ok=True)
    daily_metrics.to_csv(output_file, index=False)

    pd.DataFrame(failures).to_csv(failure_file, index=False)

    print("\nSaved daily cooling metrics:")
    print(output_file)

    print("\nSaved failures:")
    print(failure_file)

    print("\nTotal daily rows:")
    print(len(daily_metrics))

    print("\nFailures:")
    print(len(failures))

    if len(daily_metrics) > 0:
        print("\nDaily rows by upgrade:")
        print(daily_metrics["upgrade"].value_counts().sort_index())

        print("\nDaily activity flags by upgrade:")
        print(
            daily_metrics
            .groupby(["upgrade", "daily_activity_flag"])
            .size()
            .unstack(fill_value=0)
        )

        print("\nDaily metric summary by upgrade:")
        print(
            daily_metrics
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
            .describe()
        )

        print("\nPreview:")
        preview_cols = [
            "building_id",
            "upgrade",
            "day_index",
            "cooling_capacity_tons",
            "daily_energy_kwh",
            "daily_peak_kw",
            "daily_duty_cycle",
            "daily_switching_events",
            "daily_peak_kw_per_ton",
            "daily_kwh_per_ton",
            "daily_activity_flag",
        ]
        print(daily_metrics[preview_cols].head(30))

    if len(failures) > 0:
        print("\nFailure preview:")
        print(pd.DataFrame(failures).head(20))


if __name__ == "__main__":
    main()