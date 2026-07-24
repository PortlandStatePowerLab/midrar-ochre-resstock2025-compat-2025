'''
Author: Midrar Adham
Created: Thu Jul 23 2026
'''
"""
02_extract_hvac_metadata.py

Extract heating and cooling HVAC metadata for ResStock 2024 / OCHRE analysis.

This script reads the inventory created by:

01_scan_ochre_results.py

Then, for each building-upgrade case, it reads:

- home.xml
- simulation_results/ochre.json

The goal is to create a device/equipment metadata table that can later be
joined with OCHRE time-series diagnostics.

Output:

outputs/hvac_metadata.csv

Important:
This script does not modify any simulation files.
"""

import json
import pandas as pd
from pathlib import Path
import xml.etree.ElementTree as et


# ---------------------------------------------------------------------------
# User settings
# ---------------------------------------------------------------------------
# Rule: keep variable names lowercase.

analysis_dir = Path("./outputs/")
inventory_file = analysis_dir / "ochre_result_inventory.csv"

output_file = analysis_dir / "hvac_metadata.csv"

# These names should match the folders from your scan script.
results_folder = "simulation_results_august"

# These are the upgrades currently included in your study.
upgrades = ["up00", "up01", "up02"]


# ---------------------------------------------------------------------------
# Unit conversions
# ---------------------------------------------------------------------------

def btuh_to_tons(value):
    """
    Convert Btu/hr to refrigeration tons.

    1 ton = 12,000 Btu/hr.
    """
    if value is None:
        return None

    try:
        return float(value) / 12000.0
    except Exception:
        return None


def btuh_to_kw_thermal(value):
    """
    Convert Btu/hr to thermal kW.

    1 kW = 3412.142 Btu/hr.
    """
    if value is None:
        return None

    try:
        return float(value) / 3412.142
    except Exception:
        return None


def watts_to_kw(value):
    """
    Convert W to kW.
    """
    if value is None:
        return None

    try:
        return float(value) / 1000.0
    except Exception:
        return None


# ---------------------------------------------------------------------------
# General helpers
# ---------------------------------------------------------------------------

def clean_text(value):
    """
    Convert XML text to a clean string.

    Empty strings become None.
    """
    if value is None:
        return None

    value = str(value).strip()

    if value == "":
        return None

    return value


def to_float(value):
    """
    Convert a value to float when possible.

    Invalid or missing values become None.
    """
    value = clean_text(value)

    if value is None:
        return None

    try:
        return float(value)
    except Exception:
        return None


def strip_namespace(tag):
    """
    Remove XML namespace from an element tag.

    Example:
    {http://hpxmlonline.com/2023/09}HeatPump -> HeatPump
    """
    if "}" in tag:
        return tag.split("}", 1)[1]

    return tag


def child_text(element, child_name):
    """
    Return the text from a direct child with a given local tag name.

    This ignores XML namespaces.
    """
    if element is None:
        return None

    for child in list(element):
        if strip_namespace(child.tag) == child_name:
            return clean_text(child.text)

    return None


def descendant_text(element, descendant_name):
    """
    Return the first matching descendant text with a given local tag name.

    This ignores XML namespaces.
    """
    if element is None:
        return None

    for descendant in element.iter():
        if strip_namespace(descendant.tag) == descendant_name:
            return clean_text(descendant.text)

    return None


def find_elements_by_name(root, element_name):
    """
    Find all elements with a given local tag name.

    This ignores XML namespaces.
    """
    matches = []

    for element in root.iter():
        if strip_namespace(element.tag) == element_name:
            matches.append(element)

    return matches


def get_system_identifier(element):
    """
    Try to get a useful HPXML system identifier.

    HPXML IDs may appear as attributes with or without namespaces.
    """
    if element is None:
        return None

    for key, value in element.attrib.items():
        if key.endswith("id") or key.endswith("ID"):
            return value

    return None


# ---------------------------------------------------------------------------
# home.xml extraction
# ---------------------------------------------------------------------------

def classify_hpxml_equipment(element_type, equipment_type, fuel):
    """
    Create a simple analysis class for HVAC equipment.

    The labels are intentionally broad. We can refine them after we inspect the
    output table.
    """
    equipment_type_text = str(equipment_type or "").lower()
    fuel_text = str(fuel or "").lower()

    if element_type == "HeatPump":
        if "ground" in equipment_type_text or "geothermal" in equipment_type_text:
            return "geothermal_heat_pump"

        return "air_source_heat_pump"

    if element_type == "CoolingSystem":
        return "cooling_system"

    if element_type == "HeatingSystem":
        if fuel_text == "electricity":
            return "electric_heating_system"

        if fuel_text in ["natural gas", "propane", "fuel oil", "wood"]:
            return "fossil_or_other_heating_system"

        return "heating_system"

    return "unknown"


def extract_hpxml_heating_systems(root, building_id, upgrade, source_file):
    """
    Extract HeatingSystem elements from home.xml.
    """
    rows = []

    for element in find_elements_by_name(root, "HeatingSystem"):
        equipment_type = child_text(element, "HeatingSystemType")
        fuel = child_text(element, "HeatingSystemFuel")
        capacity_btuh = to_float(child_text(element, "HeatingCapacity"))

        rows.append({
            "building_id": building_id,
            "upgrade": upgrade,
            "source": "home_xml",
            "source_file": str(source_file),
            "element_type": "HeatingSystem",
            "system_identifier": get_system_identifier(element),
            "equipment_type": equipment_type,
            "fuel": fuel,
            "heating_capacity_btuh": capacity_btuh,
            "heating_capacity_tons": btuh_to_tons(capacity_btuh),
            "heating_capacity_kw_thermal": btuh_to_kw_thermal(capacity_btuh),
            "cooling_capacity_btuh": None,
            "cooling_capacity_tons": None,
            "cooling_capacity_kw_thermal": None,
            "backup_fuel": None,
            "backup_system_type": None,
            "backup_heating_capacity_btuh": None,
            "backup_heating_capacity_tons": None,
            "backup_heating_capacity_kw_thermal": None,
            "compressor_type": None,
            "annual_heating_efficiency_type": descendant_text(element, "AnnualHeatingEfficiencyUnits"),
            "annual_heating_efficiency_value": to_float(descendant_text(element, "AnnualHeatingEfficiencyValue")),
            "annual_cooling_efficiency_type": None,
            "annual_cooling_efficiency_value": None,
            "analysis_class": classify_hpxml_equipment("HeatingSystem", equipment_type, fuel),
        })

    return rows


def extract_hpxml_cooling_systems(root, building_id, upgrade, source_file):
    """
    Extract CoolingSystem elements from home.xml.
    """
    rows = []

    for element in find_elements_by_name(root, "CoolingSystem"):
        equipment_type = child_text(element, "CoolingSystemType")
        fuel = child_text(element, "CoolingSystemFuel")
        capacity_btuh = to_float(child_text(element, "CoolingCapacity"))

        rows.append({
            "building_id": building_id,
            "upgrade": upgrade,
            "source": "home_xml",
            "source_file": str(source_file),
            "element_type": "CoolingSystem",
            "system_identifier": get_system_identifier(element),
            "equipment_type": equipment_type,
            "fuel": fuel,
            "heating_capacity_btuh": None,
            "heating_capacity_tons": None,
            "heating_capacity_kw_thermal": None,
            "cooling_capacity_btuh": capacity_btuh,
            "cooling_capacity_tons": btuh_to_tons(capacity_btuh),
            "cooling_capacity_kw_thermal": btuh_to_kw_thermal(capacity_btuh),
            "backup_fuel": None,
            "backup_system_type": None,
            "backup_heating_capacity_btuh": None,
            "backup_heating_capacity_tons": None,
            "backup_heating_capacity_kw_thermal": None,
            "compressor_type": None,
            "annual_heating_efficiency_type": None,
            "annual_heating_efficiency_value": None,
            "annual_cooling_efficiency_type": descendant_text(element, "AnnualCoolingEfficiencyUnits"),
            "annual_cooling_efficiency_value": to_float(descendant_text(element, "AnnualCoolingEfficiencyValue")),
            "analysis_class": classify_hpxml_equipment("CoolingSystem", equipment_type, fuel),
        })

    return rows


def extract_hpxml_heat_pumps(root, building_id, upgrade, source_file):
    """
    Extract HeatPump elements from home.xml.

    Heat pumps are important because they may provide both heating and cooling.
    """
    rows = []

    for element in find_elements_by_name(root, "HeatPump"):
        equipment_type = child_text(element, "HeatPumpType")
        fuel = child_text(element, "HeatPumpFuel")

        heating_capacity_btuh = to_float(child_text(element, "HeatingCapacity"))
        cooling_capacity_btuh = to_float(child_text(element, "CoolingCapacity"))
        backup_heating_capacity_btuh = to_float(child_text(element, "BackupHeatingCapacity"))

        backup_fuel = child_text(element, "BackupHeatingFuel")
        backup_system_type = child_text(element, "BackupSystemType")

        rows.append({
            "building_id": building_id,
            "upgrade": upgrade,
            "source": "home_xml",
            "source_file": str(source_file),
            "element_type": "HeatPump",
            "system_identifier": get_system_identifier(element),
            "equipment_type": equipment_type,
            "fuel": fuel,
            "heating_capacity_btuh": heating_capacity_btuh,
            "heating_capacity_tons": btuh_to_tons(heating_capacity_btuh),
            "heating_capacity_kw_thermal": btuh_to_kw_thermal(heating_capacity_btuh),
            "cooling_capacity_btuh": cooling_capacity_btuh,
            "cooling_capacity_tons": btuh_to_tons(cooling_capacity_btuh),
            "cooling_capacity_kw_thermal": btuh_to_kw_thermal(cooling_capacity_btuh),
            "backup_fuel": backup_fuel,
            "backup_system_type": backup_system_type,
            "backup_heating_capacity_btuh": backup_heating_capacity_btuh,
            "backup_heating_capacity_tons": btuh_to_tons(backup_heating_capacity_btuh),
            "backup_heating_capacity_kw_thermal": btuh_to_kw_thermal(backup_heating_capacity_btuh),
            "compressor_type": child_text(element, "CompressorType"),
            "annual_heating_efficiency_type": descendant_text(element, "AnnualHeatingEfficiencyUnits"),
            "annual_heating_efficiency_value": to_float(descendant_text(element, "AnnualHeatingEfficiencyValue")),
            "annual_cooling_efficiency_type": descendant_text(element, "AnnualCoolingEfficiencyUnits"),
            "annual_cooling_efficiency_value": to_float(descendant_text(element, "AnnualCoolingEfficiencyValue")),
            "analysis_class": classify_hpxml_equipment("HeatPump", equipment_type, fuel),
        })

    return rows


def extract_home_xml_metadata(home_xml, building_id, upgrade):
    """
    Extract all HVAC equipment rows from home.xml.
    """
    try:
        root = et.parse(home_xml).getroot()
    except Exception as error:
        return [{
            "building_id": building_id,
            "upgrade": upgrade,
            "source": "home_xml",
            "source_file": str(home_xml),
            "element_type": "xml_read_error",
            "system_identifier": None,
            "equipment_type": None,
            "fuel": None,
            "heating_capacity_btuh": None,
            "heating_capacity_tons": None,
            "heating_capacity_kw_thermal": None,
            "cooling_capacity_btuh": None,
            "cooling_capacity_tons": None,
            "cooling_capacity_kw_thermal": None,
            "backup_fuel": None,
            "backup_system_type": None,
            "backup_heating_capacity_btuh": None,
            "backup_heating_capacity_tons": None,
            "backup_heating_capacity_kw_thermal": None,
            "compressor_type": None,
            "annual_heating_efficiency_type": None,
            "annual_heating_efficiency_value": None,
            "annual_cooling_efficiency_type": None,
            "annual_cooling_efficiency_value": None,
            "analysis_class": "xml_read_error",
            "read_error": str(error),
        }]

    rows = []
    rows.extend(extract_hpxml_heating_systems(root, building_id, upgrade, home_xml))
    rows.extend(extract_hpxml_cooling_systems(root, building_id, upgrade, home_xml))
    rows.extend(extract_hpxml_heat_pumps(root, building_id, upgrade, home_xml))

    for row in rows:
        row["read_error"] = None

    if not rows:
        rows.append({
            "building_id": building_id,
            "upgrade": upgrade,
            "source": "home_xml",
            "source_file": str(home_xml),
            "element_type": "no_hvac_elements_found",
            "system_identifier": None,
            "equipment_type": None,
            "fuel": None,
            "heating_capacity_btuh": None,
            "heating_capacity_tons": None,
            "heating_capacity_kw_thermal": None,
            "cooling_capacity_btuh": None,
            "cooling_capacity_tons": None,
            "cooling_capacity_kw_thermal": None,
            "backup_fuel": None,
            "backup_system_type": None,
            "backup_heating_capacity_btuh": None,
            "backup_heating_capacity_tons": None,
            "backup_heating_capacity_kw_thermal": None,
            "compressor_type": None,
            "annual_heating_efficiency_type": None,
            "annual_heating_efficiency_value": None,
            "annual_cooling_efficiency_type": None,
            "annual_cooling_efficiency_value": None,
            "analysis_class": "no_hvac_elements_found",
            "read_error": None,
        })

    return rows


# ---------------------------------------------------------------------------
# ochre.json extraction
# ---------------------------------------------------------------------------

def flatten_dict(value, prefix=""):
    """
    Flatten a nested dictionary.

    This helps us search ochre.json without assuming one exact nested layout.
    """
    rows = {}

    if not isinstance(value, dict):
        return rows

    for key, item in value.items():
        new_key = f"{prefix}.{key}" if prefix else str(key)

        if isinstance(item, dict):
            rows.update(flatten_dict(item, new_key))
        else:
            rows[new_key] = item

    return rows


def find_equipment_dicts(value, path=""):
    """
    Recursively find dictionaries in ochre.json whose path or keys mention HVAC.

    This is intentionally broad because OCHRE JSON structure can change between
    versions.
    """
    matches = []

    if isinstance(value, dict):
        text = " ".join([path] + [str(key) for key in value.keys()]).lower()

        if "hvac" in text or "heat pump" in text or "heating" in text or "cooling" in text:
            matches.append((path, value))

        for key, item in value.items():
            next_path = f"{path}.{key}" if path else str(key)
            matches.extend(find_equipment_dicts(item, next_path))

    elif isinstance(value, list):
        for index, item in enumerate(value):
            next_path = f"{path}[{index}]"
            matches.extend(find_equipment_dicts(item, next_path))

    return matches


def get_first_by_possible_keys(flattened, possible_names):
    """
    Return the first value whose flattened key ends with one of the names.

    The match is case-insensitive and ignores spaces/underscores.
    """
    normalized_possible = [
        name.lower().replace(" ", "").replace("_", "")
        for name in possible_names
    ]

    for key, value in flattened.items():
        simple_key = key.split(".")[-1].lower().replace(" ", "").replace("_", "")

        if simple_key in normalized_possible:
            return value

    return None


def extract_ochre_json_metadata(ochre_json, building_id, upgrade):
    """
    Extract broad HVAC metadata from ochre.json.

    This is secondary to home.xml. It is mainly useful for checking what OCHRE
    actually created as equipment.
    """
    try:
        with open(ochre_json, "r", encoding="utf-8") as file:
            data = json.load(file)
    except Exception as error:
        return [{
            "building_id": building_id,
            "upgrade": upgrade,
            "source": "ochre_json",
            "source_file": str(ochre_json),
            "element_type": "json_read_error",
            "system_identifier": None,
            "equipment_type": None,
            "fuel": None,
            "heating_capacity_btuh": None,
            "heating_capacity_tons": None,
            "heating_capacity_kw_thermal": None,
            "cooling_capacity_btuh": None,
            "cooling_capacity_tons": None,
            "cooling_capacity_kw_thermal": None,
            "backup_fuel": None,
            "backup_system_type": None,
            "backup_heating_capacity_btuh": None,
            "backup_heating_capacity_tons": None,
            "backup_heating_capacity_kw_thermal": None,
            "compressor_type": None,
            "annual_heating_efficiency_type": None,
            "annual_heating_efficiency_value": None,
            "annual_cooling_efficiency_type": None,
            "annual_cooling_efficiency_value": None,
            "analysis_class": "json_read_error",
            "read_error": str(error),
        }]

    equipment_matches = find_equipment_dicts(data)
    rows = []

    for path, equipment in equipment_matches:
        flattened = flatten_dict(equipment)

        equipment_name = path.split(".")[-1] if path else None

        capacity_w = to_float(get_first_by_possible_keys(
            flattened,
            ["Capacity (W)", "Capacity", "capacity_w"]
        ))

        backup_capacity_w = to_float(get_first_by_possible_keys(
            flattened,
            ["Backup Capacity (W)", "Backup Capacity", "backup_capacity_w"]
        ))

        eir = to_float(get_first_by_possible_keys(
            flattened,
            ["EIR (-)", "EIR", "eir"]
        ))

        backup_eir = to_float(get_first_by_possible_keys(
            flattened,
            ["Backup EIR (-)", "Backup EIR", "backup_eir"]
        ))

        rows.append({
            "building_id": building_id,
            "upgrade": upgrade,
            "source": "ochre_json",
            "source_file": str(ochre_json),
            "element_type": "OCHRE equipment",
            "system_identifier": path,
            "equipment_type": equipment_name,
            "fuel": get_first_by_possible_keys(flattened, ["Fuel", "fuel"]),
            "heating_capacity_btuh": None,
            "heating_capacity_tons": None,
            "heating_capacity_kw_thermal": watts_to_kw(capacity_w),
            "cooling_capacity_btuh": None,
            "cooling_capacity_tons": None,
            "cooling_capacity_kw_thermal": None,
            "backup_fuel": get_first_by_possible_keys(flattened, ["Backup Fuel", "backup_fuel"]),
            "backup_system_type": get_first_by_possible_keys(flattened, ["Backup System Type", "backup_system_type"]),
            "backup_heating_capacity_btuh": None,
            "backup_heating_capacity_tons": None,
            "backup_heating_capacity_kw_thermal": watts_to_kw(backup_capacity_w),
            "compressor_type": get_first_by_possible_keys(flattened, ["Compressor Type", "compressor_type"]),
            "annual_heating_efficiency_type": None,
            "annual_heating_efficiency_value": eir,
            "annual_cooling_efficiency_type": None,
            "annual_cooling_efficiency_value": None,
            "analysis_class": "ochre_json_equipment",
            "read_error": None,
            "ochre_capacity_w": capacity_w,
            "ochre_eir": eir,
            "ochre_backup_capacity_w": backup_capacity_w,
            "ochre_backup_eir": backup_eir,
        })

    if not rows:
        rows.append({
            "building_id": building_id,
            "upgrade": upgrade,
            "source": "ochre_json",
            "source_file": str(ochre_json),
            "element_type": "no_hvac_json_entries_found",
            "system_identifier": None,
            "equipment_type": None,
            "fuel": None,
            "heating_capacity_btuh": None,
            "heating_capacity_tons": None,
            "heating_capacity_kw_thermal": None,
            "cooling_capacity_btuh": None,
            "cooling_capacity_tons": None,
            "cooling_capacity_kw_thermal": None,
            "backup_fuel": None,
            "backup_system_type": None,
            "backup_heating_capacity_btuh": None,
            "backup_heating_capacity_tons": None,
            "backup_heating_capacity_kw_thermal": None,
            "compressor_type": None,
            "annual_heating_efficiency_type": None,
            "annual_heating_efficiency_value": None,
            "annual_cooling_efficiency_type": None,
            "annual_cooling_efficiency_value": None,
            "analysis_class": "no_hvac_json_entries_found",
            "read_error": None,
        })

    return rows


# ---------------------------------------------------------------------------
# Main script
# ---------------------------------------------------------------------------

def main():
    """
    Extract HVAC metadata for all building-upgrade cases in the inventory.
    """
    if not inventory_file.is_file():
        raise FileNotFoundError(
            f"inventory_file does not exist: {inventory_file}\n"
            "Thomas:\nRun scan_ochre_results.py first."
        )

    analysis_dir.mkdir(parents=True, exist_ok=True)

    inventory = pd.read_csv(inventory_file)

    # Keep only the requested upgrades.
    inventory = inventory[inventory["upgrade"].isin(upgrades)].copy()

    rows = []

    for _, item in inventory.iterrows():
        building_id = str(item["building_id"])
        upgrade = str(item["upgrade"])
        upgrade_dir = Path(item["upgrade_dir"])
        results_dir = Path(item["results_dir"])

        home_xml = upgrade_dir / "home.xml"
        ochre_json = results_dir / "ochre.json"

        if home_xml.is_file():
            rows.extend(extract_home_xml_metadata(home_xml, building_id, upgrade))
        else:
            rows.append({
                "building_id": building_id,
                "upgrade": upgrade,
                "source": "home_xml",
                "source_file": str(home_xml),
                "element_type": "missing_home_xml",
                "system_identifier": None,
                "equipment_type": None,
                "fuel": None,
                "heating_capacity_btuh": None,
                "heating_capacity_tons": None,
                "heating_capacity_kw_thermal": None,
                "cooling_capacity_btuh": None,
                "cooling_capacity_tons": None,
                "cooling_capacity_kw_thermal": None,
                "backup_fuel": None,
                "backup_system_type": None,
                "backup_heating_capacity_btuh": None,
                "backup_heating_capacity_tons": None,
                "backup_heating_capacity_kw_thermal": None,
                "compressor_type": None,
                "annual_heating_efficiency_type": None,
                "annual_heating_efficiency_value": None,
                "annual_cooling_efficiency_type": None,
                "annual_cooling_efficiency_value": None,
                "analysis_class": "missing_home_xml",
                "read_error": None,
            })

        if ochre_json.is_file():
            rows.extend(extract_ochre_json_metadata(ochre_json, building_id, upgrade))
        else:
            rows.append({
                "building_id": building_id,
                "upgrade": upgrade,
                "source": "ochre_json",
                "source_file": str(ochre_json),
                "element_type": "missing_ochre_json",
                "system_identifier": None,
                "equipment_type": None,
                "fuel": None,
                "heating_capacity_btuh": None,
                "heating_capacity_tons": None,
                "heating_capacity_kw_thermal": None,
                "cooling_capacity_btuh": None,
                "cooling_capacity_tons": None,
                "cooling_capacity_kw_thermal": None,
                "backup_fuel": None,
                "backup_system_type": None,
                "backup_heating_capacity_btuh": None,
                "backup_heating_capacity_tons": None,
                "backup_heating_capacity_kw_thermal": None,
                "compressor_type": None,
                "annual_heating_efficiency_type": None,
                "annual_heating_efficiency_value": None,
                "annual_cooling_efficiency_type": None,
                "annual_cooling_efficiency_value": None,
                "analysis_class": "missing_ochre_json",
                "read_error": None,
            })

    metadata = pd.DataFrame(rows)

    metadata.to_csv(output_file, index=False)

    print("\nSaved HVAC metadata:")
    print(output_file)

    print("\nTotal metadata rows:")
    print(len(metadata))

    print("\nRows by source:")
    print(metadata["source"].value_counts(dropna=False))

    print("\nRows by upgrade and element type:")
    print(
        metadata
        .groupby(["upgrade", "element_type"])
        .size()
        .unstack(fill_value=0)
    )

    print("\nRows by upgrade and analysis class:")
    print(
        metadata
        .groupby(["upgrade", "analysis_class"])
        .size()
        .unstack(fill_value=0)
    )

    print("\nHeat pump backup fuel counts from home.xml:")
    home_heat_pumps = metadata[
        (metadata["source"] == "home_xml")
        & (metadata["element_type"] == "HeatPump")
    ]
    if len(home_heat_pumps) > 0:
        print(
            home_heat_pumps
            .groupby(["upgrade", "backup_fuel"])
            .size()
            .unstack(fill_value=0)
        )
    else:
        print("No HeatPump rows found in home.xml.")

    print("\nPreview:")
    preview_cols = [
        "building_id",
        "upgrade",
        "source",
        "element_type",
        "equipment_type",
        "fuel",
        "analysis_class",
        "heating_capacity_tons",
        "cooling_capacity_tons",
        "backup_fuel",
        "backup_heating_capacity_tons",
    ]
    available_preview_cols = [col for col in preview_cols if col in metadata.columns]
    print(metadata[available_preview_cols].head(30))


if __name__ == "__main__":
    main()

