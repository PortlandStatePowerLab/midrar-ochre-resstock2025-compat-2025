'''
Author: MidrarAdham
Created: Thu Jul 16 2026
'''
"""
Create all-device histogram diagnostics for HVAC ON behavior.

This script extends the near-full-day investigation idea to ALL buildings,
not only the suspicious buildings.

It computes, for each building:
- minutes above several HVAC power thresholds
- fraction/percent of day above those thresholds
- duty cycle using the main ON threshold, 0.3 kW

Outputs:
- all_device_power_threshold_counts.csv
- all_device_power_threshold_counts_long.csv
- all_devices_duty_cycle_histogram.png
- all_devices_minutes_above_0p3kw_histogram.png
- all_devices_minutes_above_1p0kw_histogram.png
- all_devices_percent_above_threshold_by_threshold_boxplot.png
- all_devices_duty_cycle_vs_tons.png
"""

from pathlib import Path
import pandas as pd
import matplotlib.pyplot as plt


# ----------------------------
# User settings
# ----------------------------

SRC_DIR = Path("../load_profiles/cosimulation2")
UPGRADE = "up00"
RESULTS_FOLDER = "simulation_results"

OCHRE_CSV_NAME = "ochre.csv"
SUMMARY_FILE = "hvac_daily_cycle_summary_first_day.csv"

HVAC_POWER_COL = "HVAC Heating Electric Power (kW)"

FIRST_DAY_ROWS = 1440

# The first threshold is your main ON definition.
POWER_THRESHOLDS_KW = [0.3, 0.5, 1.0, 2.0, 5.0]


# ----------------------------
# Helpers
# ----------------------------

def threshold_col_name(threshold_kw):
    """Create a clean CSV column name from a threshold value."""
    return f"minutes_above_{str(threshold_kw).replace('.', 'p')}_kw"


def read_summary_metadata():
    """
    Read building-level metadata from the existing summary CSV.

    This gives us category, tons, energy, peak power, etc., without reparsing JSON.
    """
    summary_path = Path(SUMMARY_FILE)

    if not summary_path.is_file():
        raise FileNotFoundError(
            f"Missing {SUMMARY_FILE}. Run the ON-cycle analysis script first."
        )

    summary_df = pd.read_csv(summary_path)
    summary_df["building_id"] = summary_df["building_id"].astype(str)

    return summary_df


# ----------------------------
# Main computation
# ----------------------------

summary_df = read_summary_metadata()

rows = []

for _, summary_row in summary_df.iterrows():
    building_id = str(summary_row["building_id"])

    ochre_csv = (
        SRC_DIR
        / building_id
        / UPGRADE
        / RESULTS_FOLDER
        / OCHRE_CSV_NAME
    )

    if not ochre_csv.is_file():
        print(f"Missing ochre.csv: {building_id}")
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
    power_kw = first_day[HVAC_POWER_COL].fillna(0)

    row = {
        "building_id": building_id,
        "category": summary_row.get("category", "N/A"),
        "equipment_name": summary_row.get("equipment_name", "N/A"),
        "tons": summary_row.get("tons", float("nan")),
        "total_energy_kwh": summary_row.get("total_energy_kwh", float("nan")),
        "peak_kw": summary_row.get("peak_kw", float("nan")),
        "avg_kw": summary_row.get("avg_kw", float("nan")),
        "number_of_on_events": summary_row.get("number_of_on_events", float("nan")),
        "duty_cycle_from_events": summary_row.get("duty_cycle", float("nan")),
        "mean_first_day_power_kw": power_kw.mean(),
        "max_first_day_power_kw": power_kw.max(),
    }

    for threshold_kw in POWER_THRESHOLDS_KW:
        col = threshold_col_name(threshold_kw)
        minutes_above = int((power_kw > threshold_kw).sum())

        row[col] = minutes_above
        row[col.replace("minutes_above", "percent_of_day_above")] = (
            100 * minutes_above / len(first_day)
            if len(first_day) > 0
            else 0
        )

    rows.append(row)


threshold_df = pd.DataFrame(rows)
threshold_df.to_csv("all_device_power_threshold_counts.csv", index=False)


# Long format is easier for grouped plots and tables.
long_rows = []

for _, row in threshold_df.iterrows():
    for threshold_kw in POWER_THRESHOLDS_KW:
        minute_col = threshold_col_name(threshold_kw)
        percent_col = minute_col.replace("minutes_above", "percent_of_day_above")

        long_rows.append({
            "building_id": row["building_id"],
            "category": row["category"],
            "tons": row["tons"],
            "threshold_kw": threshold_kw,
            "minutes_above_threshold": row[minute_col],
            "percent_of_day_above_threshold": row[percent_col],
            "total_energy_kwh": row["total_energy_kwh"],
            "peak_kw": row["peak_kw"],
            "number_of_on_events": row["number_of_on_events"],
        })

threshold_long = pd.DataFrame(long_rows)
threshold_long.to_csv("all_device_power_threshold_counts_long.csv", index=False)


print("\nSaved:")
print("  all_device_power_threshold_counts.csv")
print("  all_device_power_threshold_counts_long.csv")

print("\nSummary of percent of day above each threshold:")
print(
    threshold_long
    .groupby(["threshold_kw", "category"])["percent_of_day_above_threshold"]
    .describe()
)


# ----------------------------
# Plots
# ----------------------------

# 1) Duty-cycle histogram for all devices.
plt.figure(figsize=(10, 6))

for category in threshold_df["category"].dropna().unique():
    subset = threshold_df[threshold_df["category"] == category]

    plt.hist(
        subset["duty_cycle_from_events"],
        bins=[i / 20 for i in range(21)],
        alpha=0.6,
        label=category,
        edgecolor="black",
        linewidth=0.4,
    )

plt.title("Distribution of First-Day HVAC Duty Cycle: All Devices", fontsize=15, weight="bold")
plt.xlabel("Duty cycle using 0.3 kW ON threshold (-)", fontsize=12)
plt.ylabel("Number of devices", fontsize=12)
plt.xlim(0, 1)
plt.grid(axis="y", alpha=0.25)
plt.legend(title="HVAC category", frameon=False)
plt.tight_layout()
plt.savefig("all_devices_duty_cycle_histogram.png", dpi=300, bbox_inches="tight")


# 2) Minutes above 0.3 kW histogram.
plt.figure(figsize=(10, 6))

col_0p3 = threshold_col_name(0.3)

for category in threshold_df["category"].dropna().unique():
    subset = threshold_df[threshold_df["category"] == category]

    plt.hist(
        subset[col_0p3],
        bins=range(0, FIRST_DAY_ROWS + 60, 60),
        alpha=0.6,
        label=category,
        edgecolor="black",
        linewidth=0.4,
    )

plt.axvline(1400, linestyle="--", linewidth=1, label="Near-full-day threshold")
plt.title("Minutes Above 0.3 kW: All Devices", fontsize=15, weight="bold")
plt.xlabel("Minutes above 0.3 kW during first day", fontsize=12)
plt.ylabel("Number of devices", fontsize=12)
plt.xlim(0, FIRST_DAY_ROWS)
plt.grid(axis="y", alpha=0.25)
plt.legend(title="HVAC category", frameon=False)
plt.tight_layout()
plt.savefig("all_devices_minutes_above_0p3kw_histogram.png", dpi=300, bbox_inches="tight")


# 3) Minutes above 1.0 kW histogram.
plt.figure(figsize=(10, 6))

col_1p0 = threshold_col_name(1.0)

for category in threshold_df["category"].dropna().unique():
    subset = threshold_df[threshold_df["category"] == category]

    plt.hist(
        subset[col_1p0],
        bins=range(0, FIRST_DAY_ROWS + 60, 60),
        alpha=0.6,
        label=category,
        edgecolor="black",
        linewidth=0.4,
    )

plt.axvline(1400, linestyle="--", linewidth=1, label="Near-full-day threshold")
plt.title("Minutes Above 1.0 kW: All Devices", fontsize=15, weight="bold")
plt.xlabel("Minutes above 1.0 kW during first day", fontsize=12)
plt.ylabel("Number of devices", fontsize=12)
plt.xlim(0, FIRST_DAY_ROWS)
plt.grid(axis="y", alpha=0.25)
plt.legend(title="HVAC category", frameon=False)
plt.tight_layout()
plt.savefig("all_devices_minutes_above_1p0kw_histogram.png", dpi=300, bbox_inches="tight")


# 4) Box plot: percent of day above each threshold.
# This summarizes how persistence changes as the power threshold increases.
plt.figure(figsize=(10, 6))

threshold_long.boxplot(
    column="percent_of_day_above_threshold",
    by="threshold_kw",
)

plt.title("Percent of Day Above Each HVAC Power Threshold: All Devices", fontsize=15, weight="bold")
plt.suptitle("")
plt.xlabel("Power threshold (kW)", fontsize=12)
plt.ylabel("Percent of first day above threshold (%)", fontsize=12)
plt.ylim(0, 105)
plt.grid(axis="y", alpha=0.25)
plt.tight_layout()
plt.savefig("all_devices_percent_above_threshold_by_threshold_boxplot.png", dpi=300, bbox_inches="tight")


# 5) Duty cycle vs tons for all devices.
plt.figure(figsize=(8, 6))

for category in threshold_df["category"].dropna().unique():
    subset = threshold_df[threshold_df["category"] == category]

    plt.scatter(
        subset["tons"],
        subset["duty_cycle_from_events"],
        alpha=0.65,
        edgecolor="black",
        linewidth=0.35,
        label=category,
    )

plt.axhline(0.97, linestyle="--", linewidth=1, label="Near-full-day duty cycle")
plt.title("First-Day HVAC Duty Cycle vs Unit Size: All Devices", fontsize=15, weight="bold")
plt.xlabel("HVAC heating capacity (tons)", fontsize=12)
plt.ylabel("Duty cycle using 0.3 kW ON threshold (-)", fontsize=12)
plt.ylim(0, 1.05)
plt.grid(True, alpha=0.25)
plt.legend(frameon=False)
plt.tight_layout()
plt.savefig("all_devices_duty_cycle_vs_tons.png", dpi=300, bbox_inches="tight")


print("\nSaved plots:")
print("  all_devices_duty_cycle_histogram.png")
print("  all_devices_minutes_above_0p3kw_histogram.png")
print("  all_devices_minutes_above_1p0kw_histogram.png")
print("  all_devices_percent_above_threshold_by_threshold_boxplot.png")
print("  all_devices_duty_cycle_vs_tons.png")
