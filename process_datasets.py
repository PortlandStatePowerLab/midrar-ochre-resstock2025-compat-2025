import os
import time
import numpy as np
import pandas as pd
import seaborn as sns
from matplotlib import ticker
import matplotlib.pyplot as plt
from tabulate import tabulate as tbl



def make_it_good (df):
    return tbl(tabular_data=df)


df = pd.read_csv('./OR_upgrade0.csv', low_memory=False)


df_city = df.groupby(by='in.city')

for id, group in df_city:
    if id == 'OR, Portland':
        df_weather = group


# Sort the data by bedrooms number:
df_weather = df_weather.sort_values(by='in.bedrooms', ascending=True)
df_weather = df_weather.reset_index()

# Clean up columns. Keep only power consumption columns
print(len(df_weather))
df_weather.to_csv('./OR_upgrade0_filtered.csv', index=False)
quit()
keep_cols = [col for col in df_weather.columns if 'kwh' in col]

def plots (df, title):
    fig, ax = plt.subplots(figsize=(8,5))
    sns.barplot(data=df, x=df.columns[0], y=df.columns[1], palette='viridis', ax=ax)
    plt.title(title)
    # ax.set_xticks(np.arange(0, len(df), 50))
    plt.xticks(rotation=90)
    fig.tight_layout()
    plt.show()

for col in keep_cols:
    new_df = (df_weather[col].value_counts(normalize=True)*100).reset_index()
    x = input('Plot the data?')

    # if x =='y':
        # plots(df=new_df, title=col)










# Checking process - The above script is cleaned. Below is the mess I went through
# ===============================================
# It does not seem like there are other words than Baseline.

# x = df['in.upgrade_name'].unique()
# x = [i for i in x if i != 'Baseline']
# ===============================================

# ===============================================
# Sorting by city is better. When doing that, there are many weather files in there.
# So we sort by the city, then sort by the weather file (portland intl arpt)

# print(df[['in.city','in.weather_file_city']])
# ===============================================

# EV analysis:

def plots (df, title):
    sns.barplot(data=df, x=df.columns[0], y=df.columns[1], palette='viridis')
    plt.title(title)

# 1) EV types and portion % in the data set
# evs_type = (df_weather['in.electric_vehicle_battery'].value_counts(normalize=True)*100).reset_index()
# evs_type['in.electric_vehicle_battery'] = evs_type['in.electric_vehicle_battery'].apply(lambda x: x.split(',')[0])
# evs_type.columns = ['SUV Type', 'data portion (%)']
# plt.figure(figsize=(8,5))


# evs_chrg_home = (df_weather['in.electric_vehicle_charge_at_home'].value_counts(normalize=True)*100).reset_index()
# evs_chrg_home.columns = ['charge at home', 'portion of the data (%)']
# print(evs_chrg_home)
# plots(df=evs_chrg_home)
# plt.grid()
# plt.savefig('./charging at home.png')
# plt.show()

# heating_fule = (df_weather['in.heating_fuel'].value_counts(normalize=True)*100).reset_index()
# plots(df=heating_fule)
# plt.show()
# ===============================================

