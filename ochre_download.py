'''
Author: Midrar Adham
Date: 11/01/2025

This script processes and downloads the ResStock 2025 dataset.
The 2025 dataset has different root than the previous versions.
Therefore, there are some adjustments needed for the Analysis.py
source code located in ~/.local/lib/python3.12/site-packages/ochre/Analysis.py

REQUIREMENTS:

- Download the OR_upgrades.csv file and make sure it is in the same 
path as this script.

- Make sure to copy Analysis.py in this folder to ~/.local/lib/python3.12/site-packages/ochre/
'''

import os
import pandas as pd
from pathlib import Path
from ochre import Analysis


def process_metdata (original_data):
    # Read the file
    df = pd.read_csv(original_data, low_memory=False)

    # Group by the city column
    df_city = df.groupby(by='in.city')

    # Identify Portland and save its data
    for id, group in df_city:
        if id == 'OR, Portland':
            df_weather = group


    # Sort the data by bedrooms number:
    df_weather = df_weather.sort_values(by='in.bedrooms', ascending=True)
    df_weather = df_weather.reset_index()

    # Not needed, but in case. Write the updated file to a csv so we can download the load files using ochre
    # df_weather.to_csv('./OR_upgrade0_filtered.csv', index=False)

    return df_weather


def create_dir():
    '''
    This function is called in process_metadata

    From ochre developers: 
        Create a folder called 'cosimulation' to store all files
    '''
    
    main_path = os.path.join(os.getcwd(), "cosimulation")
    os.makedirs(main_path, exist_ok=True)
    return main_path

def download_files (filtered_data):
    # Get the main path of where we're storing the new files
    main_path = create_dir()

    # Read the filtered data
    # df = pd.read_csv(filtered_data,usecols=['bldg_id'])
    building_ids = filtered_data['bldg_id'].to_list()
    upgrades = ["up00"]

    i = 0
    for building in building_ids:

        for upgrade in upgrades:
            i += 1

            input_path = os.path.join(main_path, str(building), upgrade)
            os.makedirs(input_path, exist_ok=True)
            Analysis.download_resstock_model(building_id=building,upgrade_id=upgrade,
                                            local_folder=input_path, overwrite=False,
                                            year="2025", release="resstock_amy2018_release_1")
            print(f"Run number {i} is done for building {building}/{upgrade}")
    
    return main_path

# def check_dir (main_path):
#     print(len(os.listdir(main_path)))
#     root = Path(main_path)
#     for f in root.rglob('in.schedules.csv'):
        
#         if f.is_file():
#             print(len(os.listdir(main_path)))
#         else:
#             print(f)

if __name__ == '__main__':
    
    metadata = './OR_upgrade0.csv'
    df = process_metdata(original_data=metadata)
    df = df.drop('index', axis=1)
    main_path = download_files(filtered_data=df)
    # main_path = create_dir()
    # check_dir(main_path=main_path)