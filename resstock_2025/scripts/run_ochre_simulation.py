'''
Author: Midrar Adham
Created: Thu Jul 09 2026
'''

import os
import datetime as dt
from pathlib import Path
from ochre.cli import create_dwelling
from ochre.utils import default_input_path
import ochre.utils.units as ochre_units

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

for building_dir in dataset_dir.iterdir():

    if not building_dir.is_dir():
        continue

    input_path = building_dir / upgrade

    if not is_ready_for_ochre(input_path):
        print(f"Skipping incomplete building: {building_dir.name}")
        continue

    output_dir = input_path / "simulation_results"

    print(f"Running one-minute test for: {building_dir.name}")

    dwelling = create_dwelling(
        input_path=str(input_path),
        start_year=2025,
        start_month=1,
        start_day=1,
        initialization_time=1,
        time_res=1,
        duration=30,
        weather_file_or_path=str(default_weather_file),
        output_path=str(output_dir),
    )

    dwelling.simulate()

    print(f"Finished: {building_dir.name}")
    # break