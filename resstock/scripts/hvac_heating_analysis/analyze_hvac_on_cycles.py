"""
Analyze HVAC ON-cycle events from OCHRE simulation results.

Outputs:
- hvac_on_events_first_day.csv
- hvac_daily_cycle_summary_first_day.csv
- hvac_event_duration_distribution.png
- hvac_event_energy_distribution.png
- hvac_duty_cycle_by_category.png
"""

import json
import numpy as np
import pandas as pd
from pathlib import Path
import matplotlib.pyplot as plt

SRC_DIR = Path("../load_profiles/cosimulation2")
UPGRADE = "up00"
RESULTS_FOLDER = "simulation_results"

OCHRE_CSV_NAME = "ochre.csv"
OCHRE_JSON_NAME = "ochre.json"

HVAC_POWER_COL = "HVAC Heating Electric Power (kW)"

# Treat HVAC as ON only when power is larger than this threshold.
ON_THRESHOLD_KW = 0.3

# One-minute resolution.
DT_HOURS = 1 / 60

# First day only.
FIRST_DAY_ROWS = 1440


def watts_to_tons(capacity_w):
    """Convert heating capacity from W thermal to tons."""
    if capacity_w is None:
        return None
    return float(capacity_w) / 3516.85


def read_ochre_json(input_dir):
    """Read OCHRE static model output."""
    candidates = [
        input_dir / RESULTS_FOLDER / OCHRE_JSON_NAME,
        input_dir / OCHRE_JSON_NAME,
    ]

    for json_path in candidates:
        if json_path.is_file():
            with open(json_path, "r") as f:
                return json.load(f)

    return None


def get_hvac_static_info(input_dir):
    """Extract HVAC equipment info from ochre.json."""
    data = read_ochre_json(input_dir)

    if data is None:
        return None

    hvac = data.get("Equipment", {}).get("HVAC Heating", {})

    if not hvac:
        return None

    equipment_name = hvac.get("Equipment Name", "N/A")
    fuel = hvac.get("Fuel", "N/A")

    capacity_w = hvac.get("Capacity (W)")
    backup_capacity_w = hvac.get("Backup Capacity (W)")
    rated_aux_power_w = hvac.get("Rated Auxiliary Power (W)")
    eir = hvac.get("EIR (-)")
    backup_eir = hvac.get("Backup EIR (-)")
    rated_efficiency = hvac.get("Rated Efficiency")

    name_lower = str(equipment_name).lower()
    fuel_lower = str(fuel).lower()

    if "heat pump" in name_lower or "air-to-air" in name_lower:
        category = "heat_pump"
    elif fuel_lower == "electricity":
        category = "electric_resistance"
    else:
        category = "other"

    return {
        "category": category,
        "equipment_name": equipment_name,
        "fuel": fuel,
        "capacity_w": capacity_w,
        "tons": watts_to_tons(capacity_w),
        "eir": eir,
        "rated_efficiency": rated_efficiency,
        "rated_aux_power_w": rated_aux_power_w,
        "backup_capacity_w": backup_capacity_w,
        "backup_capacity_kw": None if backup_capacity_w is None else backup_capacity_w / 1000,
        "backup_eir": backup_eir,
        "hp_lockout_c": hvac.get("Heat Pump Lockout Temperature (C)"),
        "backup_lockout_c": hvac.get("Backup Lockout Temperature (C)"),
    }


def find_on_events(power_kw, on_threshold_kw=ON_THRESHOLD_KW):
    """Detect contiguous ON events from a power time series."""
    power_kw = power_kw.fillna(0).reset_index(drop=True)
    is_on = power_kw > on_threshold_kw

    # New block whenever ON/OFF state changes.
    block_id = (is_on != is_on.shift(fill_value=False)).cumsum()

    events = []

    for _, idx in is_on.groupby(block_id).groups.items():
        idx = list(idx)

        if not bool(is_on.iloc[idx[0]]):
            continue

        event_power = power_kw.iloc[idx]

        events.append({
            "start_index": idx[0],
            "end_index": idx[-1],
            "duration_minutes": len(idx),
            "energy_kwh": event_power.sum() * DT_HOURS,
            "avg_kw": event_power.mean(),
            "peak_kw": event_power.max(),
        })

    return events


event_rows = []
summary_rows = []

for building_dir in SRC_DIR.iterdir():
    if not building_dir.is_dir():
        continue

    building_id = building_dir.name
    input_dir = building_dir / UPGRADE
    sim_dir = input_dir / RESULTS_FOLDER
    ochre_csv = sim_dir / OCHRE_CSV_NAME

    if not ochre_csv.is_file():
        print(f"Missing ochre.csv: {building_id}")
        continue

    hvac_info = get_hvac_static_info(input_dir)

    if hvac_info is None:
        print(f"Missing/invalid ochre.json HVAC info: {building_id}")
        continue

    try:
        df = pd.read_csv(ochre_csv)
    except Exception as e:
        print(f"Could not read ochre.csv for {building_id}: {e}")
        continue

    if HVAC_POWER_COL not in df.columns:
        print(f"Missing HVAC power column for {building_id}")
        continue

    first_day = df.iloc[:FIRST_DAY_ROWS].copy()

    if len(first_day) == 0:
        continue

    power_kw = first_day[HVAC_POWER_COL].fillna(0)
    events = find_on_events(power_kw, ON_THRESHOLD_KW)

    for event_id, event in enumerate(events, start=1):
        event_rows.append({
            "building_id": building_id,
            "event_id": event_id,
            "category": hvac_info["category"],
            "equipment_name": hvac_info["equipment_name"],
            "tons": hvac_info["tons"],
            "capacity_w": hvac_info["capacity_w"],
            "capacity_kw_thermal": None if hvac_info["capacity_w"] is None else hvac_info["capacity_w"] / 1000,
            "eir": hvac_info["eir"],
            "rated_efficiency": hvac_info["rated_efficiency"],
            "backup_capacity_kw": hvac_info["backup_capacity_kw"],
            "backup_eir": hvac_info["backup_eir"],
            **event,
        })

    total_minutes = len(first_day)
    total_on_minutes = sum(e["duration_minutes"] for e in events)
    total_energy_kwh = power_kw.sum() * DT_HOURS
    peak_kw = power_kw.max()
    avg_kw = power_kw.mean()
    duty_cycle = total_on_minutes / total_minutes if total_minutes > 0 else 0

    if events:
        event_energy_values = [e["energy_kwh"] for e in events]
        event_duration_values = [e["duration_minutes"] for e in events]
        event_peak_values = [e["peak_kw"] for e in events]

        avg_event_energy_kwh = sum(event_energy_values) / len(event_energy_values)
        max_event_energy_kwh = max(event_energy_values)
        avg_event_duration_minutes = sum(event_duration_values) / len(event_duration_values)
        max_event_duration_minutes = max(event_duration_values)
        avg_event_peak_kw = sum(event_peak_values) / len(event_peak_values)
        max_event_peak_kw = max(event_peak_values)
    else:
        avg_event_energy_kwh = 0
        max_event_energy_kwh = 0
        avg_event_duration_minutes = 0
        max_event_duration_minutes = 0
        avg_event_peak_kw = 0
        max_event_peak_kw = 0

    summary_rows.append({
        "building_id": building_id,
        "category": hvac_info["category"],
        "equipment_name": hvac_info["equipment_name"],
        "tons": hvac_info["tons"],
        "capacity_w": hvac_info["capacity_w"],
        "capacity_kw_thermal": None if hvac_info["capacity_w"] is None else hvac_info["capacity_w"] / 1000,
        "eir": hvac_info["eir"],
        "rated_efficiency": hvac_info["rated_efficiency"],
        "backup_capacity_kw": hvac_info["backup_capacity_kw"],
        "backup_eir": hvac_info["backup_eir"],
        "number_of_on_events": len(events),
        "total_minutes": total_minutes,
        "total_on_minutes": total_on_minutes,
        "duty_cycle": duty_cycle,
        "total_energy_kwh": total_energy_kwh,
        "peak_kw": peak_kw,
        "avg_kw": avg_kw,
        "avg_event_duration_minutes": avg_event_duration_minutes,
        "max_event_duration_minutes": max_event_duration_minutes,
        "avg_event_energy_kwh": avg_event_energy_kwh,
        "max_event_energy_kwh": max_event_energy_kwh,
        "avg_event_peak_kw": avg_event_peak_kw,
        "max_event_peak_kw": max_event_peak_kw,
    })


events_df = pd.DataFrame(event_rows)
summary_df = pd.DataFrame(summary_rows)

events_df.to_csv("hvac_on_events_first_day.csv", index=False)
summary_df.to_csv("hvac_daily_cycle_summary_first_day.csv", index=False)

print("\nSaved:")
print("  hvac_on_events_first_day.csv")
print("  hvac_daily_cycle_summary_first_day.csv")

print("\nDaily summary head:")
print(summary_df.head())

if not summary_df.empty:
    print("\nCategory counts:")
    print(summary_df["category"].value_counts())

    print("\nDuty cycle summary:")
    print(summary_df.groupby("category")["duty_cycle"].describe())

if not events_df.empty:
    print("\nON event duration summary:")
    print(events_df.groupby("category")["duration_minutes"].describe())

    print("\nON event energy summary:")
    print(events_df.groupby("category")["energy_kwh"].describe())


# ----------------------------
# Plots
# ----------------------------

if not events_df.empty:
    plt.figure(figsize=(8, 6))

    for category in events_df["category"].unique():
        subset = events_df[events_df["category"] == category]

        plt.scatter(
            subset["duration_minutes"],
            subset["energy_kwh"],
            alpha=0.6,
            edgecolor="black",
            linewidth=0.3,
            label=category,
        )

    plt.title("Energy per HVAC ON Event vs ON-Event Duration", fontsize=15, weight="bold")
    plt.xlabel("ON-event duration (minutes)", fontsize=12)
    plt.ylabel("Energy per ON event (kWh)", fontsize=12)
    plt.grid(True, alpha=0.25)
    plt.legend(title="HVAC category", frameon=False)
    plt.tight_layout()
    plt.savefig("hvac_event_energy_vs_duration.png", dpi=300, bbox_inches="tight")
    # plt.show()

    
    # 1) Event duration distribution
    plt.figure(figsize=(10, 6))

    duration_upper = events_df["duration_minutes"].quantile(0.99)

    for category in events_df["category"].unique():
        subset = events_df[events_df["category"] == category]

        plt.hist(
            subset["duration_minutes"],
            bins=range(0, int(duration_upper) + 5, 5),
            alpha=0.6,
            label=category,
            edgecolor="black",
            linewidth=0.4,
        )

    plt.xlim(0, duration_upper)

    plt.title("Distribution of HVAC ON-Event Durations", fontsize=15, weight="bold")
    plt.xlabel("ON-event duration (minutes)", fontsize=12)
    plt.ylabel("Number of ON events", fontsize=12)
    plt.grid(axis="y", alpha=0.25)
    plt.legend(title="HVAC category", frameon=False)
    plt.tight_layout()
    plt.savefig("hvac_event_duration_distribution.png", dpi=300, bbox_inches="tight")

    # 2) Event energy distribution
    plt.figure(figsize=(10, 6))

    energy_upper = events_df["energy_kwh"].quantile(0.99)

    for category in events_df["category"].unique():
        subset = events_df[events_df["category"] == category]

        plt.hist(
            subset["energy_kwh"],
            bins=np.arange(0, energy_upper + 0.25, 0.25),
            alpha=0.6,
            label=category,
            edgecolor="black",
            linewidth=0.4,
        )

    plt.xlim(0, energy_upper)

    plt.title("Distribution of HVAC ON-Event Energy", fontsize=15, weight="bold")
    plt.xlabel("Energy per ON event (kWh)", fontsize=12)
    plt.ylabel("Number of ON events", fontsize=12)
    plt.grid(axis="y", alpha=0.25)
    plt.legend(title="HVAC category", frameon=False)
    plt.tight_layout()
    plt.savefig("hvac_event_energy_distribution.png", dpi=300, bbox_inches="tight")

if not summary_df.empty:
    plt.figure(figsize=(8, 6))
    summary_df.boxplot(column="duty_cycle", by="category")
    plt.title("First-Day HVAC Duty Cycle by Category", fontsize=15, weight="bold")
    plt.suptitle("")
    plt.xlabel("HVAC category", fontsize=12)
    plt.ylabel("Duty cycle (-)", fontsize=12)
    plt.grid(axis="y", alpha=0.25)
    plt.tight_layout()
    plt.savefig("hvac_duty_cycle_by_category.png", dpi=300, bbox_inches="tight")
