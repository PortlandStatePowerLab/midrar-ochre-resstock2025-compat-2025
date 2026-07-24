import pandas as pd
from pathlib import Path

csv = Path("../load_profiles/cosimulation2/436076/up00/simulation_results_cooling/ochre.csv")

df = pd.read_csv(csv)

print(df.tail())
print(df.columns.tolist())

keywords = ["cool", "temp", "setpoint", "hvac", "indoor"]

for col in df.columns:
    if any(k in col.lower() for k in keywords):
        print(col)


import matplotlib.pyplot as plt

cols = [
    col for col in df.columns
    if any(k in col.lower() for k in ["cool", "temp", "setpoint", "indoor"])
]

df_tail = df.tail(24 * 60)  # last day before failure

df_tail[cols].plot(figsize=(12, 6))
plt.title("Building 436076 Cooling Failure Diagnostic")
plt.xlabel("Timestep")
plt.grid(True, alpha=0.3)
plt.tight_layout()
plt.show()
