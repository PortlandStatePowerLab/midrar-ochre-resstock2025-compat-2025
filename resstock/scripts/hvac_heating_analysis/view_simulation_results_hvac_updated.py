"""
Analyze first-day HVAC heating operation using OCHRE outputs.

This version uses:
- ochre.json for static equipment parameters
- ochre.csv for simulated first-day operation
"""

from pathlib import Path
import json
import pandas as pd
import matplotlib.pyplot as plt


src_dir = Path("../load_profiles/cosimulation2")
upgrade = "up00"
results_folder = "simulation_results"

HVAC_POWER_COL = "HVAC Heating Electric Power (kW)"
MINUTES_PER_DAY = 1440
DT_HOURS = 1 / 60  # one-minute resolution


def safe_float(value):
    """Return float(value), or None if unavailable."""
    try:
        if value is None:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def w_to_kw(value_w):
    value_w = safe_float(value_w)
    return None if value_w is None else value_w / 1000


def w_to_tons(value_w):
    """Convert heating thermal capacity from W to refrigeration tons."""
    value_w = safe_float(value_w)
    if value_w is None:
        return None

    # 1 ton = 12000 Btu/hr = 3516.85284 W
    return value_w / 3516.85284


def read_ochre_json(json_path):
    with open(json_path, "r") as f:
        return json.load(f)


def get_hvac_info_from_ochre_json(json_path):
    """
    Extract static HVAC heating parameters from OCHRE's ochre.json.

    OCHRE reports HVAC heating capacity in W. For heat pumps, it may also
    report backup electric resistance capacity and lockout temperatures.
    """
    data = read_ochre_json(json_path)

    hvac = data.get("Equipment", {}).get("HVAC Heating", {})

    equipment_name = hvac.get("Equipment Name", "N/A")
    fuel = hvac.get("Fuel", "N/A")

    capacity_w = safe_float(hvac.get("Capacity (W)"))
    capacity_kw_thermal = w_to_kw(capacity_w)
    tons = w_to_tons(capacity_w)

    backup_capacity_w = safe_float(hvac.get("Backup Capacity (W)"))
    backup_capacity_kw = w_to_kw(backup_capacity_w)

    rated_aux_power_w = safe_float(hvac.get("Rated Auxiliary Power (W)"))
    rated_aux_power_kw = w_to_kw(rated_aux_power_w)

    eir = safe_float(hvac.get("EIR (-)"))
    backup_eir = safe_float(hvac.get("Backup EIR (-)"))

    rated_efficiency = hvac.get("Rated Efficiency", "N/A")

    hp_lockout_c = safe_float(hvac.get("Heat Pump Lockout Temperature (C)"))
    backup_lockout_c = safe_float(hvac.get("Backup Lockout Temperature (C)"))

    # Practical category rule:
    # OCHRE heat pumps often appear as "air-to-air".
    # Electric resistance systems usually do not have backup heat-pump fields.
    if backup_capacity_kw is not None or "HSPF" in str(rated_efficiency):
        category = "heat_pump"
    elif str(fuel).lower() == "electricity":
        category = "electric_resistance"
    else:
        category = "other"

    return {
        "category": category,
        "equipment_name": equipment_name,
        "fuel": fuel,
        "capacity_w": capacity_w,
        "capacity_kw_thermal": capacity_kw_thermal,
        "tons": tons,
        "rated_efficiency": rated_efficiency,
        "eir": eir,
        "rated_aux_power_kw": rated_aux_power_kw,
        "backup_capacity_kw": backup_capacity_kw,
        "backup_eir": backup_eir,
        "hp_lockout_c": hp_lockout_c,
        "backup_lockout_c": backup_lockout_c,
    }


def find_interesting_columns(columns):
    """Find HVAC/backup/temperature columns worth inspecting."""
    keywords = [
        "hvac",
        "heat",
        "heating",
        "backup",
        "aux",
        "resistance",
        "indoor",
        "temperature",
        "setpoint",
    ]

    return [
        col for col in columns
        if any(keyword in col.lower() for keyword in keywords)
    ]


rows = []
missing = {
    "ochre_json": 0,
    "ochre_csv": 0,
    "hvac_power_col": 0,
}

for building_dir in src_dir.iterdir():
    if not building_dir.is_dir():
        continue

    building_id = building_dir.name
    input_dir = building_dir / upgrade
    sim_dir = input_dir / results_folder

    ochre_json = sim_dir / "ochre.json"
    ochre_csv = sim_dir / "ochre.csv"

    if not ochre_json.is_file():
        print(f"Missing ochre.json: {building_id}")
        missing["ochre_json"] += 1
        continue

    if not ochre_csv.is_file():
        print(f"Missing ochre.csv: {building_id}")
        missing["ochre_csv"] += 1
        continue

    try:
        hvac_info = get_hvac_info_from_ochre_json(ochre_json)
    except Exception as e:
        print(f"Could not read ochre.json for {building_id}: {e}")
        continue

    try:
        ts = pd.read_csv(ochre_csv)
    except Exception as e:
        print(f"Could not read ochre.csv for {building_id}: {e}")
        continue

    if HVAC_POWER_COL not in ts.columns:
        print(f"Missing HVAC power column for {building_id}")
        missing["hvac_power_col"] += 1
        continue

    # First day = first 1440 rows for one-minute resolution
    first_day = ts.iloc[:MINUTES_PER_DAY].copy()

    power_kw = first_day[HVAC_POWER_COL].fillna(0)

    daily_energy_kwh = power_kw.sum() * DT_HOURS
    peak_kw = power_kw.max()
    avg_kw = power_kw.mean()
    runtime_minutes = (power_kw > 0).sum()
    runtime_hours = runtime_minutes / 60

    kw_per_ton = None
    if hvac_info["tons"] not in (None, 0):
        kw_per_ton = peak_kw / hvac_info["tons"]

    # Simple diagnostic for heat pumps:
    # Electric resistance is about 3.516 kW per ton.
    if hvac_info["category"] == "heat_pump":
        if kw_per_ton is not None and kw_per_ton >= 3.5:
            hp_mode = "likely_backup_resistance_active"
        else:
            hp_mode = "likely_compressor_only"
    else:
        hp_mode = "not_heat_pump"

    rows.append({
        "building_id": building_id,
        **hvac_info,
        "peak_kw": peak_kw,
        "avg_kw": avg_kw,
        "daily_energy_kwh": daily_energy_kwh,
        "runtime_hours": runtime_hours,
        "kw_per_ton": kw_per_ton,
        "heat_pump_mode": hp_mode,
    })


summary = pd.DataFrame(rows)

summary.to_csv("first_day_hvac_summary_from_ochre_json.csv", index=False)

print("\nMissing files/columns:")
print(missing)

print("\nSummary head:")
print(summary.head())

print("\nCategory counts:")
print(summary["category"].value_counts(dropna=False))

if "heat_pump_mode" in summary.columns:
    print("\nHeat pump mode counts:")
    print(summary["heat_pump_mode"].value_counts(dropna=False))

print("\nNumerical summary:")
print(summary[[
    "tons",
    "capacity_kw_thermal",
    "backup_capacity_kw",
    "peak_kw",
    "avg_kw",
    "daily_energy_kwh",
    "runtime_hours",
    "kw_per_ton",
]].describe())


# ------------------------------------------------------------
# Plot 1: first-day energy vs unit size
# ------------------------------------------------------------
plt.figure(figsize=(8, 6))

for category in summary["category"].dropna().unique():
    subset = summary[summary["category"] == category]

    plt.scatter(
        subset["tons"],
        subset["daily_energy_kwh"],
        alpha=0.7,
        edgecolor="black",
        linewidth=0.4,
        label=category,
    )

plt.title("First-Day HVAC Heating Energy vs Unit Size", fontsize=15, weight="bold")
plt.xlabel("HVAC heating capacity (tons)", fontsize=12)
plt.ylabel("First-day heating energy consumption (kWh)", fontsize=12)
plt.grid(True, alpha=0.25)
plt.legend(title="HVAC category", frameon=False)
plt.tight_layout()
plt.savefig("first_day_energy_vs_tons.png", dpi=300, bbox_inches="tight")
plt.close()


# ------------------------------------------------------------
# Plot 2: first-day peak power vs unit size
# ------------------------------------------------------------
plt.figure(figsize=(8, 6))

for category in summary["category"].dropna().unique():
    subset = summary[summary["category"] == category]

    plt.scatter(
        subset["tons"],
        subset["peak_kw"],
        alpha=0.7,
        edgecolor="black",
        linewidth=0.4,
        label=category,
    )

plt.title("First-Day Peak HVAC Heating Power vs Unit Size", fontsize=15, weight="bold")
plt.xlabel("HVAC heating capacity (tons)", fontsize=12)
plt.ylabel("Peak heating electric power (kW)", fontsize=12)
plt.grid(True, alpha=0.25)
plt.legend(title="HVAC category", frameon=False)
plt.tight_layout()
plt.savefig("first_day_peak_kw_vs_tons.png", dpi=300, bbox_inches="tight")
plt.close()


# ------------------------------------------------------------
# Plot 3: heat-pump diagnostic using compressor/backup context
# ------------------------------------------------------------
hp_summary = summary[summary["category"] == "heat_pump"].copy()

if not hp_summary.empty:
    plt.figure(figsize=(8, 6))

    for mode in hp_summary["heat_pump_mode"].dropna().unique():
        subset = hp_summary[hp_summary["heat_pump_mode"] == mode]

        plt.scatter(
            subset["tons"],
            subset["peak_kw"],
            alpha=0.75,
            edgecolor="black",
            linewidth=0.4,
            label=mode,
        )

    plt.axline(
        (0, 0),
        slope=3.51685,
        linestyle="--",
        linewidth=1.2,
        label="electric resistance reference"
    )

    plt.title("Heat Pump Peak Power Diagnostic", fontsize=15, weight="bold")
    plt.xlabel("Heat pump heating capacity (tons)", fontsize=12)
    plt.ylabel("First-day peak heating electric power (kW)", fontsize=12)
    plt.grid(True, alpha=0.25)
    plt.legend(frameon=False)
    plt.tight_layout()
    plt.savefig("heat_pump_peak_power_diagnostic.png", dpi=300, bbox_inches="tight")
    plt.close()


# ------------------------------------------------------------
# Plot 4: represented capacity bins with actual first-day energy
# ------------------------------------------------------------
bin_width = 0.5
max_tons = summary["tons"].max()

if pd.notna(max_tons):
    bins = pd.interval_range(
        start=0,
        end=max_tons + bin_width,
        freq=bin_width,
        closed="left"
    )

    summary["tons_range"] = pd.cut(
        summary["tons"],
        bins=[interval.left for interval in bins] + [bins[-1].right],
        right=False,
        include_lowest=True,
    )

    bin_df = (
        summary.groupby("tons_range", observed=False)
        .agg(
            device_count=("building_id", "count"),
            total_peak_kw=("peak_kw", "sum"),
            total_first_day_energy_kwh=("daily_energy_kwh", "sum"),
        )
        .reset_index()
    )

    bin_df = bin_df[bin_df["device_count"] > 0]
    bin_df["tons_range_str"] = bin_df["tons_range"].astype(str)

    bin_df.to_csv("first_day_hvac_by_tons_bin.csv", index=False)

    plt.figure(figsize=(12, 6))

    bars = plt.bar(
        bin_df["tons_range_str"],
        bin_df["total_first_day_energy_kwh"],
        edgecolor="black",
        linewidth=0.5,
    )

    for bar, count in zip(bars, bin_df["device_count"]):
        height = bar.get_height()
        plt.text(
            bar.get_x() + bar.get_width() / 2,
            height,
            f"n={count}",
            ha="center",
            va="bottom",
            fontsize=9,
        )

    plt.title("First-Day Heating Energy by HVAC Capacity Range", fontsize=15, weight="bold")
    plt.xlabel("HVAC heating capacity range (tons)", fontsize=12)
    plt.ylabel("Total first-day heating energy (kWh)", fontsize=12)
    plt.xticks(rotation=45, ha="right")
    plt.grid(axis="y", alpha=0.25)
    plt.tight_layout()
    plt.savefig("first_day_energy_by_capacity_range.png", dpi=300, bbox_inches="tight")
    plt.close()

print("\nSaved:")
print("- first_day_hvac_summary_from_ochre_json.csv")
print("- first_day_energy_vs_tons.png")
print("- first_day_peak_kw_vs_tons.png")
print("- heat_pump_peak_power_diagnostic.png")
print("- first_day_hvac_by_tons_bin.csv")
print("- first_day_energy_by_capacity_range.png")
