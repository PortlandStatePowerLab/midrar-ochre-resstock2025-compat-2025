'''
Author: Midrar Adham
Created: Sat Jul 18 2026
'''
"""
Step 3: Build state-based diagnostics for each canonical HVAC device.

Inputs:
- canonical_hvac_devices.csv
- OCHRE simulation results under:
    ../load_profiles/cosimulation2/<building_id>/up00/simulation_results/ochre.csv

Output:
- canonical_hvac_device_diagnostics.csv

Purpose:
Add operational/state diagnostics to the canonical HVAC metadata table before
filtering and bin construction.

For each device, this script computes:
- duty_cycle
- total_on_minutes
- total_off_minutes
- number_of_on_events
- number_of_off_events
- number_of_switching_events
- mean/max ON-event duration
- total HVAC heating energy
- peak/average HVAC heating kW
- diagnostic flags useful for Step 4 filtering
"""

from pathlib import Path
import pandas as pd


# ----------------------------
# User settings
# ----------------------------

src_dir = Path("../load_profiles/cosimulation2")
upgrade = "up00"
results_dir = "simulation_results"

canonical_file = Path("canonical_hvac_devices.csv")
output_file = Path("canonical_hvac_device_diagnostics.csv")

ochre_csv_name = "ochre.csv"
hvac_power_col = "HVAC Heating Electric Power (kW)"

# One-minute OCHRE results.
dt_hours = 1 / 60

# Analyze the first day by default.
first_day_rows = 1440

# Main ON threshold chosen in earlier analysis.
on_threshold_kw = 0.3

# Diagnostic thresholds.
never_on_duty_threshold = 0.01
never_off_duty_threshold = 0.99
near_always_on_duty_threshold = 0.97
low_switching_threshold = 2


# ----------------------------
# Helpers
# ----------------------------

def read_first_day_power(building_id):
    """Read first-day HVAC heating power for one building."""
    ochre_csv = (
        src_dir
        / str(building_id)
        / upgrade
        / results_dir
        / ochre_csv_name
    )

    if not ochre_csv.is_file():
        return None, f"missing_ochre_csv: {ochre_csv}"

    try:
        df = pd.read_csv(ochre_csv)
    except Exception as e:
        return None, f"could_not_read_ochre_csv: {e}"

    if hvac_power_col not in df.columns:
        return None, f"missing_column: {hvac_power_col}"

    first_day = df.iloc[:first_day_rows].copy()

    if first_day.empty:
        return None, "empty_first_day"

    # power_kw = first_day[hvac_power_col].fillna(0).reset_index(drop=True)
    power_kw = first_day[hvac_power_col]
    
    if power_kw.isna().any():
        return None, "missing_power_samples"
    
    return power_kw, None


def get_binary_state(power_kw, threshold_kw=on_threshold_kw):
    """Return binary ON/OFF state from power using the ON threshold."""
    return power_kw > threshold_kw


def summarize_state(power_kw):
    """Compute state-based diagnostics from a power time series."""
    is_on = get_binary_state(power_kw)

    total_minutes = len(is_on)
    total_on_minutes = int(is_on.sum())
    total_off_minutes = int(total_minutes - total_on_minutes)

    duty_cycle = total_on_minutes / total_minutes if total_minutes > 0 else 0

    # Switching event count: number of state transitions.
    number_of_switching_events = int((is_on != is_on.shift(fill_value=is_on.iloc[0])).sum())

    # Contiguous ON/OFF blocks.
    block_id = (is_on != is_on.shift(fill_value=is_on.iloc[0])).cumsum()

    on_durations = []
    off_durations = []

    for _, idx in is_on.groupby(block_id).groups.items():
        idx = list(idx)
        block_state = bool(is_on.iloc[idx[0]])
        duration = len(idx)

        if block_state:
            on_durations.append(duration)
        else:
            off_durations.append(duration)

    number_of_on_events = len(on_durations)
    number_of_off_events = len(off_durations)

    mean_on_duration_minutes = (
        sum(on_durations) / len(on_durations)
        if on_durations
        else 0
    )
    max_on_duration_minutes = max(on_durations) if on_durations else 0

    mean_off_duration_minutes = (
        sum(off_durations) / len(off_durations)
        if off_durations
        else 0
    )
    max_off_duration_minutes = max(off_durations) if off_durations else 0

    total_energy_kwh = power_kw.sum() * dt_hours
    peak_kw = power_kw.max()
    avg_kw = power_kw.mean()

    return {
        "total_minutes": total_minutes,
        "total_on_minutes": total_on_minutes,
        "total_off_minutes": total_off_minutes,
        "duty_cycle": duty_cycle,
        "number_of_on_events": number_of_on_events,
        "number_of_off_events": number_of_off_events,
        "number_of_switching_events": number_of_switching_events,
        "mean_on_duration_minutes": mean_on_duration_minutes,
        "max_on_duration_minutes": max_on_duration_minutes,
        "mean_off_duration_minutes": mean_off_duration_minutes,
        "max_off_duration_minutes": max_off_duration_minutes,
        "total_energy_kwh": total_energy_kwh,
        "peak_kw": peak_kw,
        "avg_kw": avg_kw,
    }


def make_diagnostic_flag(row):
    """
    Assign one primary diagnostic flag.

    These are not final exclusions yet. Step 4 can decide how to use them.
    """
    if pd.isna(row.get("capacity_tons")) or row.get("capacity_tons", 0) <= 0:
        return "invalid_capacity"

    if row.get("read_status") != "ok":
        return row.get("read_status")

    duty = row.get("duty_cycle", 0)
    switches = row.get("number_of_switching_events", 0)

    if duty <= never_on_duty_threshold:
        return "near_never_on"

    if duty >= never_off_duty_threshold:
        return "near_never_off"

    if duty >= near_always_on_duty_threshold:
        return "near_always_on_qc"

    if switches < low_switching_threshold:
        return "low_switching_qc"

    return "normal"


# ----------------------------
# Main
# ----------------------------

def main():
    if not canonical_file.is_file():
        raise FileNotFoundError(
            f"Missing {canonical_file}. Run build_canonical_hvac_devices.py first."
        )

    canonical = pd.read_csv(canonical_file)
    canonical["building_id"] = canonical["building_id"].astype(str)

    rows = []

    for _, device in canonical.iterrows():
        building_id = device["building_id"]
        power_kw, error = read_first_day_power(building_id)

        base = device.to_dict()

        if error is not None:
            base.update({
                "read_status": error,
                "total_minutes": 0,
                "total_on_minutes": 0,
                "total_off_minutes": 0,
                "duty_cycle": None,
                "number_of_on_events": 0,
                "number_of_off_events": 0,
                "number_of_switching_events": 0,
                "mean_on_duration_minutes": 0,
                "max_on_duration_minutes": 0,
                "mean_off_duration_minutes": 0,
                "max_off_duration_minutes": 0,
                "total_energy_kwh": None,
                "peak_kw": None,
                "avg_kw": None,
            })
        else:
            base.update({"read_status": "ok"})
            base.update(summarize_state(power_kw))

        rows.append(base)

    diagnostics = pd.DataFrame(rows)

    diagnostics["diagnostic_flag"] = diagnostics.apply(make_diagnostic_flag, axis=1)

    diagnostics["include_candidate_step4"] = (
        (diagnostics["diagnostic_flag"] == "normal")
        & diagnostics["technology"].isin(["electric_resistance", "heat_pump"])
        & diagnostics["capacity_tons"].notna()
        & (diagnostics["capacity_tons"] > 0)
    )

    diagnostics.to_csv(output_file, index=False)

    print(f"Saved: {output_file}")
    print("\nRows:", len(diagnostics))
    print("Unique devices:", diagnostics["device_filename"].nunique())
    print("Unique buildings:", diagnostics["building_id"].nunique())

    print("\nRead status counts:")
    print(diagnostics["read_status"].value_counts(dropna=False))

    print("\nDiagnostic flag counts:")
    print(diagnostics["diagnostic_flag"].value_counts(dropna=False))

    print("\nInclude candidate counts:")
    print(diagnostics["include_candidate_step4"].value_counts(dropna=False))

    print("\nDuty-cycle summary by technology:")
    print(diagnostics.groupby("technology")["duty_cycle"].describe())

    print("\nSwitching-event summary by technology:")
    print(diagnostics.groupby("technology")["number_of_switching_events"].describe())

    print("\nPreview:")
    preview_cols = [
        "device_filename",
        "building_id",
        "technology",
        "capacity_tons",
        "metadata_reference_estimated_electric_kw",
        "duty_cycle",
        "number_of_on_events",
        "number_of_switching_events",
        "total_energy_kwh",
        "peak_kw",
        "diagnostic_flag",
        "include_candidate_step4",
    ]
    print(diagnostics[preview_cols].head(20))


if __name__ == "__main__":
    main()

