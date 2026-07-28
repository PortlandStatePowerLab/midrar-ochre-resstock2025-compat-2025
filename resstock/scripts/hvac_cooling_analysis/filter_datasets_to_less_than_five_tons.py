'''
Author: MidrarAdham
Created: Tue Jul 28 2026
'''
import os
import json
import pandas as pd
from pathlib import Path
from pprint import pprint as pp

src_dir = Path('./outputs/hvac_state_diagnostics.csv')
output_dir = Path('../../filtered_data/')

df = pd.read_csv (src_dir)
up2_df = (df[df['upgrade'] == 'up02']).reset_index ()
less_five_tons_df = up2_df[up2_df['cooling_capacity_tons'] < 5.0]

print(less_five_tons_df['cooling_capacity_tons'])

print('\n\n------------------\n\n')

less_five_tons_df = (less_five_tons_df[less_five_tons_df['service'] == 'cooling']).reset_index ()

print(less_five_tons_df.columns)

print('\n\n------------------\n\n')

less_five_tons_df[['building_id','timeseries_file']].dropna(subset='timeseries_file').to_csv ('less_than_five_tons_resstock_2024.csv', index=False)

less_five_tons_df = (less_five_tons_df[['building_id','timeseries_file']].dropna(subset='timeseries_file')).reset_index()

