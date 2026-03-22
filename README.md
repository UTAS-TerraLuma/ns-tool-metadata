# DJI Metadata Tool

A Python tool for extracting and managing metadata from DJI WPML (Waypoint Mission Language) KMZ files. This tool parses flight mission parameters from DJI drone mission files and combines them with user-provided metadata to create comprehensive flight records.

## TODO
- [ ] Add tests
- [ ] Default to NatureScan_drone directory
- [ ] Use to push user metadata down to individual surveys. Aka split into drone metadata and user metadata

## Requirements

- [pixi](https://pixi.sh)

## Install

```sh
git clone https://github.com/UTAS-TerraLuma/dji-metadata-tool
cd dji-metadata-tool
pixi install
```

## Usage

```sh
pixi run metadata-tool <input.kmz>
```

Or pass a directory to process all KMZ files recursively:

```sh
pixi run metadata-tool <directory>
```

### Example

```sh
pixi run metadata-tool kmz_test_files/1_simple/20250724-SAABHC0005-m3m-50mAGL.kmz
```

The tool will:

1. Extract metadata from the KMZ file (platform, flight height, speed, overlaps, etc.)
2. Prompt you to enter additional metadata (site name, white balance, weather conditions, etc.)
3. Save all metadata to a GeoJSON file

## TODO

- [ ] Get DSM file for terrain follow
