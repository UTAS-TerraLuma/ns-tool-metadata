import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path
from typing import Any

import pyproj
from pydantic import BaseModel
from pyproj.aoi import AreaOfInterest
from shapely import Polygon, wkt
from shapely.geometry import mapping
from shapely.ops import transform


class DJIMetadata(BaseModel):
    platform: str
    sensor: str
    mission_updated_timestamp: int
    flight_height_m: int | float
    flight_speed_ms: float
    orientation_deg: int | float
    margin_m: int | float
    forward_overlap: int | float
    side_overlap: int | float
    terrain_follow: str
    terrain_type: str
    target_surface_takeoff_m: float
    polygon: str
    polygon_with_buffer: str

    def to_geojson_feature(self) -> dict[str, Any]:
        geom = wkt.loads(self.polygon_with_buffer)

        props = self.model_dump()

        return {
            "type": "Feature",
            "geometry": mapping(geom),
            "properties": props,
        }


# The buffer must be done in a projected coordinate system
def buffer_in_metres(geom: Polygon, margin_m: int | float):
    # Define projections
    wgs84 = pyproj.CRS("EPSG:4326")

    # Auto-pick appropriate UTM zone based on centroid
    utm_crs = pyproj.CRS.from_user_input(
        pyproj.database.query_utm_crs_info(
            datum_name="WGS 84",
            area_of_interest=AreaOfInterest(
                west_lon_degree=geom.centroid.x,
                south_lat_degree=geom.centroid.y,
                east_lon_degree=geom.centroid.x,
                north_lat_degree=geom.centroid.y,
            ),
        )[0].code
    )

    # Transformers
    project_to_utm = pyproj.Transformer.from_crs(
        wgs84, utm_crs, always_xy=True
    ).transform
    project_to_wgs = pyproj.Transformer.from_crs(
        utm_crs, wgs84, always_xy=True
    ).transform

    # Reproject to metres
    geom_utm = transform(project_to_utm, geom)

    # Buffer in metres
    buffered_utm = geom_utm.buffer(margin_m, cap_style="square", join_style="mitre")

    # Reproject back to WGS84
    buffered_wgs84 = transform(project_to_wgs, buffered_utm)

    return buffered_wgs84


def _get_root_element_from_kmz(kmz_file: Path) -> ET.Element:
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


def _get_value(root: ET.Element, tag: str):
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


def _kml_coords_to_polygon(coords_str: str) -> Polygon:
    coord_lines = coords_str.split("\n")
    coord_lines = [line.strip().split(",") for line in coord_lines]
    coords = [(float(x), float(y), float(z)) for x, y, z in coord_lines]
    return Polygon(coords)


def _parse_tree(root: ET.Element) -> DJIMetadata:
    """
    Parse DJI KMZ XML tree and extract flight mission metadata.

    Extracts key flight parameters from a DJI WPML KML file including platform information,
    flight settings, terrain following configuration, and target surface takeoff offset.

    Args:
        root: The root XML Element from a DJI WPML template.kml file.

    Returns:
        A dictionary containing the flight metadata.

    Raises:
        ValueError: If required XML elements (droneEnumValue, droneSubEnumValue, etc.) are not found
        KeyError: If the drone enum combination is not in the sensor lookup table.

    """

    # ---- Platform ----

    # See here for look up values
    # https://developer.dji.com/doc/cloud-api-tutorial/en/overview/product-support.html#enumeration-values-of-aircraft-rc-and-dock
    # Our keys are formated as "{type}_{subtype}"
    dji_platform_lookup = {
        "103_0": "Matrice 400",
        "89_0": "Matrice 350 RTK",
        "60_0": "Matrice 300 RTK",
        "67_0": "Matrice 30",
        "67_1": "Matrice 30T",
        "77_0": "M3M/M3E",
        "77_1": "M3T",
        "77_3": "M3TA",
        "91_0": "Matrice 3D",
        "91_1": "Matrice 3TD",
        "100_0": "Matrice 4D",
        "100_1": "Matrice 4TD",
        "99_0": "M4E",
        "99_1": "M4T",
    }
    drone_enum = _get_value(root, "droneEnumValue")
    drone_sub_enum = _get_value(root, "droneSubEnumValue")
    try:
        platform = dji_platform_lookup[f"{drone_enum}_{drone_sub_enum}"]
    except KeyError:
        platform = f"unknown platform (code: {drone_enum}_{drone_sub_enum})"

    # ---- Sensor / Payload ----

    # The sensors aren't as well documented, so this is based on our experience
    dji_sensor_lookup = {
        "68_3": "m3m",
        "68_0": "m3m",  # To Confirm
        "50_1": "p1",
        "84_1": "l2",
    }
    payload_enum = _get_value(root, "payloadEnumValue")
    payload_sub_enum = _get_value(root, "payloadSubEnumValue")
    try:
        sensor = dji_sensor_lookup[f"{payload_enum}_{payload_sub_enum}"]
    except KeyError:
        sensor = f"unknown sensor (code: {payload_enum}_{payload_sub_enum})"
        print(f"\n\n\nunknown sensor (code: {payload_enum}_{payload_sub_enum})\n\n\n")

    # ---- Flight Params ----
    flight_height = _get_value(root, "globalShootHeight")
    assert isinstance(flight_height, (int, float))
    flight_speed = _get_value(root, "autoFlightSpeed")
    assert isinstance(flight_speed, (int, float))
    flight_speed = round(flight_speed, 2)
    flight_direction = _get_value(root, "direction")
    margin_m = _get_value(root, "margin")
    forward_overlap = _get_value(root, "orthoCameraOverlapH")
    side_overlap = _get_value(root, "orthoCameraOverlapW")

    # ---- Terrain Values ----
    try:
        terrain_follow = _get_value(root, "surfaceFollowModeEnable")
        assert terrain_follow == 1
        terrain_follow = "Enabled"

        terrain_type = _get_value(root, "isRealtimeSurfaceFollow")
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
        height = _get_value(root, "height")
        assert isinstance(height, (float, int))
        tsto = flight_height - height
    except Exception:
        tsto = 0

    # ---- Polygon ----
    polygon_el = root.find(".//{*}Polygon")
    assert polygon_el is not None
    polygon_coordinates = _get_value(polygon_el, "coordinates")
    polygon = _kml_coords_to_polygon(str(polygon_coordinates))
    assert isinstance(polygon, Polygon)

    polygon_with_buffer = buffer_in_metres(polygon, margin_m)

    # ---- Update Time ----
    mission_updated_timestamp = _get_value(root, "updateTime")

    return DJIMetadata(
        platform=platform,
        sensor=sensor,
        mission_updated_timestamp=mission_updated_timestamp,
        flight_height_m=flight_height,
        flight_speed_ms=flight_speed,
        orientation_deg=flight_direction,
        margin_m=margin_m,
        forward_overlap=forward_overlap,
        side_overlap=side_overlap,
        terrain_follow=terrain_follow,
        terrain_type=terrain_type,
        target_surface_takeoff_m=tsto,
        polygon=polygon.wkt,
        polygon_with_buffer=polygon_with_buffer.wkt,
    )


def parse_kmz(input: Path) -> DJIMetadata:
    root = _get_root_element_from_kmz(input)
    metadata_from_file = _parse_tree(root)

    return metadata_from_file
