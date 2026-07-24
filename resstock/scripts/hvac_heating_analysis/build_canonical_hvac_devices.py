'''
Author: Midrar Adham
Created: Sat Jul 18 2026
'''
"""
Build the canonical HVAC device table.

Step 2 in the HVAC binning / OLS workflow.

Input:
- hvac_equipment_report.csv
  produced by report_hvac_equipment_metadata.py

Output:
- canonical_hvac_devices.csv

Purpose:
Create one clean row per co-simulation HVAC device. This table is the bridge
between raw HPXML/OCHRE metadata and later filtering/bin construction.
"""

from pathlib import Path
import pandas as pd


input_file = Path("hvac_equipment_report.csv")
output_file = Path("canonical_hvac_devices.csv")


def build_device_filename(building_id):
    """Match the device naming convention used in the OCHRE/Bayesian workflow."""
    return f"ochre_load_{building_id}.csv"


def normalize_text(value):
    """Normalize text values while preserving missing values."""
    if pd.isna(value):
        return None
    text = str(value).strip()
    if text == "" or text.lower() in {"nan", "none"}:
        return None
    return text


def infer_technology(row):
    """Create the technology label used by binning."""
    element_type = normalize_text(row.get("element_type"))
    analysis_class = normalize_text(row.get("analysis_class"))
    equipment_type = normalize_text(row.get("equipment_type"))
    fuel = normalize_text(row.get("fuel"))

    if element_type == "HeatPump":
        return "heat_pump"

    if analysis_class == "electric_resistance":
        return "electric_resistance"

    if equipment_type is not None and "electricresistance" in equipment_type.lower().replace(" ", ""):
        return "electric_resistance"

    if fuel is not None and fuel.lower() == "electricity":
        return "electric_heating_system_uncertain"

    return "other_or_non_electric"


def choose_first_available(row, column_names):
    """Return the first non-missing value from a list of candidate columns."""
    for col in column_names:
        if col in row.index and pd.notna(row.get(col)):
            return row.get(col)
    return None


def choose_estimated_electric_kw(row, technology, capacity_kw_thermal):
    """
    Estimate primary electric input kW.

    Rules:
    - If OCHRE estimated electric kW exists, use it.
    - If OCHRE thermal capacity and EIR exist, use capacity_kw_thermal * EIR.
    - For electric resistance, electric kW ~= thermal kW.
    - Otherwise leave missing.
    """
    value = choose_first_available(row, ["ochre_estimated_electric_kw"])
    if value is not None:
        return value

    ochre_capacity_kw_thermal = choose_first_available(
        row,
        ["ochre_capacity_kw_thermal", "ochre_capacity_kw"],
    )
    eir = choose_first_available(row, ["ochre_eir"])

    if ochre_capacity_kw_thermal is not None and eir is not None:
        return ochre_capacity_kw_thermal * eir

    if technology == "electric_resistance" and capacity_kw_thermal is not None:
        return capacity_kw_thermal

    return None


def choose_estimated_backup_electric_kw(row, backup_fuel, backup_capacity_kw_thermal):
    """
    Estimate backup electric input kW.

    Rules:
    - If OCHRE estimated backup electric kW exists, use it.
    - If backup fuel is electricity and backup EIR exists, use thermal kW * EIR.
    - If backup fuel is electricity and no EIR exists, approximate electric
      resistance backup as electric kW ~= thermal kW.
    - If backup fuel is fossil/wood/other non-electric, do not convert
      thermal capacity into electric demand.
    """
    value = choose_first_available(row, ["ochre_estimated_backup_electric_kw"])
    if value is not None:
        return value

    if backup_fuel is None:
        return None

    if str(backup_fuel).lower() != "electricity":
        return 0.0

    backup_eir = choose_first_available(row, ["ochre_backup_eir"])

    if backup_eir is not None and backup_capacity_kw_thermal is not None:
        return backup_capacity_kw_thermal * backup_eir

    if backup_capacity_kw_thermal is not None:
        return backup_capacity_kw_thermal

    return None


def build_canonical_table(report):
    rows = []

    for _, row in report.iterrows():
        building_id = str(row["building_id"])
        technology = infer_technology(row)

        capacity_btuh = choose_first_available(row, ["heating_capacity_btu_hr"])
        capacity_tons = choose_first_available(
            row,
            ["heating_capacity_tons", "ochre_capacity_tons"],
        )
        capacity_kw_thermal = choose_first_available(
            row,
            ["heating_capacity_kw_thermal", "ochre_capacity_kw_thermal", "ochre_capacity_kw"],
        )

        estimated_electric_kw = choose_estimated_electric_kw(
            row,
            technology=technology,
            capacity_kw_thermal=capacity_kw_thermal,
        )

        backup_type = normalize_text(
            choose_first_available(row, ["backup_system_type", "backup_type"])
        )
        backup_fuel = normalize_text(row.get("backup_fuel"))

        backup_capacity_tons = choose_first_available(
            row,
            ["backup_heating_capacity_tons", "ochre_backup_capacity_tons"],
        )
        backup_capacity_kw_thermal = choose_first_available(
            row,
            [
                "backup_heating_capacity_kw_thermal",
                "ochre_backup_capacity_kw_thermal",
                "ochre_backup_capacity_kw",
            ],
        )

        estimated_backup_electric_kw = choose_estimated_backup_electric_kw(
            row,
            backup_fuel=backup_fuel,
            backup_capacity_kw_thermal=backup_capacity_kw_thermal,
        )

        rows.append({
            "device_filename": build_device_filename(building_id),
            "building_id": building_id,
            "element_type": normalize_text(row.get("element_type")),
            "equipment_type": normalize_text(row.get("equipment_type")),
            "technology": technology,
            "analysis_class": normalize_text(row.get("analysis_class")),
            "fuel": normalize_text(row.get("fuel")),
            "capacity_btuh": capacity_btuh,
            "capacity_tons": capacity_tons,
            "capacity_kw_thermal": capacity_kw_thermal,
            "metadata_reference_estimated_electric_kw": estimated_electric_kw,
            "backup_type": backup_type,
            "backup_fuel": backup_fuel,
            "backup_capacity_tons": backup_capacity_tons,
            "backup_capacity_kw_thermal": backup_capacity_kw_thermal,
            "metadata_reference_backup_electric_kw": estimated_backup_electric_kw,
            "compressor_type": normalize_text(row.get("compressor_type")),
        })

    canonical = pd.DataFrame(rows)

    duplicated = canonical[canonical["device_filename"].duplicated(keep=False)]
    if not duplicated.empty:
        duplicated.to_csv("canonical_hvac_duplicate_device_filenames.csv", index=False)
        print(
            "WARNING: duplicate device_filename values found. "
            "Saved canonical_hvac_duplicate_device_filenames.csv"
        )

    return canonical


def main():
    if not input_file.is_file():
        raise FileNotFoundError(
            f"Missing {input_file}. Run report_hvac_equipment_metadata.py first."
        )

    report = pd.read_csv(input_file)
    canonical = build_canonical_table(report)

    canonical.to_csv(output_file, index=False)

if __name__ == "__main__":
    main()

