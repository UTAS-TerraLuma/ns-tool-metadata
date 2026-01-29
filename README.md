# DJI Metadata Tool

A Python tool for extracting and managing metadata from DJI WPML (Waypoint Mission Language) KMZ files. This tool parses flight mission parameters from DJI drone mission files and combines them with user-provided metadata to create comprehensive flight records.

## Installation

### Option 1: Install as a tool (Recommended)

Install directly from GitHub using `uv`:

```sh
uv tool install git+https://github.com/UTAS-TerraLuma/dji-metadata-tool
```

Or install from a local directory:

```sh
uv tool install /path/to/dji-metadata-tool
```

This installs the tool globally and allows you to run it from anywhere.

### Option 2: Development installation

If you want to contribute or modify the code, clone the repository and install dependencies:

This project uses [uv](https://docs.astral.sh/uv/) for dependency management. If you don't have `uv` installed see [installation page](https://docs.astral.sh/uv/#installation).

```sh
git clone https://github.com/UTAS-TerraLuma/dji-metadata-tool
cd dji-metadata-tool
uv sync
```

## Usage

### If installed with `uv tool install`:

```sh
dji-metadata-tool <input.kmz>

# Optionally provide a path to an output CSV
dji-metadata-tool <input.kmz> --output <output.csv>
```

### If running from source (development):

```sh
uv run main.py <input.kmz>

# Optionally provide a path to an output CSV
uv run main.py <input.kmz> --output <output.csv>
```

### Example

```sh
# Using installed tool
dji-metadata-tool kmz_test_files/mission.kmz
# This will create output at kmz_test_files/mission.csv

# Or from source
uv run main.py kmz_test_files/mission.kmz
```

The tool will:

1. Extract metadata from the KMZ file (platform, flight height, speed, overlaps, etc.)
2. Prompt you to enter additional metadata (site name, white balance, weather conditions, etc.)
3. Save all metadata to a CSV file

## TODO

- [ ] Get DSM file for terrain follow
