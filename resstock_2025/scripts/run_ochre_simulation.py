import os
from pathlib import Path
from ochre.cli import create_dwelling
from ochre.utils import default_input_path


def _filter_datasets (input_path):
    target_file = input_path / 'in.schedules.csv'
    if target_file.is_file() and target_file.stat().st_size > 0:
        return input_path
    
    else:
        print('file does not exist')

root = Path (__file__).resolve().parent
dataset_dir = root.parent / 'load_profiles' / 'cosimulation'
upgrades = ['up00']
input_paths = [files / upgrades[0] for files in dataset_dir.iterdir()]

default_weather_file_name = "USA_OR_Portland.Intl.AP.726980_TMY3.epw"
default_weather_file = os.path.join(default_input_path, "Weather", default_weather_file_name)

for input_path in input_paths:

    input_file = _filter_datasets (input_path)
    if input_file is None:
        continue


    dwelling = create_dwelling (
        input_path=str(input_file),
        start_year=2025,
        start_month=1,
        start_day=1,
        initialization_time=1,
        time_res= 60,
        duration= 1,
        weather_file_or_path=str(default_weather_file),
        # output_path=output_dir,
        )
    dwelling.simulate()
