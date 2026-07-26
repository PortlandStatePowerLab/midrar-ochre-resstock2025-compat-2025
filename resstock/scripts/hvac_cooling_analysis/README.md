# HVAC Cooling Analysis Workflow

This README explains the order for running the HVAC cooling analysis scripts.

The workflow is designed for the ResStock 2024 / OCHRE 2024.2 cooling simulations. The current analysis focuses on **cooling only**, especially the OCHRE output column:

```text
HVAC Cooling Electric Power (kW)
```

The scripts should be run in order because later scripts depend on CSV files created by earlier scripts.

---

## Folder assumptions

The scripts assume this general project structure:

```text
project/
├── ochre-resstock2025-compat/
│   └── resstock/
│       └── scripts/
│           ├── hvac_cooling_analysis/
│           |   ├── script_1/
│           |   ├── script_2/
│           |   ├── script_3/
│           |   └── script_#/
└──---------└── outputs/
```

Most recent scripts use:

```python
analysis_dir = Path("./outputs")
```

Before running the scripts, make sure the dataset drive is mounted and that the paths in each script match your local folder structure.

---

## Recommended run order

Run the scripts in this order:

```bash
python scan_ochre_results.py
python extract_hvac_metadata.py
python build_canonical_electric_hvac_devices.py
python build_hvac_state_diagnostics.py
python plot_cooling_hvac_analysis.py
python plot_cooling_capacity_bins.py
python build_daily_cooling_metrics.py
python plot_daily_cooling_metrics.py
python sweep_cooling_kw_bins.py
```

---

## Step 1: Scan OCHRE simulation results

Script:

```text
scan_ochre_results.py
```

Purpose:

This script scans the ResStock/OCHRE simulation folders for each building and upgrade. It checks whether each simulation has the expected files and whether the OCHRE time-series output contains heating and cooling columns.

Main input:

```text
datasets/resstock_2024/cosimulation/
```

Main output:

```text
outputs/ochre_result_inventory.csv
```

What it tells you:

```text
which buildings have up00, up01, up02 results
which buildings have home.xml
which buildings have in.schedules.csv
which buildings have ochre.json
which buildings have ochre.parquet or ochre.csv
whether the HVAC Cooling Electric Power (kW) column exists
whether the simulation result looks complete
```

Run this first because all later scripts depend on knowing which simulations are usable.

---

## Step 2: Extract HVAC metadata

Script:

```text
extract_hvac_metadata.py
```

Purpose:

This script extracts HVAC equipment information from each building's metadata files. It reads the HPXML `home.xml` files and OCHRE equipment metadata.

Main input:

```text
outputs/ochre_result_inventory.csv
```

Main output:

```text
outputs/hvac_metadata.csv
```

What it tells you:

```text
equipment type
fuel type
heating system information
cooling system information
heat pump information
cooling capacity
heating capacity
backup system fields, when available
```

This is still a raw metadata extraction step. Do not use this file directly as the cleaned device population.

---

## Step 2b: Build canonical electric HVAC device table

Script:

```text
build_canonical_electric_hvac_devices.py
```

Purpose:

This script converts the raw metadata into a cleaner one-row-per-device table for electric HVAC analysis.

Main input:

```text
outputs/hvac_metadata.csv
```

Main outputs:

```text
outputs/canonical_electric_hvac_devices.csv
outputs/hvac_metadata_with_electric_filter_flags.csv
```

What it does:

```text
keeps electric HVAC devices
keeps heat pumps as electric HVAC candidates
removes fossil-fuel HVAC devices from the electric HVAC analysis
assigns device_type
assigns service_type
adds inclusion/exclusion flags
```

Why this matters:

The cooling analysis should not mix electric cooling devices with non-electric HVAC equipment. This step defines the cleaned electric HVAC population used later.

---

## Step 3: Build HVAC state diagnostics

Script:

```text
build_hvac_state_diagnostics.py
```

Purpose:

This script reads the OCHRE time-series data and computes state-based diagnostics for each building, upgrade, and service.

Main inputs:

```text
outputs/ochre_result_inventory.csv
outputs/canonical_electric_hvac_devices.csv
```

Main output:

```text
outputs/hvac_state_diagnostics.csv
```

Main metrics:

```text
duty_cycle
total_on_minutes
total_off_minutes
n_on_events
n_off_events
n_switching_events
mean_on_duration_minutes
max_on_duration_minutes
total_energy_kwh
avg_kw
peak_kw
```

Important flags:

```text
include_in_device_population
include_in_active_operation_plots
include_in_ols_candidate_pool
```

For the cooling analysis, most later scripts use:

```text
service = cooling
include_in_active_operation_plots = True
```

This step is the main bridge between raw simulation output and analysis-ready metrics.

---

## Step 4: Plot overall cooling HVAC analysis

Script:

```text
plot_cooling_hvac_analysis.py
```

Purpose:

This script creates the first set of cooling-only figures.

Main inputs:

```text
outputs/hvac_state_diagnostics.csv
outputs/canonical_electric_hvac_devices.csv
```

Main output folder:

```text
outputs/figures/cooling
```

Main figures:

```text
cooling device population by upgrade
active cooling operation population by upgrade
diagnostic flags by upgrade
cooling duty cycle by upgrade
monthly cooling energy by upgrade
observed peak cooling kW by upgrade
cooling switching events by upgrade
cooling capacity vs observed peak kW
cooling duty cycle vs monthly energy
active cooling devices by upgrade and device type
```

Use this step to understand the broad differences between `up00`, `up01`, and `up02`.

---

## Step 5: Plot cooling capacity-bin analysis

Script:

```text
plot_cooling_capacity_bins.py
```

Purpose:

This script compares cooling devices within cooling capacity bins.

Main input:

```text
outputs/hvac_state_diagnostics.csv
```

Main output folder:

```text
outputs/figures/cooling_capacity_bins
```

Capacity bins:

```text
0-1 tons
1-2 tons
2-3 tons
3-4 tons
4-5 tons
5+ tons
```

Main figures:

```text
active cooling case counts by capacity bin
active cooling case counts by observed peak kW bin
median peak kW by cooling capacity bin
median monthly cooling energy by capacity bin
median cooling duty cycle by capacity bin
median switching events by capacity bin
cooling capacity vs observed peak kW with OLS trendlines
capacity-bin by peak-kW-bin heatmaps
```

Why this step matters:

This step checks whether the upgrade differences are only caused by different equipment sizes. The results showed that capacity alone is not the best binning variable for the OLS-Bayesian problem because devices with similar cooling capacity can have very different electrical behavior.

---

## Step 6: Build daily cooling metrics

Script:

```text
build_daily_cooling_metrics.py
```

Purpose:

This script creates daily metrics from the one-minute cooling time series.

Main input:

```text
outputs/hvac_state_diagnostics.csv
```

Main outputs:

```text
outputs/daily_cooling_metrics.csv
outputs/daily_cooling_metric_failures.csv
```

Each row represents:

```text
building_id + upgrade + day
```

Main metrics:

```text
daily_energy_kwh
daily_peak_kw
daily_avg_kw
daily_on_minutes
daily_off_minutes
daily_duty_cycle
daily_switching_events
daily_peak_kw_per_ton
daily_kwh_per_ton
daily_switching_events_per_on_hour
daily_activity_flag
```

Important definition:

A device is considered ON when:

```text
HVAC Cooling Electric Power (kW) > 0.3
```

The daily activity flags are:

```text
active_day
near_never_on_day
near_always_on_day
off_all_day
```

Run this before any daily plotting.

---

## Step 7: Plot daily cooling metrics

Script:

```text
07_plot_daily_cooling_metrics.py
```

Purpose:

This script creates daily cooling figures using the daily metrics table.

Main input:

```text
outputs/daily_cooling_metrics.csv
```

Main output folder:

```text
outputs/figures/daily_cooling_metrics
```

Main figures:

```text
daily activity flag counts by upgrade
daily activity flag percentages by upgrade
median daily cooling energy by upgrade
median daily peak kW by upgrade
median daily duty cycle by upgrade
median daily switching events by upgrade
median daily peak kW per ton by upgrade
median daily kWh per ton by upgrade
median switching events per ON-hour by upgrade
daily kWh per ton boxplot by upgrade
daily peak kW per ton boxplot by upgrade
daily switching rate boxplot by upgrade
binned daily peak kW per ton
binned daily kWh per ton
binned daily duty cycle
binned daily switching rate
```

Important setting:

```text
minimum_on_minutes_for_switching_rate = 10
```

This is used for switching-rate plots because the OLS model uses 10-minute windows. The metric should only be computed on days where the device was ON long enough to be relevant to the OLS time scale.

---

## Step 8: Sweep cooling kW bins

Script:

```text
08_sweep_cooling_kw_bins.py
```

Purpose:

This script tests different observed electrical-kW bin definitions for transformer-level OLS/Bayesian aggregation.

Main inputs:

```text
outputs/hvac_state_diagnostics.csv
outputs/daily_cooling_metrics.csv
```

Main output folder:

```text
outputs/kw_bin_sweep
```

Main outputs:

```text
outputs/kw_bin_sweep/cooling_kw_bin_sweep_summary.csv
outputs/kw_bin_sweep/cooling_kw_bin_sweep_groups.csv
outputs/kw_bin_sweep/cooling_kw_bin_sweep_bootstrap.csv
outputs/kw_bin_sweep/cooling_kw_bin_sweep_bootstrap_by_sample_size.csv
outputs/kw_bin_sweep/cooling_kw_bin_sweep_excluded_large_devices.csv
```

Main figure folder:

```text
outputs/kw_bin_sweep/figures
```

Main idea:

The OLS-Bayesian setup struggles when the number of devices is small. Since the transformer-level problem may only involve a few HVAC devices, this script tests realistic group sizes:

```text
2, 3, 4, 5, 6, 8, 10, 13 devices
```

The script compares different binning schemes by repeatedly sampling small groups of devices from each bin.

For each sampled group:

```text
actual aggregate peak kW = sum(sampled device peak_kw)

predicted aggregate peak kW = group_size * median peak_kw of that bin
```

The error is used as a bin-quality diagnostic.

Main QC filter:

```text
cooling_capacity_tons <= 5
```

Devices above 5 tons are excluded from the main sweep because they are unusually large for residential systems and can dominate small transformer-level groups. They are saved separately for review.

Important interpretation:

This is not the final OLS-Bayesian model. It is a diagnostic to decide which bin definitions are more stable for small transformer groups.

---

## Full workflow interpretation

The workflow moves from raw simulation files to increasingly targeted analysis:

```text
simulation availability
    ↓
HVAC metadata
    ↓
canonical electric HVAC devices
    ↓
monthly state diagnostics
    ↓
cooling population and operation plots
    ↓
capacity-bin analysis
    ↓
daily metrics
    ↓
daily plots
    ↓
kW-bin sweep for transformer-level aggregation
```

The main conclusion from the workflow so far is:

```text
Electrical kW is a better binning variable than cooling capacity for the OLS-Bayesian aggregation problem.
```

Cooling capacity is still useful for describing equipment size, but the model is trying to predict electric power. Therefore, observed electrical behavior, especially peak cooling kW and normalized kW metrics, is more relevant for binning.

---

## Notes for future work

### Heat pumps with electric backup

A later metadata/QC step should explicitly inspect heat pumps with electric backup in the ResStock 2024 dataset.

Questions to answer:

```text
How many heat pumps have electric backup?
Which upgrades contain these devices?
What is their backup capacity?
Do they create high-kW heating events?
Should they be binned separately for heating analysis?
```

This is mostly a heating-side question, not a cooling-side question, but it should be documented before finalizing the HVAC flexibility model.

### Transformer-specific analysis

The kW-bin sweep is still a bin-quality diagnostic. The next major step is to connect these bins to actual transformer assignments:

```text
25 kVA transformer
50 kVA transformer
75 kVA transformer
```

For each transformer size, the analysis should test:

```text
number of houses
number of active HVAC devices
aggregate observed kW
predicted aggregate kW from bins
OLS/Bayesian prediction error
```

This will connect the device-level binning results directly to the transformer-level research question.

---

## Quick troubleshooting

### Problem: daily metrics output has zero rows

Most likely causes:

```text
dataset drive is not mounted
timeseries_file paths are invalid
script is reading the wrong outputs folder
include_in_active_operation_plots was saved as text instead of boolean
```

Check the debug output from:

```bash
python build_daily_cooling_metrics.py
```

Look at:

```text
Cooling active flag values
Active cooling devices to process
Failures
```

### Problem: missing OCHRE files

Check:

```text
outputs/ochre_result_inventory.csv
```

Look at:

```text
has_timeseries_file
timeseries_format
has_cooling_col
simulation_status
```

### Problem: too many unrealistic cooling capacities

Check:

```text
outputs/kw_bin_sweep/cooling_kw_bin_sweep_excluded_large_devices.csv
```

This file lists devices excluded from the primary kW-bin sweep because:

```text
cooling_capacity_tons > 5
```

---

## Current recommended main analysis settings

```text
Cooling ON threshold:
    0.3 kW

Daily switching-rate minimum ON time:
    10 minutes

Primary kW-bin sweep population:
    active cooling devices with cooling_capacity_tons <= 5

Transformer group sizes:
    2, 3, 4, 5, 6, 8, 10, 13 devices

Primary binning variable:
    observed monthly peak cooling kW

Preferred exploratory binning method:
    pooled quantile kW bins

Preferred practical comparison:
    fixed engineering kW bins
```
