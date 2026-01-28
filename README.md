# DJI Metadata Tool

A Python tool for extracting and managing metadata from DJI WPML (Waypoint Mission Language) KMZ files. This tool parses flight mission parameters from DJI drone mission files and combines them with user-provided metadata to create comprehensive flight records.

## Installation

This project uses [uv](https://docs.astral.sh/uv/) for dependency management. If you don't have `uv` installed see [installation page](https://docs.astral.sh/uv/#installation).

Then install the project dependencies:

```sh
uv sync
```

## Usage

Run the tool with a DJI KMZ file as input and specify an output CSV file:

```sh
uv run main.py <input.kmz> <output.csv>
```

### Example

```sh
uv run python main.py kmz_test_files/mission.kmz flight_metadata.csv
```

## TODO

- [ ] Get DSM file for terrain follow
- [ ] Allow input to be directory and run for all kmz files inside (with output to a single csv)
