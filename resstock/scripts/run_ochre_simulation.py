'''
Author: Midrar Adham
Created: Thu Jul 09 2026
'''

import os
import pandas as pd
import datetime as dt
from pathlib import Path
from ochre.cli import create_dwelling
from ochre.utils import default_input_path
import ochre.utils.units as ochre_units


"""
This only happened for cooling systems simulation:

- These buildings are excluded because they don't have a cooling system, causing COHRE to produce this error: 

ochre.Models.StateSpaceModel.ModelException: Envelope temperatures are outside acceptable range.
Indoor temp=50.02785938402305. Extreme temps: {}
"""

excluded_bldg = ["436076", "324807", "39511", "278662", "536626"]

try:
    ochre_units.ureg.define("inch_H2O_39F = 249.08891 * pascal")
except Exception as e:
    if "Cannot redefine" not in str(e):
        raise


def is_ready_for_ochre(input_path):
    required_files = ["home.xml", "in.schedules.csv"]

    for file_name in required_files:
        file_path = input_path / file_name
        if not file_path.is_file() or file_path.stat().st_size == 0:
            return False

    return True


root = Path(__file__).resolve().parent

dataset_dir = root.parent / "load_profiles" / "cosimulation2"
upgrade = "up00"

default_weather_file_name = "USA_OR_Portland.Intl.AP.726980_TMY3.epw"
default_weather_file = os.path.join(
    default_input_path,
    "Weather",
    default_weather_file_name
)

failed_buildings = []
finished_buildings = []
skipped_buildings = []

for building_dir in dataset_dir.iterdir():

    if not building_dir.is_dir():
        continue

    building_id = building_dir.name

    if building_id in excluded_bldg:
        print(f"Excluding building {building_id} ...")
        skipped_buildings.append({
            "building_id": building_id,
            "reason": "manually_excluded",
        })
        continue

    input_path = building_dir / upgrade

    if not is_ready_for_ochre(input_path):
        print(f"Skipping incomplete building: {building_id}")
        skipped_buildings.append({
            "building_id": building_id,
            "reason": "missing_home_xml_or_schedules",
        })
        continue

    output_dir = input_path / "simulation_results_cooling"

    print(f"\nRunning one-minute cooling simulation for: {building_id}")

    try:
        dwelling = create_dwelling(
            input_path=str(input_path),
            start_year=2025,
            start_month=6,
            start_day=1,
            initialization_time=1,
            time_res=1,
            duration=90,
            weather_file_or_path=str(default_weather_file),
            output_path=str(output_dir),
        )

        dwelling.simulate()

        print(f"Finished: {building_id}")
        finished_buildings.append(building_id)

    except Exception as e:
        print(f"FAILED: {building_id}")
        print(f"Reason: {type(e).__name__}: {e}")

        failed_buildings.append({
            "building_id": building_id,
            "error_type": type(e).__name__,
            "error_message": str(e),
        })

        continue

print("\n==============================")
print("OCHRE cooling simulation report")
print("==============================")

print(f"Finished buildings: {len(finished_buildings)}")
print(f"Failed buildings:   {len(failed_buildings)}")
print(f"Skipped buildings:  {len(skipped_buildings)}")

if failed_buildings:
    print("\nFailed building IDs:")
    for item in failed_buildings:
        print(
            f"- {item['building_id']}: "
            f"{item['error_type']} - {item['error_message']}"
        )

if skipped_buildings:
    print("\nSkipped building IDs:")
    for item in skipped_buildings:
        print(f"- {item['building_id']}: {item['reason']}")

if failed_buildings:
    pd.DataFrame(failed_buildings).to_csv(
        "failed_cooling_buildings.csv",
        index=False,
    )

if skipped_buildings:
    pd.DataFrame(skipped_buildings).to_csv(
        "skipped_cooling_buildings.csv",
        index=False,
    )

if finished_buildings:
    pd.DataFrame({"building_id": finished_buildings}).to_csv(
        "finished_cooling_buildings.csv",
        index=False,
    )