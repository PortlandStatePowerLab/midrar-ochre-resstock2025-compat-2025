# Using OCHRE with ResStock 2025 Dataset
## Brief Intro

OCHRE's [Jupyter Notebook](https://github.com/NREL/OCHRE/blob/main/notebook/user_tutorial.ipynb) uses a dataset that is compatible with OCHRE modules. However, downloading another version of ResStock causes some errors when running simulations. This repo uses [ResStock 2025 dataset](https://resstock.nrel.gov/datasets), and shows the fixes that needs to be addressed in order to run a simulation with the aforementioned dataset.

## Download the ResStock 2025:

### Setup:

- Copy the **Analysis.py** to OCHRE's installation directory
- Make sure you download the needed metadata file from [ResStock 2025 dataset](https://resstock.nrel.gov/datasets)
    - In this repository, **OR_upgrade0.csv** is downloaded.
- Run the **ochre_download.py**:
~~~sh
python3 ochre_download.py
~~~

# About ResStock 2025:
The ResStock 2025 include many improvements to the envelope and other aspects of weather and dwelling behavior. However, some of the buildings do not include **in.schedules.csv** files, or they are included but empty. As such, these profiles need to be processed with cautious. Below are some of the errors encountered and the attempted fixes.


### Errors & Fixes:
As of today's date (11/11/2025), the fixes in this repo only consider upgrade 00 (up00). Other upgrades have not yet to be processed.

### Structure of this directory:

The 2025 ResStock dataset is downloaded in /gld-opedss-ochre-helics/datasets/.

### tl;dr:
- Copy the envelope.py, hpxml.py, and the Analysis.py files in this directory to OCHRE installtion directory:
    - /home/deras/.local/lib/python3.12/site-packages/ochre/utils, or whichever directory OCHRE is installed.

### Compatibility between OCHRE and ResStock 2025 dataset:
ResStock 2025 provides detailed building envelope and equipment data derived from newer EnergyPlus and HPXML conventions. However, OCHRE was designed around an earlier HPXML structure that expects unique boundary enteries and specific combinations of **Construction Type, Finish Type, and Insulation Details** that are defined in its internal CSV database. As such, OCHRE interprets most of ResStock fields correctly, but it encounters mismatches where ResStock introduces new material descripions or multiple geometric segments for the same boundary category.

The minor additions of this repository is addressed by adding ifnore lists for unsupported combinations and summing multiple area enteries. Therefore, we restore the functional compatibility without changing OCHRE's thermal-modeling logic, which allow users to run ResStock 2025 houses in OCHRE simulations with consistent envelope and RC parameters.

## Error Messages and fixes:

### Error 1:

~~~sh
HTTP: 404 Error - The exact error message was not recorded.
~~~

### Fix:

The OEDI path is different from one ResStock version to the other. The fix proposed here is to identify the version of the needed ResStock dataset. This is done using the following lines within the Analysis.py:

~~~sh
    base = [
        "nrel-pds-building-stock",
        "end-use-load-profiles-for-us-building-stock",
        year,
        release,
        ]

    # 2024-style vs 2025-style layout
    if year == "2025" and release == "resstock_amy2018_release_1":
        sub = ["building_energy_models", f"upgrade={upgrade_id}"]
    else:
        sub = ["model_and_schedule_files", "building_energy_models", f"upgrade={upgrade_id}"]

    zip_name = f"{building_id}-{upgrade_str}.zip"
    oedi_path = "/".join(base + sub + [zip_name])
~~~

### Error 2:
There are so many errors, such as the following, that were addressed using the fix higlighted below.
~~~sh
Cannot find material properties for Garage Attached Wall with properties: {'Construction Type': 'WoodStud', 'Finish Type': 'fiber cement siding'}
~~~
OCHRE raises such exceptions because ResStock 2025 introduced new **Construction Type**/**Finish Type** combinations that are not listed in OCHRE's **Envelope Boundary Type.csv**

### Fixe:

- Added an `IGNORE_COMBINATIONS` dictionary inside `get_boundary_rc_values()` function.
- A warning will be printed in the terminal indicating the bad combinations during the simulation.

### Error 3:
~~~sh
Unable to parse multiple attic floor areas: [...]
~~~

### Fix:
OCHRE's original code places some restriced rule where one area only is selected. This was replaced by a sum-and-warn approach. This fix includes modifying the top-floor/attic sections in **parse_hpxml_boundaries()** function within the **hpxml.py** Python file. The original order of perferance is kept the same (**Attic Floor, Adjacent Ceiling, Roof**).

### Error 4:

~~~sh
KeyError: "NO SPACE COOLING, NO SPACE HEATING"
~~~

### Fix:
Within **schedules.py**, ochres incorporates an ignore dictionary (within a lookup table). Here is the original ignore dictionary:

~~~sh
"Ignore": {
        "extra_refrigerator": None,
        "freezer": None,
        "clothes_dryer_exhaust": None,
        "lighting_exterior_holiday": None,
        "plug_loads_vehicle": None,
        "battery": None,
        "vacancy": None,
        "water_heater_operating_mode": None,
        "Vacancy": None,
        "Power Outage": None,
    },
~~~

Adding the three column labels that was causing the problem resolved the issue. Here is the updated ignore dictionary:

~~~sh
"Ignore": {
        "extra_refrigerator": None,
        "freezer": None,
        "clothes_dryer_exhaust": None,
        "lighting_exterior_holiday": None,
        "plug_loads_vehicle": None,
        "battery": None,
        "vacancy": None,
        "water_heater_operating_mode": None,
        "Vacancy": None,
        "Power Outage": None,
        # Midrar Added:
        "No Space Heating": None,
        "No Space Cooling": None,
        "electric_vehicle_charging": None,
        },
~~~
