'''
Author: Midrar Adham
Created: Thu Jul 23 2026
'''
"""
02b_build_canonical_electric_hvac_devices.py

Build a cleaned canonical electric HVAC device table.

This script reads:

outputs/hvac_metadata.csv

created by:

02_extract_hvac_metadata.py

Then it creates one cleaned table focused on electric HVAC devices that are
appropriate for electric kW diagnostics, plotting, binning, and OLS.

Output:

outputs/hvac_analysis/canonical_electric_hvac_devices.csv

Important:
This script does not modify any simulation files.
"""

from pathlib import Path
import pandas as pd


# ---------------------------------------------------------------------------
# User settings
# ---------------------------------------------------------------------------
# Rule: keep variable names lowercase.

analysis_dir = Path("./outputs/")
metadata_file = analysis_dir / "hvac_metadata.csv"
output_file = analysis_dir / "canonical_electric_hvac_devices.csv"

upgrades = ["up00", "up01", "up02"]

electric_fuels = ["electricity"]

non_electric_fuels = [
    "natural gas",
    "propane",
    "fuel oil",
    "wood",
    "coal",
    "other fuel",
]


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

def normalize_text(value):
    """
    Normalize text for comparisons.
    """
    if pd.isna(value):
        return ""

    return str(value).strip().lower()


def is_electric_fuel(value):
    """
    Return True when the equipment fuel is electricity.
    """
    return normalize_text(value) in electric_fuels


def is_non_electric_fuel(value):
    """
    Return True when the equipment fuel is clearly non-electric.
    """
    return normalize_text(value) in non_electric_fuels


def infer_service_type(row):
    """
    Infer whether the metadata row represents heating, cooling, or both.
    """
    element_type = normalize_text(row.get("element_type"))
    equipment_type = normalize_text(row.get("equipment_type"))

    has_heating_capacity = pd.notna(row.get("heating_capacity_kw_thermal"))
    has_cooling_capacity = pd.notna(row.get("cooling_capacity_kw_thermal"))

    if element_type == "heatpump":
        return "heating_and_cooling"

    if element_type == "coolingsystem":
        return "cooling"

    if element_type == "heatingsystem":
        return "heating"

    if "hvac cooling" in equipment_type:
        return "cooling"

    if "hvac heating" in equipment_type:
        return "heating"

    if has_heating_capacity and has_cooling_capacity:
        return "heating_and_cooling"

    if has_heating_capacity:
        return "heating"

    if has_cooling_capacity:
        return "cooling"

    return "unknown"


def infer_device_type(row):
    """
    Create a clean device type label.
    """
    element_type = normalize_text(row.get("element_type"))
    equipment_type = normalize_text(row.get("equipment_type"))
    analysis_class = normalize_text(row.get("analysis_class"))

    if element_type == "heatpump":
        if "geothermal" in analysis_class or "ground" in equipment_type:
            return "geothermal_heat_pump"

        return "air_source_heat_pump"

    if element_type == "coolingsystem":
        return "air_conditioner"

    if element_type == "heatingsystem":
        if is_electric_fuel(row.get("fuel")):
            return "electric_heating_system"

        return "non_electric_heating_system"

    if "hvac cooling" in equipment_type:
        return "ochre_hvac_cooling"

    if "hvac heating" in equipment_type:
        return "ochre_hvac_heating"

    return "unknown"


def choose_capacity_kw_thermal(row):
    """
    Choose one representative thermal capacity.

    For heat pumps and cooling devices, cooling capacity is useful for August
    cooling analysis. For heating-only devices, heating capacity is used.
    """
    service_type = row.get("service_type")

    cooling_capacity = row.get("cooling_capacity_kw_thermal")
    heating_capacity = row.get("heating_capacity_kw_thermal")

    if service_type == "cooling":
        return cooling_capacity

    if service_type == "heating":
        return heating_capacity

    if service_type == "heating_and_cooling":
        if pd.notna(cooling_capacity):
            return cooling_capacity

        return heating_capacity

    if pd.notna(cooling_capacity):
        return cooling_capacity

    return heating_capacity


def should_include_in_electric_hvac(row):
    """
    Decide whether this row should be used for electric HVAC analysis.

    The key rule is:
    - Keep electric HVAC devices.
    - Exclude natural gas, propane, fuel oil, wood, and other non-electric fuels.
    """
    source = normalize_text(row.get("source"))
    element_type = normalize_text(row.get("element_type"))
    equipment_type = normalize_text(row.get("equipment_type"))
    fuel = normalize_text(row.get("fuel"))
    service_type = row.get("service_type")

    if source != "home_xml":
        return False

    if service_type not in ["heating", "cooling", "heating_and_cooling"]:
        return False

    if element_type in ["missing_home_xml", "xml_read_error", "no_hvac_elements_found"]:
        return False

    if is_non_electric_fuel(fuel):
        return False

    if is_electric_fuel(fuel):
        return True

    # Some HeatPump rows may have missing fuel in HPXML depending on version.
    # If the element is explicitly a HeatPump and it has cooling or heating
    # capacity, keep it as an electric HVAC candidate but flag the fuel as
    # missing/assumed.
    if element_type == "heatpump":
        return True

    # Some cooling systems may omit the fuel field but still represent electric
    # air conditioning. We do not include those automatically yet, because that
    # can hide metadata problems. We will inspect them separately.
    if element_type == "coolingsystem" and fuel == "":
        return False

    return False


def exclusion_reason(row):
    """
    Explain why a row is not included in electric HVAC analysis.
    """
    if row.get("include_in_electric_hvac_analysis"):
        return "included"

    source = normalize_text(row.get("source"))
    fuel = normalize_text(row.get("fuel"))
    service_type = row.get("service_type")
    element_type = normalize_text(row.get("element_type"))

    if source != "home_xml":
        return "not_home_xml_source"

    if element_type in ["missing_home_xml", "xml_read_error", "no_hvac_elements_found"]:
        return element_type

    if service_type not in ["heating", "cooling", "heating_and_cooling"]:
        return "not_hvac_service"

    if is_non_electric_fuel(fuel):
        return f"non_electric_fuel_{fuel.replace(' ', '_')}"

    if fuel == "":
        return "missing_fuel"

    return "other_exclusion"


def main():
    """
    Build the canonical electric HVAC device table.
    """
    if not metadata_file.is_file():
        raise FileNotFoundError(
            f"metadata_file does not exist: {metadata_file}\n"
            "Run 02_extract_hvac_metadata.py first."
        )

    metadata = pd.read_csv(metadata_file)
    metadata = metadata[metadata["upgrade"].isin(upgrades)].copy()

    metadata["service_type"] = metadata.apply(infer_service_type, axis=1)
    metadata["device_type"] = metadata.apply(infer_device_type, axis=1)
    metadata["representative_capacity_kw_thermal"] = metadata.apply(
        choose_capacity_kw_thermal,
        axis=1,
    )
    metadata["include_in_electric_hvac_analysis"] = metadata.apply(
        should_include_in_electric_hvac,
        axis=1,
    )
    metadata["exclusion_reason"] = metadata.apply(exclusion_reason, axis=1)

    canonical = metadata[
        metadata["include_in_electric_hvac_analysis"] == True
    ].copy()

    canonical = canonical[
        [
            "building_id",
            "upgrade",
            "source",
            "element_type",
            "system_identifier",
            "equipment_type",
            "fuel",
            "service_type",
            "device_type",
            "analysis_class",
            "heating_capacity_btuh",
            "heating_capacity_tons",
            "heating_capacity_kw_thermal",
            "cooling_capacity_btuh",
            "cooling_capacity_tons",
            "cooling_capacity_kw_thermal",
            "representative_capacity_kw_thermal",
            "backup_fuel",
            "backup_system_type",
            "backup_heating_capacity_btuh",
            "backup_heating_capacity_tons",
            "backup_heating_capacity_kw_thermal",
            "compressor_type",
            "annual_heating_efficiency_type",
            "annual_heating_efficiency_value",
            "annual_cooling_efficiency_type",
            "annual_cooling_efficiency_value",
            "source_file",
        ]
    ].copy()

    canonical.to_csv(output_file, index=False)

    review_file = analysis_dir / "hvac_metadata_with_electric_filter_flags.csv"
    metadata.to_csv(review_file, index=False)

    print("\nSaved canonical electric HVAC device table:")
    print(output_file)

    print("\nSaved review table with inclusion/exclusion flags:")
    print(review_file)

    print("\nCanonical rows:")
    print(len(canonical))

    print("\nCanonical rows by upgrade and service type:")
    print(
        canonical
        .groupby(["upgrade", "service_type"])
        .size()
        .unstack(fill_value=0)
    )

    print("\nCanonical rows by upgrade and device type:")
    print(
        canonical
        .groupby(["upgrade", "device_type"])
        .size()
        .unstack(fill_value=0)
    )

    print("\nExcluded rows by reason:")
    print(
        metadata[metadata["include_in_electric_hvac_analysis"] == False]
        .groupby(["upgrade", "exclusion_reason"])
        .size()
        .unstack(fill_value=0)
    )

    print("\nFuel counts in included canonical table:")
    print(
        canonical
        .groupby(["upgrade", "fuel"])
        .size()
        .unstack(fill_value=0)
    )

    print("\nPreview:")
    preview_cols = [
        "building_id",
        "upgrade",
        "element_type",
        "equipment_type",
        "fuel",
        "service_type",
        "device_type",
        "heating_capacity_tons",
        "cooling_capacity_tons",
        "representative_capacity_kw_thermal",
        "backup_fuel",
    ]
    print(canonical[preview_cols].head(30))


if __name__ == "__main__":
    main()
