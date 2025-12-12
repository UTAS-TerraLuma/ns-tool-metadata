import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

import pandas as pd
import typer


def get_root_element_from_kmz(kmz_file: Path) -> ET.Element:
    """
    Extract and parse the template.kml file from a DJI WPML KMZ file.

    Args:
        kmz_file: Path to the KMZ file (which is a ZIP archive containing KML data).

    Returns:
        An Element which is the root of the KML Tree.

    Raises:
        FileNotFoundError: If the wpmz/template.kml file is not found in the KMZ archive.
        zipfile.BadZipFile: If the provided file is not a valid ZIP/KMZ file.
    """
    with zipfile.ZipFile(kmz_file) as kml_zip:
        template_file_name = "wpmz/template.kml"
        if template_file_name not in kml_zip.namelist():
            raise FileNotFoundError("wpmz/template.kml not found")

        with kml_zip.open(template_file_name) as template_file:
            tree = ET.parse(template_file)
            root = tree.getroot()
            return root


def get_value(root: ET.Element, tag: str) -> str | float | int:
    """
    Extract text from an XML element and convert to appropriate numeric type if possible.

    Searches for an element with the specified tag name (using namespace wildcards)
    and returns its text content. Attempts to convert the text to int or float,
    falling back to string if the text is not numeric.

    Args:
        root: The root XML Element to search within.
        tag: The tag name to search for (without namespace prefix).
             Namespace wildcards are used automatically in the search.

    Returns:
        The element's text content as an int, float, or str:
        - int if the text represents a whole number (e.g., "42" -> 42)
        - float if the text represents a decimal number (e.g., "3.14" -> 3.14)
        - str if the text is not numeric (e.g., "hello" -> "hello")

    Raises:
        ValueError: If no element with the specified tag is found in the tree.
    """
    el = root.find(".//{*}" + tag)
    if el is None:
        raise ValueError(f"No element with tag {tag}")

    text = el.text.strip() if el.text else ""

    try:
        return int(text)
    except ValueError:
        pass

    try:
        return float(text)
    except ValueError:
        pass

    return text


def parse_tree(root: ET.Element) -> pd.Series:
    """
    Parse DJI KMZ XML tree and extract flight mission metadata.

    Extracts key flight parameters from a DJI WPML KML file including platform information,
    flight settings, terrain following configuration, and target surface takeoff offset.

    Args:
        root: The root XML Element from a DJI WPML template.kml file.

    Returns:
        A pandas Series containing the flight metadata.

    Raises:
        ValueError: If required XML elements (droneEnumValue, droneSubEnumValue, etc.) are not found.
        KeyError: If the drone enum combination is not in the sensor lookup table.

    """
    dji_sensor_lookup = {
        "89_0": "Matrice 350 RTK",
        "60_0": "Matrice 300 RTK",
        "67_0": "Matrice 30",
        "67_1": "Matrice 30T",
        "77_0": "M3M/M3E",
        "77_1": "M3T",
        "91_0": "Matrice 3D",
        "91_1": "Matrice 3TD",
        "100_0": "Matrice 4D",
        "100_1": "Matrice 4TD",
        "99_0": "M4E",
        "99_1": "M4T",
    }

    # ---- Common Values ----

    drone_enum = get_value(root, "droneEnumValue")
    drone_sub_enum = get_value(root, "droneSubEnumValue")
    platform = dji_sensor_lookup[f"{drone_enum}_{drone_sub_enum}"]
    flight_height = get_value(root, "globalShootHeight")
    assert isinstance(flight_height, (int, float))
    flight_speed = get_value(root, "autoFlightSpeed")
    assert isinstance(flight_speed, (int, float))
    flight_speed = round(flight_speed, 2)
    flight_direction = get_value(root, "direction")
    margin_m = get_value(root, "margin")
    forward_overlap = get_value(root, "orthoCameraOverlapH")
    side_overlap = get_value(root, "orthoCameraOverlapW")

    # ---- Terrain Values ----
    try:
        terrain_follow = get_value(root, "surfaceFollowModeEnable")
        assert terrain_follow == 1
        terrain_follow = "Enabled"

        terrain_type = get_value(root, "isRealtimeSurfaceFollow")
        if terrain_type == 0:
            terrain_type = "AGL model"
        elif terrain_type == 1:
            terrain_type = "real time follow"
        else:
            terrain_type = f"{terrain_type} Unknown"
    except Exception:
        terrain_follow = "Disabled"
        terrain_type = "N/A"

    try:
        height = get_value(root, "height")
        assert isinstance(height, (float, int))
        tsto = flight_height - height
    except Exception:
        tsto = 0

    return pd.Series(
        {
            "Platform": platform,
            "Flight_height(m)": flight_height,
            "Flight_speed(m/s)": flight_speed,
            "Orientation_deg": flight_direction,
            "Margin_m": margin_m,
            "Forward_overlap%": forward_overlap,
            "Side_overlap%": side_overlap,
            "Terrain_follow": terrain_follow,
            "Terrain_type": terrain_type,
            "Target_surface_takeoff(m)": tsto,
        }
    )


def get_user_fields() -> pd.Series:
    """
    Prompt user for manual metadata input not available in KMZ file.

    Returns:
        A pandas Series containing user-provided metadata fields.
    """
    site_name = typer.prompt("Enter site name")
    white_balance = typer.prompt("Enter white balance setting")
    cloudy = typer.prompt("Enter sky conditions")
    wind = typer.prompt("Enter average wind conditions")
    base_station = typer.prompt("Was a base station established? (y/n)")
    comments = typer.prompt("Enter any relevant comments about the flight")

    return pd.Series(
        {
            "Site_name": site_name,
            "White_balance": white_balance,
            "Sky_conditions": cloudy,
            "Wind_conditions": wind,
            "Base_station": base_station,
            "Comments": comments,
        }
    )


def combine_metadata(
    metadata_from_file: pd.Series, metadata_from_user: pd.Series
) -> pd.Series:
    """
    Combine metadata from KMZ file and user input, with Site_name as the first field.

    Args:
        metadata_from_file: Metadata extracted from the KMZ file.
        metadata_from_user: Metadata collected from user prompts.

    Returns:
        A pandas Series containing all metadata with Site_name as the first field,
        followed by file metadata, then remaining user metadata fields.
    """
    # Reorder to put Site_name first
    site_name = pd.Series({"Site_name": metadata_from_user["Site_name"]})
    other_user_fields = metadata_from_user.drop("Site_name")

    metadata = pd.concat([site_name, metadata_from_file, other_user_fields])

    return metadata


def save_metadata(metadata: pd.Series, output: Path) -> pd.DataFrame:
    """
    Save metadata to a CSV file with field names as rows (header rows format).

    Args:
        metadata: A pandas Series containing all metadata fields and values.
        output: Path to the CSV file where metadata will be saved.

    Returns:
        A pandas DataFrame with metadata formatted for CSV output.
    """
    # Convert to DataFrame with field names as rows (header rows format)
    metadata_df = metadata.to_frame(name="Value")
    metadata_df.index.name = "Field"

    # Save to CSV
    metadata_df.to_csv(output)

    return metadata_df


app = typer.Typer()


def title():
    ascii = """
░███    ░██    ░███    ░██████████░██     ░██ ░█████████  ░██████████
░████   ░██   ░██░██       ░██    ░██     ░██ ░██     ░██ ░██
░██░██  ░██  ░██  ░██      ░██    ░██     ░██ ░██     ░██ ░██
░██ ░██ ░██ ░█████████     ░██    ░██     ░██ ░█████████  ░█████████
░██  ░██░██ ░██    ░██     ░██    ░██     ░██ ░██   ░██   ░██
░██   ░████ ░██    ░██     ░██     ░██   ░██  ░██    ░██  ░██
░██    ░███ ░██    ░██     ░██      ░██████   ░██     ░██ ░██████████

          ░██████     ░██████     ░███    ░███    ░██
         ░██   ░██   ░██   ░██   ░██░██   ░████   ░██
        ░██         ░██         ░██  ░██  ░██░██  ░██
         ░████████  ░██        ░█████████ ░██ ░██ ░██
                ░██ ░██        ░██    ░██ ░██  ░██░██
         ░██   ░██   ░██   ░██ ░██    ░██ ░██   ░████
          ░██████     ░██████  ░██    ░██ ░██    ░███


    """
    typer.echo(ascii)


@app.command()
def parse_kmz(input: Path, output: Path) -> None:
    """
    Parse a DJI KMZ file and extract metadata.

    Args:
        input: Path to the KMZ file to parse.
        output: Path to CSV file to save the output.
    """
    title()
    # TODO - Check if path is a dir or is a .kmz file
    typer.echo(f"Grabbing metadata from: {input}")
    root = get_root_element_from_kmz(input)

    metadata_from_file = parse_tree(root)
    typer.echo("\nPulled the following values:\n")
    typer.echo(metadata_from_file)

    typer.echo("\nPrompting user for metadata...\n")
    metadata_from_user = get_user_fields()
    metadata = combine_metadata(metadata_from_file, metadata_from_user)
    save_metadata(metadata, output)
    typer.echo(f"\nMetadata saved to {output}")


if __name__ == "__main__":
    app()
