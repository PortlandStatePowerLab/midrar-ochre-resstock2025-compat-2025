"""
Author: Midrar Adham
Created: Sat Aug 01 2026
"""

import os
import pandas as pd
from pathlib import Path
import pyarrow.parquet as pq


wh_column = "Water Heating Electric Power (kW)"
hvac_column = "HVAC Cooling Electric Power (kW)"
output_dir = Path(
    "~/projects/gld-opedss-ochre-helics/cosimulation_tools/"
    "gld-ochre-helics/non-real-time/results"
).expanduser()


def write_manifest(manifest_filename: str | Path) -> None:
    path_dir = Path("/mnt/datasets/resstock_2024/cosimulation/")
    upgrade = "up02"
    existing_files = []

    for bldg_id in os.listdir(path_dir):
        parquet_file = (
            path_dir / bldg_id / upgrade / "simulation_results_august" / "ochre.parquet"
        )

        if parquet_file.is_file() and parquet_file.stat().st_size > 0:
            existing_files.append({"bldg_id": bldg_id, "path": str(parquet_file)})

    manifest_df = pd.DataFrame(existing_files, columns=["bldg_id", "path"])
    manifest_df.to_csv(manifest_filename, index=False)

    print(f"Wrote {len(manifest_df)} valid Parquet paths to {manifest_filename}")


def has_wh(file_cols: list[str]) -> bool:
    return wh_column in file_cols


def has_hvac(file_cols: list[str]) -> bool:
    return hvac_column in file_cols


def building_id_from_path(parquet_path: str | Path) -> str:
    """Extract the building ID from <bldg_id>/<upgrade>/<results>/ochre.parquet."""
    path = Path(parquet_path)
    if len(path.parents) < 3:
        raise ValueError(f"Path does not contain a building ID: {path}")
    return path.parents[2].name


def write_wh_hvac_manifests(full_df: pd.DataFrame) -> None:
    wh_manifest_filename = output_dir / "wh_manifest.csv"
    hvac_manifest_filename = output_dir / "hvac_manifest.csv"

    output_dir.mkdir(parents=True, exist_ok=True)

    wh_buildings = []
    hvac_buildings = []
    both_count = 0
    neither_count = 0

    for row in full_df.itertuples(index=False):
        try:
            parquet_file = pq.ParquetFile(row.path)
            file_cols = parquet_file.schema.names
            row_bldg_id = getattr(row, "bldg_id", None)
            bldg_id = (
                str(row_bldg_id)
                if row_bldg_id is not None and not pd.isna(row_bldg_id)
                else building_id_from_path(row.path)
            )
            manifest_row = {"bldg_id": bldg_id, "path": row.path}

            has_wh_column = has_wh(file_cols)
            has_hvac_column = has_hvac(file_cols)

            if has_wh_column:
                wh_buildings.append(manifest_row)
            if has_hvac_column:
                hvac_buildings.append(manifest_row)
            if has_wh_column and has_hvac_column:
                both_count += 1
            elif not has_wh_column and not has_hvac_column:
                neither_count += 1

        except Exception as exc:
            print(f"Could not inspect {row.path}: {exc}")

    manifest_columns = ["bldg_id", "path"]
    wh_df = pd.DataFrame(wh_buildings, columns=manifest_columns)
    hvac_df = pd.DataFrame(hvac_buildings, columns=manifest_columns)

    wh_df.to_csv(wh_manifest_filename, index=False)
    hvac_df.to_csv(hvac_manifest_filename, index=False)

    print("There are:")
    print(f"{len(wh_df)} files with WH")
    print(f"{len(hvac_df)} files with HVAC cooling")
    print(f"{both_count} files with both WH and HVAC cooling (included in both)")
    print(f"{neither_count} files with neither column (excluded)")
    print(f"Wrote {wh_manifest_filename}")
    print(f"Wrote {hvac_manifest_filename}")


def main() -> None:
    manifest_filename = Path("./datasets_manifest.csv")

    if not manifest_filename.is_file():
        write_manifest(manifest_filename)

    full_df = pd.read_csv(manifest_filename)
    write_wh_hvac_manifests(full_df)


if __name__ == "__main__":
    main()
