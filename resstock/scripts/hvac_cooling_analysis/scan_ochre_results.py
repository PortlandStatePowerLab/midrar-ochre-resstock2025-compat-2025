'''
Author: Midrar Adham
Created: Thu Jul 23 2026
'''
"""
01_scan_ochre_results.py

Scan OCHRE results for ResStock 2024 HVAC analysis.

This script does not modify any simulation files. It only checks whether each
building and upgrade has the expected input/result files and whether the OCHRE
time-series file contains heating and/or cooling HVAC power columns.

Expected dataset structure:

datasets/
└── resstock_2024/
    └── cosimulation/
        ├── <building_id>/
        │   ├── up00/
        │   ├── up01/
        │   └── up02/

Output:

outputs/ochre_result_inventory.csv
"""

import pandas as pd
from pathlib import Path


# ---------------------------------------------------------------------------
# User settings
# ---------------------------------------------------------------------------

dataset_dir = Path("/mnt/datasets/resstock_2024/cosimulation")
output_dir = Path("./outputs/")

upgrades = ["up00", "up01", "up02"]

# Change this if your OCHRE results are saved in a different folder name.
results_folder = "simulation_results_august"

heating_power_col = "HVAC Heating Electric Power (kW)"
cooling_power_col = "HVAC Cooling Electric Power (kW)"

expected_time_resolution_minutes = 1

# August has 31 days. At 1-minute resolution, a complete month has:
# 31 days * 24 hours/day * 60 minutes/hour = 44,640 rows.
expected_rows = 30 * 24 * 60


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

def read_parquet_metadata(parquet_path):
    """
    Read Parquet column names and row count.

    This first tries pyarrow metadata because it is fast and does not load the
    full time-series file. If pyarrow is unavailable, it falls back to pandas.
    """
    try:
        import pyarrow.parquet as pq

        parquet_file = pq.ParquetFile(parquet_path)
        columns = parquet_file.schema.names
        n_rows = parquet_file.metadata.num_rows

        return columns, n_rows, None

    except Exception:
        try:
            df = pd.read_parquet(parquet_path)
            columns = list(df.columns)
            n_rows = len(df)

            return columns, n_rows, None

        except Exception as error:
            return [], None, str(error)


def read_csv_metadata(csv_path):
    """
    Read CSV column names and row count.

    This avoids loading the full OCHRE CSV into memory.
    """
    try:
        columns = list(pd.read_csv(csv_path, nrows=0).columns)
    except Exception as error:
        return [], None, str(error)

    try:
        with open(csv_path, "r", encoding="utf-8", errors="ignore") as file:
            n_rows = sum(1 for _ in file) - 1

        n_rows = max(n_rows, 0)

    except Exception as error:
        return columns, None, str(error)

    return columns, n_rows, None


def classify_simulation_status(has_timeseries_file, n_rows, read_error, has_cooling_col):
    """
    Create a simple status label for each building-upgrade result.

    These labels are intentionally simple. Later scripts can use them for
    filtering before metadata extraction, diagnostics, and plotting.
    """
    if read_error is not None:
        return "timeseries_read_error"

    if not has_timeseries_file:
        return "missing_timeseries_file"

    if n_rows is None:
        return "unknown_row_count"

    if n_rows == 0:
        return "empty_timeseries_file"

    if n_rows < expected_rows:
        return "partial_month"

    if not has_cooling_col:
        return "complete_month_missing_cooling_column"

    return "complete_month"


def scan_building_upgrade(building_dir, upgrade):
    """
    Scan one building and one upgrade.

    Returns one dictionary row for the inventory table.
    """
    building_id = building_dir.name
    upgrade_dir = building_dir / upgrade
    results_dir = upgrade_dir / results_folder

    home_xml = upgrade_dir / "home.xml"
    schedules_csv = upgrade_dir / "in.schedules.csv"
    ochre_json = results_dir / "ochre.json"
    ochre_parquet = results_dir / "ochre.parquet"
    ochre_csv = results_dir / "ochre.csv"

    has_upgrade_dir = upgrade_dir.is_dir()
    has_results_dir = results_dir.is_dir()
    has_home_xml = home_xml.is_file() and home_xml.stat().st_size > 0
    has_in_schedules = schedules_csv.is_file() and schedules_csv.stat().st_size > 0
    has_ochre_json = ochre_json.is_file() and ochre_json.stat().st_size > 0
    has_ochre_parquet = ochre_parquet.is_file() and ochre_parquet.stat().st_size > 0
    has_ochre_csv = ochre_csv.is_file() and ochre_csv.stat().st_size > 0

    # Prefer Parquet because that is your current output format.
    # Fall back to CSV only if Parquet is unavailable.
    timeseries_file = None
    timeseries_format = None

    if has_ochre_parquet:
        timeseries_file = ochre_parquet
        timeseries_format = "parquet"
    elif has_ochre_csv:
        timeseries_file = ochre_csv
        timeseries_format = "csv"

    has_timeseries_file = timeseries_file is not None

    columns = []
    read_error = None
    n_rows = None

    if has_timeseries_file and timeseries_format == "parquet":
        columns, n_rows, read_error = read_parquet_metadata(timeseries_file)

    elif has_timeseries_file and timeseries_format == "csv":
        columns, n_rows, read_error = read_csv_metadata(timeseries_file)

    has_heating_col = heating_power_col in columns
    has_cooling_col = cooling_power_col in columns

    simulation_status = classify_simulation_status(
        has_timeseries_file=has_timeseries_file,
        n_rows=n_rows,
        read_error=read_error,
        has_cooling_col=has_cooling_col,
    )

    return {
        "building_id": building_id,
        "upgrade": upgrade,
        "upgrade_dir": str(upgrade_dir),
        "results_dir": str(results_dir),
        "has_upgrade_dir": has_upgrade_dir,
        "has_results_dir": has_results_dir,
        "has_home_xml": has_home_xml,
        "has_in_schedules": has_in_schedules,
        "has_ochre_json": has_ochre_json,
        "has_ochre_parquet": has_ochre_parquet,
        "has_ochre_csv": has_ochre_csv,
        "has_timeseries_file": has_timeseries_file,
        "timeseries_format": timeseries_format,
        "timeseries_file": str(timeseries_file) if timeseries_file is not None else None,
        "n_rows": n_rows,
        "expected_rows": expected_rows,
        "has_heating_col": has_heating_col,
        "has_cooling_col": has_cooling_col,
        "simulation_status": simulation_status,
        "read_error": read_error,
    }


# ---------------------------------------------------------------------------
# Main script
# ---------------------------------------------------------------------------

def main():
    """
    Scan all building folders and save one inventory CSV.
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    if not dataset_dir.is_dir():
        raise FileNotFoundError(
            f"dataset_dir does not exist: {dataset_dir}\n"
            "Check the dataset_dir setting at the top of the script."
        )

    rows = []

    for building_dir in sorted(dataset_dir.iterdir()):
        if not building_dir.is_dir():
            continue

        for upgrade in upgrades:
            rows.append(scan_building_upgrade(building_dir, upgrade))

    inventory = pd.DataFrame(rows)

    output_file = output_dir / "ochre_result_inventory.csv"
    inventory.to_csv(output_file, index=False)

    print("\nSaved inventory:")
    print(output_file)

    print("\nTotal rows:")
    print(len(inventory))

    print("\nRows by upgrade:")
    print(inventory["upgrade"].value_counts().sort_index())

    print("\nTime-series format by upgrade:")
    print(
        inventory
        .groupby(["upgrade", "timeseries_format"])
        .size()
        .unstack(fill_value=0)
    )

    print("\nSimulation status by upgrade:")
    print(
        inventory
        .groupby(["upgrade", "simulation_status"])
        .size()
        .unstack(fill_value=0)
    )

    print("\nHeating column counts by upgrade:")
    print(inventory.groupby("upgrade")["has_heating_col"].sum())

    print("\nCooling column counts by upgrade:")
    print(inventory.groupby("upgrade")["has_cooling_col"].sum())

    print("\nOCHRE JSON exists but time-series file is missing:")
    json_no_timeseries = inventory[
        (inventory["has_ochre_json"] == True)
        & (inventory["has_timeseries_file"] == False)
    ]
    print(json_no_timeseries.groupby("upgrade").size())

    print("\nPreview:")
    preview_cols = [
        "building_id",
        "upgrade",
        "has_home_xml",
        "has_in_schedules",
        "has_ochre_json",
        "has_ochre_parquet",
        "has_ochre_csv",
        "timeseries_format",
        "n_rows",
        "has_heating_col",
        "has_cooling_col",
        "simulation_status",
    ]
    print(inventory[preview_cols].head(20))


if __name__ == "__main__":
    main()
