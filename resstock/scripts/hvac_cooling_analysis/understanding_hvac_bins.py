'''
Author: Midrar Adham
Created: Sun Jul 26 2026
'''
import pandas as pd
import numpy as np
from pathlib import Path
import matplotlib.pyplot as plt

diagnostics_file = Path("./outputs/hvac_state_diagnostics.csv")

df = pd.read_csv(diagnostics_file)

print

# Keep cooling active rows.
df = df[
    (df["service"] == "cooling")
    & (df["include_in_active_operation_plots"] == True)
].copy()

# Convert numeric columns.
df["peak_kw"] = pd.to_numeric(df["peak_kw"], errors="coerce")
df["cooling_capacity_tons"] = pd.to_numeric(df["cooling_capacity_tons"], errors="coerce")

# Match the sweep filter.
df = df[
    (df["cooling_capacity_tons"].isna())
    | (df["cooling_capacity_tons"] <= 5)
].copy()

df = df.dropna(subset=["peak_kw"])

df_tmp = (df[['service', 'upgrade', 'peak_kw']]).reset_index()

df_tmp = df_tmp[df_tmp['service'] == 'cooling']

df_tmp = (df_tmp[df_tmp['upgrade'] == 'up02']).reset_index()

# These are the percentiles for 8 quantile bins.
percentiles = np.linspace(0, 1, 5)

edges = df_tmp["peak_kw"].quantile(percentiles)

print("Percentile edges for pooled 8-bin scheme:")
for p, edge in zip(percentiles, edges):
    print(f"{p * 100:5.1f}% percentile: {edge:.4f} kW")
