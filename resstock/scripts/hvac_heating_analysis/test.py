'''
Author: Midrar Adham
Created: Fri Jul 10 2026
'''

import os
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from pprint import pprint as pp
import xml.etree.ElementTree as ET

hvac_info = {}
src_dir = "../load_profiles/cosimulation2/"

excluded_fuels = ("propane", "natural gas", "fuel oil", "wood")


def btu_hr_to_kw_thermal(capacity_btu_hr):
    return float(capacity_btu_hr) / 3412.142


def btu_hr_to_tons(capacity_btu_hr):
    return float(capacity_btu_hr) / 12000


def get_efficiency(system, ns):
    units = system.findtext(".//h:AnnualHeatingEfficiency/h:Units", default="N/A", namespaces=ns)
    value = system.findtext(".//h:AnnualHeatingEfficiency/h:Value", default="1.0", namespaces=ns)

    try:
        value = float(value)
    except ValueError:
        value = 1.0

    return units, value


def estimate_electric_kw(capacity_btu_hr, thermal_kw, eff_units, eff_value):
    eff_units = str(eff_units).strip()

    if eff_units == "COP":
        return thermal_kw / eff_value

    elif eff_units == "HSPF":
        # HSPF = Btu / Wh
        # electric W = Btu/hr / HSPF
        # electric kW = Btu/hr / HSPF / 1000
        return float(capacity_btu_hr) / eff_value / 1000

    elif eff_units == "Percent":
        # Sometimes percent is stored as 0.98 or 1.0,
        # sometimes as 98 or 100.
        if eff_value > 1:
            efficiency_fraction = eff_value / 100
        else:
            efficiency_fraction = eff_value

        return thermal_kw / efficiency_fraction

    elif eff_units == "AFUE":
        # AFUE is usually stored as a fraction, e.g., 0.76
        return thermal_kw / eff_value

    else:
        # Electric resistance fallback: COP ≈ 1
        return thermal_kw


for bldg_id in os.listdir(src_dir):
    home_xml = f"{src_dir}/{bldg_id}/up00/home.xml"

    try:
        tree = ET.parse(home_xml)
    except FileNotFoundError:
        continue

    root = tree.getroot()
    ns_uri = root.tag.split("}")[0].strip("{")
    ns = {"h": ns_uri}

    hvac_list = []

    # HeatingSystem: electricity here is likely electric resistance
    for system in root.findall(".//h:HVAC/h:HVACPlant/h:HeatingSystem", ns):

        system_id = system.find("h:SystemIdentifier", ns).attrib.get("id")
        fuel = system.findtext("h:HeatingSystemFuel", default="N/A", namespaces=ns)
        capacity = system.findtext("h:HeatingCapacity", default="N/A", namespaces=ns)

        if fuel in excluded_fuels:
            continue

        thermal_kw = btu_hr_to_kw_thermal(capacity)
        tons = btu_hr_to_tons(capacity)

        eff_units, eff_value = get_efficiency(system, ns)
        electric_kw = estimate_electric_kw(capacity, thermal_kw, eff_units, eff_value)

        hvac_list.append({
            "category": "electric_resistance",
            "id": system_id,
            "fuel": fuel,
            "heating_capacity_btu_hr": float(capacity),
            "tons": round(tons, 2),
            "thermal_kw": round(thermal_kw, 2),
            "efficiency_units": eff_units,
            "efficiency_value": eff_value,
            "electric_kw": round(electric_kw, 2),
        })

    # HeatPump: actual heat pumps
    for hp in root.findall(".//h:HVAC/h:HVACPlant/h:HeatPump", ns):

        hp_id = hp.find("h:SystemIdentifier", ns).attrib.get("id")
        hp_type = hp.findtext("h:HeatPumpType", default="N/A", namespaces=ns)
        fuel = hp.findtext("h:HeatPumpFuel", default="electricity", namespaces=ns)
        capacity = hp.findtext("h:HeatingCapacity", default="N/A", namespaces=ns)

        thermal_kw = btu_hr_to_kw_thermal(capacity)
        tons = btu_hr_to_tons(capacity)

        eff_units, eff_value = get_efficiency(hp, ns)
        electric_kw = estimate_electric_kw(capacity, thermal_kw, eff_units, eff_value)

        hvac_list.append({
            "category": "heat_pump",
            "id": hp_id,
            "type": hp_type,
            "fuel": fuel,
            "heating_capacity_btu_hr": float(capacity),
            "tons": round(tons, 2),
            "thermal_kw": round(thermal_kw, 2),
            "efficiency_units": eff_units,
            "efficiency_value": eff_value,
            "electric_kw": round(electric_kw, 2),
        })

    if hvac_list:
        hvac_info[bldg_id] = hvac_list

# for key, value in hvac_info.items ():
#     if key == '62052':
#         print(key, value[0]['category'])

    
# quit()
print("Total buildings:", len(hvac_info))
print("Heat pump buildings:",
      sum(any(x["category"] == "heat_pump" for x in systems)
          for systems in hvac_info.values()))

print("Electric resistance buildings:",
      sum(any(x["category"] == "electric_resistance" for x in systems)
          for systems in hvac_info.values()))


rows = []

for bldg_id, systems in hvac_info.items():
    for system in systems:
        rows.append({
            "building_id": bldg_id,
            "category": system["category"],
            "fuel": system["fuel"],
            "capacity_btu_hr": system["heating_capacity_btu_hr"],
            "tons": system["tons"],
            "thermal_kw": system["thermal_kw"],
            "electric_kw": system["electric_kw"],
            "efficiency_units": system["efficiency_units"],
            "efficiency_value": system["efficiency_value"],
        })

df = pd.DataFrame(rows)

print(df.head())
print(df["category"].value_counts())


# 0.5 kW bins
bin_width = 0.5
max_kw = df["electric_kw"].max()

bins = np.arange(0, max_kw + bin_width, bin_width)

df["kw_range"] = pd.cut(
    df["electric_kw"],
    bins=bins,
    right=False,
    include_lowest=True
)

# Count devices by kW range and category
plot_df = (
    df.groupby(["kw_range", "category"], observed=False)
      .size()
      .reset_index(name="device_count")
)

# Convert interval labels to clean strings
plot_df["kw_range"] = plot_df["kw_range"].astype(str)

# Pivot for stacked bar plot
pivot_df = plot_df.pivot(
    index="kw_range",
    columns="category",
    values="device_count"
).fillna(0)

# Keep only bins that actually have devices
pivot_df = pivot_df[pivot_df.sum(axis=1) > 0]

plt.figure(figsize=(12, 6))

pivot_df.plot(
    kind="bar",
    stacked=True,
    figsize=(12, 6),
    edgecolor="black",
    linewidth=0.4
)

plt.title("Distribution of HVAC Heating Electric Power", fontsize=15, weight="bold")
plt.xlabel("Estimated heating electric power range (kW)", fontsize=12)
plt.ylabel("Number of HVAC devices", fontsize=12)

plt.xticks(rotation=45, ha="right")
plt.grid(axis="y", alpha=0.25)

plt.legend(
    title="HVAC category",
    frameon=False
)

plt.tight_layout()

plt.savefig("hvac_heating_power_distribution.png", dpi=300, bbox_inches="tight")
# plt.show()

# 0.5 ton bins
bin_width = 0.5
max_tons = df["tons"].max()

bins = np.arange(0, max_tons + bin_width, bin_width)

df["tons_range"] = pd.cut(
    df["tons"],
    bins=bins,
    right=False,
    include_lowest=True
)

plot_df = (
    df.groupby(["tons_range", "category"], observed=False)
      .size()
      .reset_index(name="device_count")
)

plot_df["tons_range"] = plot_df["tons_range"].astype(str)

pivot_df = plot_df.pivot(
    index="tons_range",
    columns="category",
    values="device_count"
).fillna(0)

pivot_df = pivot_df[pivot_df.sum(axis=1) > 0]

ax = pivot_df.plot(
    kind="bar",
    stacked=True,
    figsize=(12, 6),
    edgecolor="black",
    linewidth=0.4
)

plt.title("Distribution of HVAC Heating Capacity", fontsize=15, weight="bold")
plt.xlabel("Heating capacity range (tons)", fontsize=12)
plt.ylabel("Number of HVAC devices", fontsize=12)

plt.xticks(rotation=45, ha="right")
plt.grid(axis="y", alpha=0.25)
plt.legend(title="HVAC category", frameon=False)

plt.tight_layout()
plt.savefig("hvac_heating_capacity_distribution_tons.png", dpi=300, bbox_inches="tight")
# plt.show()

plt.figure(figsize=(8, 6))

for category in df["category"].unique():
    subset = df[df["category"] == category]

    plt.scatter(
        subset["tons"],
        subset["electric_kw"],
        alpha=0.7,
        label=category,
        edgecolor="black",
        linewidth=0.4
    )

plt.title("Heating Capacity vs. Heating Electric Power", fontsize=15, weight="bold")
plt.xlabel("Heating capacity (tons)", fontsize=12)
plt.ylabel("Estimated heating electric power (kW)", fontsize=12)

plt.grid(True, alpha=0.25)
plt.legend(title="HVAC category", frameon=False)

plt.tight_layout()
plt.savefig("hvac_capacity_vs_electric_power.png", dpi=300, bbox_inches="tight")
# plt.show()




# ======================================================================================


bin_width = 0.5
max_tons = df["tons"].max()

bins = np.arange(0, max_tons + bin_width, bin_width)

df["tons_range"] = pd.cut(
    df["tons"],
    bins=bins,
    right=False,
    include_lowest=True
)

# For each tons bin:
# - sum electric kW
# - count devices
plot_df = (
    df.groupby("tons_range", observed=False)
      .agg(
          total_electric_kw=("electric_kw", "sum"),
          device_count=("building_id", "count")
      )
      .reset_index()
)

# Remove empty bins
plot_df = plot_df[plot_df["device_count"] > 0]

plot_df["tons_range_str"] = plot_df["tons_range"].astype(str)

plt.figure(figsize=(12, 6))

bars = plt.bar(
    plot_df["tons_range_str"],
    plot_df["total_electric_kw"],
    edgecolor="black",
    linewidth=0.5
)

# Add device count labels above bars
for bar, count in zip(bars, plot_df["device_count"]):
    height = bar.get_height()
    plt.text(
        bar.get_x() + bar.get_width() / 2,
        height,
        f"n={count}",
        ha="center",
        va="bottom",
        fontsize=9
    )

plt.title("Aggregated Heating Electric Power by HVAC Capacity Range", fontsize=15, weight="bold")
plt.xlabel("Heating capacity range (tons)", fontsize=12)
plt.ylabel("Total represented heating electric power (kW)", fontsize=12)

plt.xticks(rotation=45, ha="right")
plt.grid(axis="y", alpha=0.25)

plt.tight_layout()
plt.savefig("aggregated_kw_by_capacity_range.png", dpi=300, bbox_inches="tight")
# plt.show()



