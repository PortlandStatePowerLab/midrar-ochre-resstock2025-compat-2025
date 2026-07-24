'''
Author: MidrarAdham
Created: Sat Jul 18 2026
'''
"""
Report and validate HVAC heating equipment metadata from HPXML home.xml files.

For each building, this script reports:
- building_id
- number of HVAC heating records found in home.xml
- system_identifier
- element_type: HeatingSystem or HeatPump
- equipment_type
- compressor_type, when present for HeatPump
- fuel
- heating_capacity_btu_hr
- heating_capacity_tons
- heating_capacity_kw_thermal
- backup_heating_capacity_btu_hr, if present in HPXML
- backup_heating_capacity_tons, if present
- backup_heating_capacity_kw_thermal, if present
- backup_fuel, if present in HPXML
- backup_system_type, if present in HPXML
- OCHRE-interpreted HVAC Heating fields from ochre.json, if available

Important:
OCHRE "Capacity (W)" and "Backup Capacity (W)" are heating-output capacities,
so this script labels them as thermal W/kW/tons. Estimated electric draw is
reported separately using EIR where possible.

Outputs:
- hvac_equipment_report.csv
- hvac_equipment_building_counts.csv
- hvac_equipment_manual_check_candidates.csv
"""

from pathlib import Path
import json
import xml.etree.ElementTree as ET
import pandas as pd


src_dir = Path("../load_profiles/cosimulation2")
upgrade = "up00"
results_folder = "simulation_results"


def safe_float(value):
    """Convert a value to float when possible; otherwise return None."""
    if value is None or value == "N/A":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def btu_hr_to_tons(capacity_btu_hr):
    value = safe_float(capacity_btu_hr)
    if value is None:
        return None
    return value / 12000


def btu_hr_to_kw_thermal(capacity_btu_hr):
    value = safe_float(capacity_btu_hr)
    if value is None:
        return None
    return value / 3412.142


def watts_to_tons(capacity_w):
    value = safe_float(capacity_w)
    if value is None:
        return None
    return value / 3516.85


def get_root_and_ns(home_xml):
    tree = ET.parse(home_xml)
    root = tree.getroot()
    ns_uri = root.tag.split("}")[0].strip("{")
    ns = {"h": ns_uri}
    return root, ns


def get_system_identifier(element, ns):
    ident = element.find("h:SystemIdentifier", ns)
    if ident is None:
        return None
    return ident.attrib.get("id")


def get_heating_system_type(system, ns):
    """
    For HeatingSystem, HPXML usually stores the equipment type as a child
    under HeatingSystemType, such as Furnace, Boiler, ElectricResistance, etc.
    """
    type_parent = system.find("h:HeatingSystemType", ns)

    if type_parent is None:
        return None

    for child in list(type_parent):
        return child.tag.split("}")[-1]

    return None


def first_existing_text(element, ns, candidate_names):
    """
    Search for the first existing direct child or descendant tag
    from a list of possible HPXML tag names.
    """
    for name in candidate_names:
        value = element.findtext(f"h:{name}", default=None, namespaces=ns)
        if value is not None:
            return value

    for name in candidate_names:
        value = element.findtext(f".//h:{name}", default=None, namespaces=ns)
        if value is not None:
            return value

    return None


def read_ochre_json(input_dir):
    """Read OCHRE JSON if available."""
    candidates = [
        input_dir / results_folder / "ochre.json",
        input_dir / "ochre.json",
    ]

    for path in candidates:
        if path.is_file():
            with open(path, "r") as f:
                return json.load(f)

    return None


def get_ochre_hvac_heating_info(input_dir):
    data = read_ochre_json(input_dir)

    if data is None:
        return {}

    return data.get("Equipment", {}).get("HVAC Heating", {}) or {}


def classify_record(element_type, equipment_type, fuel):
    """
    Create a conservative analysis class.
    """
    equipment_type_lower = str(equipment_type).lower().replace(" ", "")
    fuel_lower = str(fuel).lower()

    if element_type == "HeatPump":
        return "heat_pump"

    if element_type == "HeatingSystem" and "electricresistance" in equipment_type_lower:
        return "electric_resistance"

    if element_type == "HeatingSystem" and fuel_lower == "electricity":
        return "electric_heating_system_uncertain"

    return "other_or_non_electric"


def estimate_ochre_electric_kw_thermal_capacity(capacity_w_thermal, eir):
    """
    Estimate electric input kW from OCHRE thermal capacity and EIR.

    OCHRE Capacity (W) is thermal output. EIR is approximately electric input /
    thermal output. Therefore:
        electric_input_kw ≈ thermal_capacity_w * EIR / 1000
    """
    capacity_w_thermal = safe_float(capacity_w_thermal)
    eir = safe_float(eir)

    if capacity_w_thermal is None or eir is None:
        return None

    return capacity_w_thermal * eir / 1000


def make_row(
    building_id,
    home_xml_path,
    element_type,
    system_identifier,
    equipment_type,
    compressor_type,
    fuel,
    heating_capacity,
    backup_capacity,
    backup_fuel,
    backup_system_type,
    ochre_hvac,
):
    ochre_capacity_w_thermal = safe_float(ochre_hvac.get("Capacity (W)"))
    ochre_backup_capacity_w_thermal = safe_float(ochre_hvac.get("Backup Capacity (W)"))
    ochre_eir = safe_float(ochre_hvac.get("EIR (-)"))
    ochre_backup_eir = safe_float(ochre_hvac.get("Backup EIR (-)"))

    return {
        "building_id": building_id,
        "home_xml_path": str(home_xml_path),
        "system_identifier": system_identifier,
        "element_type": element_type,
        "equipment_type": equipment_type,
        "compressor_type": compressor_type,
        "fuel": fuel,
        "analysis_class": classify_record(element_type, equipment_type, fuel),

        # HPXML primary capacity
        "heating_capacity_btu_hr": safe_float(heating_capacity),
        "heating_capacity_tons": btu_hr_to_tons(heating_capacity),
        "heating_capacity_kw_thermal": btu_hr_to_kw_thermal(heating_capacity),

        # HPXML backup capacity and backup type/fuel when present
        "backup_heating_capacity_btu_hr": safe_float(backup_capacity),
        "backup_heating_capacity_tons": btu_hr_to_tons(backup_capacity),
        "backup_heating_capacity_kw_thermal": btu_hr_to_kw_thermal(backup_capacity),
        "backup_fuel": backup_fuel,
        "backup_system_type": backup_system_type,

        # OCHRE-interpreted primary values.
        # These are thermal/output capacities, not electric input draw.
        "ochre_equipment_name": ochre_hvac.get("Equipment Name"),
        "ochre_fuel": ochre_hvac.get("Fuel"),
        "ochre_capacity_w_thermal": ochre_capacity_w_thermal,
        "ochre_capacity_kw_thermal": (
            ochre_capacity_w_thermal / 1000
            if ochre_capacity_w_thermal is not None
            else None
        ),
        "ochre_capacity_tons": watts_to_tons(ochre_capacity_w_thermal),
        "ochre_eir": ochre_eir,
        "ochre_rated_efficiency": ochre_hvac.get("Rated Efficiency"),
        "ochre_estimated_electric_kw": estimate_ochre_electric_kw_thermal_capacity(
            ochre_capacity_w_thermal,
            ochre_eir,
        ),

        # OCHRE-interpreted backup values.
        # These are also thermal/output capacities. Electric draw is estimated
        # separately using Backup EIR when available.
        "ochre_backup_capacity_w_thermal": ochre_backup_capacity_w_thermal,
        "ochre_backup_capacity_kw_thermal": (
            ochre_backup_capacity_w_thermal / 1000
            if ochre_backup_capacity_w_thermal is not None
            else None
        ),
        "ochre_backup_capacity_tons": watts_to_tons(ochre_backup_capacity_w_thermal),
        "ochre_backup_eir": ochre_backup_eir,
        "ochre_estimated_backup_electric_kw": estimate_ochre_electric_kw_thermal_capacity(
            ochre_backup_capacity_w_thermal,
            ochre_backup_eir,
        ),
        "ochre_hp_lockout_c": safe_float(ochre_hvac.get("Heat Pump Lockout Temperature (C)")),
        "ochre_backup_lockout_c": safe_float(ochre_hvac.get("Backup Lockout Temperature (C)")),
    }


def collect_hvac_rows_for_building(building_dir):
    building_id = building_dir.name
    input_dir = building_dir / upgrade
    home_xml = input_dir / "home.xml"

    if not home_xml.is_file():
        return []

    try:
        root, ns = get_root_and_ns(home_xml)
    except Exception as e:
        print(f"Could not parse home.xml for {building_id}: {e}")
        return []

    ochre_hvac = get_ochre_hvac_heating_info(input_dir)
    rows = []

    # HeatingSystem elements
    for system in root.findall(".//h:HVAC/h:HVACPlant/h:HeatingSystem", ns):
        system_id = get_system_identifier(system, ns)
        equipment_type = get_heating_system_type(system, ns)
        fuel = system.findtext("h:HeatingSystemFuel", default=None, namespaces=ns)
        heating_capacity = system.findtext("h:HeatingCapacity", default=None, namespaces=ns)

        backup_capacity = first_existing_text(
            system,
            ns,
            [
                "BackupHeatingCapacity",
                "BackupCapacity",
                "AuxiliaryHeatingCapacity",
                "SupplementalHeatingCapacity",
            ],
        )

        backup_fuel = first_existing_text(
            system,
            ns,
            [
                "BackupSystemFuel",
                "BackupHeatingFuel",
                "BackupFuel",
                "AuxiliaryHeatingFuel",
                "SupplementalHeatingFuel",
            ],
        )

        backup_system_type = first_existing_text(
            system,
            ns,
            [
                "BackupType",
                "BackupHeatingSystemType",
                "BackupSystemType",
                "AuxiliaryHeatingSystemType",
                "SupplementalHeatingSystemType",
            ],
        )

        rows.append(
            make_row(
                building_id=building_id,
                home_xml_path=home_xml,
                element_type="HeatingSystem",
                system_identifier=system_id,
                equipment_type=equipment_type,
                compressor_type=None,
                fuel=fuel,
                heating_capacity=heating_capacity,
                backup_capacity=backup_capacity,
                backup_fuel=backup_fuel,
                backup_system_type=backup_system_type,
                ochre_hvac=ochre_hvac,
            )
        )

    # HeatPump elements
    for hp in root.findall(".//h:HVAC/h:HVACPlant/h:HeatPump", ns):
        system_id = get_system_identifier(hp, ns)
        equipment_type = hp.findtext("h:HeatPumpType", default=None, namespaces=ns)
        fuel = hp.findtext("h:HeatPumpFuel", default="electricity", namespaces=ns)
        heating_capacity = hp.findtext("h:HeatingCapacity", default=None, namespaces=ns)
        compressor_type = hp.findtext("h:CompressorType", default=None, namespaces=ns)

        backup_capacity = first_existing_text(
            hp,
            ns,
            [
                "BackupHeatingCapacity",
                "BackupCapacity",
                "AuxiliaryHeatingCapacity",
                "SupplementalHeatingCapacity",
            ],
        )

        backup_fuel = first_existing_text(
            hp,
            ns,
            [
                "BackupSystemFuel",
                "BackupHeatingFuel",
                "BackupFuel",
                "AuxiliaryHeatingFuel",
                "SupplementalHeatingFuel",
            ],
        )

        backup_system_type = first_existing_text(
            hp,
            ns,
            [
                "BackupType",
                "BackupHeatingSystemType",
                "BackupSystemType",
                "AuxiliaryHeatingSystemType",
                "SupplementalHeatingSystemType",
            ],
        )

        rows.append(
            make_row(
                building_id=building_id,
                home_xml_path=home_xml,
                element_type="HeatPump",
                system_identifier=system_id,
                equipment_type=equipment_type,
                compressor_type=compressor_type,
                fuel=fuel,
                heating_capacity=heating_capacity,
                backup_capacity=backup_capacity,
                backup_fuel=backup_fuel,
                backup_system_type=backup_system_type,
                ochre_hvac=ochre_hvac,
            )
        )

    return rows


def choose_manual_check_candidates(report):
    """
    Pick one candidate from each target class for manual XML/OCHRE inspection:
    - one electric resistance system
    - one air-to-air heat pump
    - one mini-split heat pump
    """
    candidates = []

    electric_resistance = report[
        report["analysis_class"] == "electric_resistance"
    ]

    if not electric_resistance.empty:
        candidates.append(electric_resistance.sort_values("building_id").iloc[0])

    air_to_air = report[
        (report["element_type"] == "HeatPump")
        & (report["equipment_type"].astype(str).str.contains("air-to-air", case=False, na=False))
    ]

    if not air_to_air.empty:
        candidates.append(air_to_air.sort_values("building_id").iloc[0])

    mini_split = report[
        (report["element_type"] == "HeatPump")
        & (
            report["equipment_type"].astype(str).str.contains("mini", case=False, na=False)
            | report["compressor_type"].astype(str).str.contains("mini", case=False, na=False)
        )
    ]

    if not mini_split.empty:
        candidates.append(mini_split.sort_values("building_id").iloc[0])

    if not candidates:
        return pd.DataFrame()

    return pd.DataFrame(candidates).drop_duplicates(subset=["building_id", "system_identifier"])


def main():
    all_rows = []

    for building_dir in src_dir.iterdir():
        if not building_dir.is_dir():
            continue

        all_rows.extend(collect_hvac_rows_for_building(building_dir))

    report = pd.DataFrame(all_rows)

    if report.empty:
        print("No HVAC equipment found.")
        return

    counts = (
        report.groupby("building_id")
        .size()
        .reset_index(name="n_hvac_heating_records")
    )

    report = report.merge(counts, on="building_id", how="left")

    report = report.sort_values(
        ["analysis_class", "element_type", "equipment_type", "heating_capacity_tons", "building_id"],
        na_position="last",
    )

    report.to_csv("hvac_equipment_report.csv", index=False)
    # counts.to_csv("hvac_equipment_building_counts.csv", index=False)

    manual_candidates = choose_manual_check_candidates(report)
    # manual_candidates.to_csv("hvac_equipment_manual_check_candidates.csv", index=False)

    print("Saved:")
    print("  hvac_equipment_report.csv")
    # print("  hvac_equipment_building_counts.csv")
    # print("  hvac_equipment_manual_check_candidates.csv")

    # print("\nRows:", len(report))
    # print("\nBuildings:", report["building_id"].nunique())

    # print("\nHVAC heating records per building:")
    # print(counts["n_hvac_heating_records"].value_counts().sort_index())

    # print("\nAnalysis class counts:")
    # print(report["analysis_class"].value_counts(dropna=False))

    # print("\nElement type counts:")
    # print(report["element_type"].value_counts(dropna=False))

    # print("\nEquipment type counts:")
    # print(report["equipment_type"].value_counts(dropna=False))

    # print("\nCompressor type counts:")
    # print(report["compressor_type"].value_counts(dropna=False))

    # print("\nFuel counts:")
    # print(report["fuel"].value_counts(dropna=False))

    # print("\nBackup fuel counts:")
    # print(report["backup_fuel"].value_counts(dropna=False))

    # print("\nBackup system type counts:")
    # print(report["backup_system_type"].value_counts(dropna=False))

    print("\nManual check candidates:")
    if manual_candidates.empty:
        print("No manual-check candidates found.")
    else:
        cols = [
            "building_id",
            "analysis_class",
            "element_type",
            "equipment_type",
            "compressor_type",
            "fuel",
            "heating_capacity_btu_hr",
            "heating_capacity_tons",
            "backup_heating_capacity_btu_hr",
            "backup_fuel",
            "backup_system_type",
            "ochre_equipment_name",
            "ochre_capacity_w_thermal",
            "ochre_estimated_electric_kw",
            "ochre_backup_capacity_w_thermal",
            "ochre_estimated_backup_electric_kw",
            "home_xml_path",
        ]
    #     print(manual_candidates[cols])
    
    # print("\n\n======================\n\n")
    # heat_pumps = report[report["element_type"] == "HeatPump"]
    # print(heat_pumps["backup_fuel"].value_counts(dropna=False))
    # print("\n\n======================\n\n")
    # print(heat_pumps["backup_system_type"].value_counts(dropna=False))


if __name__ == "__main__":
    main()
