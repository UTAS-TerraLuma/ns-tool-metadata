import json
from pathlib import Path
from typing import Annotated

import typer
from rich import print

from dji_metadata_tool.dji_wpml import parse_kmz

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
    print(ascii)


def extract_and_save(kmz: Path):
    try:
        print(f"Extracting metadata from {kmz.name}")
        metadata = parse_kmz(kmz)
        kmz_json = kmz.with_suffix(".json")
        geojson = metadata.to_geojson_feature()
        kmz_json.write_text(json.dumps(geojson, indent=4))
    except Exception as e:
        print(f"Error parsing {kmz}\n{e}")


@app.command()
def main(
    input: Annotated[
        Path,
        typer.Argument(
            help="Input directory or file. If directory, it will recursively search for any .kmz files",
            file_okay=True,
            dir_okay=True,
            readable=True,
            resolve_path=True,
        ),
    ],
):
    title()

    if input.is_file():
        assert input.suffix == ".kmz", "If a file it must be a kmz file."
        extract_and_save(input)
    else:
        kmzs = input.rglob("*.kmz")
        for kmz in kmzs:
            extract_and_save(kmz)


if __name__ == "__main__":
    app()
