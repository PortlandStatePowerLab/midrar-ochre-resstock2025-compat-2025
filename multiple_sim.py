import os
import shutil
import numpy as np
import pandas as pd
import datetime as dt
from ochre import Analysis, Dwelling
from ochre.utils import default_input_path
from ochre.cli import create_dwelling, limit_input_paths, run_multiple_local, run_multiple_hpc


# 1) Run multiple simulations: Three house instances
# 2) Run multiple simulations: Three houses + one EV in each of them
# 3) Run multiple simulations: Try the run_multiple_local thing

default_weather_file_name = "USA_OR_Portland.Intl.AP.726980_TMY3.epw"
default_weather_file = os.path.join(default_input_path, "Weather", default_weather_file_name)

def compile_results (main_path, n_max=None):
    output_path = os.path.join(main_path, "compiled")
    os.makedirs(output_path, exist_ok=True)
    print("Compiling OCHRE resutls for:", main_path)

    # Find all building folders
    required_files = ["ochre_complete"]
    run_paths = Analysis.find_subfolders(main_path, required_files)
    n = len(run_paths)

    # ensure at least 1 run folders
    if not n:
        print("No buildings found in:", main_path)
        return
    else:
        print(f"Found {n} completed simulations in:", main_path)
    
    if n_max is not None and n > n_max:
        print(f"Limiting number of runs to {n_max}")
        run_paths = run_paths[:n_max]
        n = n_max
    
    run_names = {os.path.relpath(path, main_path): path for path in run_paths}

    # combine input json files
    json_files = {name: os.path.join(path, "ochre.json") for name, path in run_names.items()}
    df = Analysis.combine_json_files(json_files)
    df.to_csv(os.path.join(output_path, "all_ochre_inputs.csv"))

    # combine metrics files
    metrics_files = {
        name: os.path.join(path, "ochre_metrics.csv") for name, path in run_names.items()
    }
    df = Analysis.combine_metrics_files(metrics_files)
    df.to_csv(os.path.join(output_path, "all_ochre_metrics.csv"))

    # combine single time series column for each house (e.g., total electricity consumption)
    results_files = {name: os.path.join(path, "ochre.csv") for name, path in run_names.items()}
    df = Analysis.combine_time_series_column("Total Electric Power (kW)", results_files)
    df.to_csv(os.path.join(output_path, "all_ochre_total_powers.csv"))

    # aggregate time series data across all simulations
    df = Analysis.combine_time_series_files(results_files, agg_type="House")
    df.to_csv(os.path.join(output_path, "all_ochre_results.csv"))

    print("Saved OCHRE results to:", output_path)

def filter_datasets(dataset_path):
    '''
    This function looks into the ResStock datasets, checks buildings with no in.schedules.csv file,
    and ignore them. It also remove building IDs with empty in.schedules.csv

    The fuction returns a list of building IDs that have in.schedules.csv file

    TODO: Remove this function from here. It takes so much time. Also, this is bad implementation
    '''
    missing = []
    exists = []
    for folder in os.listdir(dataset_path):
        upgrade_path = os.path.join(dataset_path, folder, 'up00')
        if os.path.isdir(upgrade_path):
            target_file = os.path.join(upgrade_path, 'in.schedules.csv')
            if os.path.isfile(target_file):
                "Checking if in.schedules.csv is empty or not"
                try:
                    df = pd.read_csv(target_file)
                    bldg_id = upgrade_path.split('/')[-2]
                    exists.append(bldg_id)
                except pd.errors.EmptyDataError:
                    missing.append(bldg_id)
            else:
                "Checking if in.schedules.csv exists"
                missing.append(bldg_id)
    # exists is just a list of building IDs.
    return exists
    

def create_sim_times ():
    start_time = dt.datetime(2025, 1, 1)           # Start date
    time_res = dt.timedelta(minutes=1)            # Time step = 1 minutes
    duration = dt.timedelta(days=1)                # Simulate 1 day
    sim_times = pd.date_range(
        start_time,
        start_time + duration,
        freq=time_res,
        inclusive="left",
    )
    return start_time, time_res, duration, sim_times

if __name__ == "__main__":
    main_path = os.getcwd()
    dataset = '/home/deras/gld-opedss-ochre-helics/datasets/cosimulation/'
    buildings = filter_datasets(dataset_path=dataset)
    start_time, time_res, duration, sim_times = create_sim_times()
    # buildings = ['451658']
    input_paths = []
    upgrades = ["up00"]
    for upgrade in upgrades:
        for building in buildings:
            input_path = os.path.join(dataset, building, upgrade)
            input_paths.append(input_path)
    
    for input_path in input_paths:
        output_file_name = f"out_{input_path.split('/')[-2]}_{input_path.split('/')[-1]}"
        dwelling = Dwelling (
            verbosity = 8,
            name = output_file_name,
            initialization_time = dt.timedelta(days=1),
            # output_path = './output_path/',
            save_results = True,
            start_time = start_time,
            time_res = time_res,
            duration = duration,
            hpxml_file = os.path.join(input_path, "home.xml"),
            hpxml_schedule_file = os.path.join(input_path, "in.schedules.csv"),
            weather_file = default_weather_file,
            equipment_args = {},
        )
        dwelling.simulate()