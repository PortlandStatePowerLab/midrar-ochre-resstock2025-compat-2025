'''
Check required OCHRE files and move excluded ResStock buildings.
'''

import shutil
import pandas as pd
from pathlib import Path
import xml.etree.ElementTree as ET

src_dir = Path("../load_profiles/cosimulation2")
excluded_dir = Path("../load_profiles/excluded_non_resistive_non_heatpump")
upgrade = "up00"

required_files = [
    "home.xml",
    "in.schedules.csv",
]

excluded_hvac_fuels = {
    "propane",
    "natural gas",
    "fuel oil",
    "wood",
}

allowed_water_heater_types = {
    "storage water heater",
    "heat pump water heater",
}


def has_required_files(input_dir):
    missing_files = []

    for file_name in required_files:
        file_path = input_dir / file_name
        if not file_path.is_file() or file_path.stat().st_size == 0:
            missing_files.append(file_name)

    return len(missing_files) == 0, missing_files


def get_root_and_ns(input_dir):
    home_xml = input_dir / "home.xml"
    tree = ET.parse(home_xml)
    root = tree.getroot()
    ns_uri = root.tag.split("}")[0].strip("{")
    ns = {"h": ns_uri}
    return root, ns


def has_allowed_hvac(input_dir):
    root, ns = get_root_and_ns(input_dir)

    # Heat pump HVAC
    heat_pumps = root.findall(".//h:HVAC/h:HVACPlant/h:HeatPump", ns)
    if len(heat_pumps) > 0:
        return True

    # Electric HeatingSystem = likely electric resistance
    for system in root.findall(".//h:HVAC/h:HVACPlant/h:HeatingSystem", ns):
        fuel = system.findtext(
            "h:HeatingSystemFuel",
            default="N/A",
            namespaces=ns
        )

        if fuel not in excluded_hvac_fuels:
            return True

    return False


def has_allowed_water_heater(input_dir):
    root, ns = get_root_and_ns(input_dir)

    for wh in root.findall(".//h:WaterHeating/h:WaterHeatingSystem", ns):
        fuel = wh.findtext("h:FuelType", default="N/A", namespaces=ns)
        wh_type = wh.findtext("h:WaterHeaterType", default="N/A", namespaces=ns)

        if fuel == "electricity" and wh_type in allowed_water_heater_types:
            return True

    return False


results = []

for building_dir in src_dir.iterdir():
    if not building_dir.is_dir():
        continue

    building_id = building_dir.name
    input_dir = building_dir / upgrade

    has_files, missing_files = has_required_files(input_dir)

    row = {
        "building_id": building_id,
        "input_dir": str(input_dir),
        "missing_files": ", ".join(missing_files),
        "has_required_files": has_files,
        "allowed_hvac": False,
        "allowed_water_heater": False,
        "ready_for_ochre": False,
    }

    if has_files:
        row["allowed_hvac"] = has_allowed_hvac(input_dir)
        row["allowed_water_heater"] = has_allowed_water_heater(input_dir)

    row["ready_for_ochre"] = (
        row["has_required_files"]
        and row["allowed_hvac"]
        and row["allowed_water_heater"]
    )

    results.append(row)


df = pd.DataFrame(results)

print("\nRequired files:")
print(df["has_required_files"].value_counts())

print("\nAllowed HVAC:")
print(df["allowed_hvac"].value_counts())

print("\nAllowed water heater:")
print(df["allowed_water_heater"].value_counts())

print("\nFinal ready buildings:")
print(df["ready_for_ochre"].value_counts())

df.to_csv("ochre_filter_report.csv", index=False)
print("\nSaved report to: ochre_filter_report.csv")


excluded_dir.mkdir(parents=True, exist_ok=True)

exclude_ids = (
    df.loc[df["ready_for_ochre"] == False, "building_id"]
      .astype(str)
      .tolist()
)

moved = 0
missing = 0

for building_id in exclude_ids:
    src = src_dir / building_id
    dst = excluded_dir / building_id

    if not src.exists():
        print(f"Missing folder: {src}")
        missing += 1
        continue

    if dst.exists():
        print(f"Already moved/skipping: {dst}")
        continue

    shutil.move(str(src), str(dst))
    moved += 1
    print(f"Moved: {building_id}")

print(f"\nMoved {moved} excluded building folders.")
print(f"Missing folders: {missing}")
print(f"Kept {df['ready_for_ochre'].sum()} ready buildings in {src_dir}")