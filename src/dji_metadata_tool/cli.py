import json
from pathlib import Path
from typing import Annotated

import pandas as pd
import typer
from rich import print

from dji_metadata_tool.dji_wpml import parse_kmz

app = typer.Typer(add_completion=False)

NATURESCAN_DRONE_DIR = Path(
    R"R:\CoSE\GPSS\TerraLuma\_data\NatureScan_data\NatureScan_drone"
)


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
        geojson = metadata.to_geojson_feature()
        kmz_json = kmz.with_suffix(".json")
        kmz_json.write_text(json.dumps(geojson, indent=4))
    except Exception as e:
        print(f"Error parsing {kmz}\n{e}")


def parse_survey_uid(survey_uid: str) -> tuple[str, str, str]:
    parts = survey_uid.split("_")
    if len(parts) != 3:
        raise typer.BadParameter(
            f"Survey UID must be SITE_DATE_TAG (3 parts separated by '_'), "
            f"got {len(parts)} parts: {survey_uid!r}"
        )
    return parts[0], parts[1], parts[2]


def _process_survey(survey_uid: str, metadata_dir: Path, overwrite: bool, warn_only: bool = False) -> str:
    """Process a single survey's metadata folder.

    Returns "written", "skipped", or "warning".
    warn_only: print warnings instead of fatal errors (used when iterating all surveys).
    """
    kmzs = list(metadata_dir.glob("*.kmz"))
    if not kmzs:
        if warn_only:
            print(f"[yellow]Warning: no .kmz found in {metadata_dir}, skipping.[/yellow]")
            return "warning"
        print(f"[red]Error: no .kmz file found in {metadata_dir}[/red]")
        raise typer.Exit(1)
    if len(kmzs) > 1:
        names = [k.name for k in kmzs]
        if warn_only:
            print(f"[yellow]Warning: multiple .kmz files in {metadata_dir}: {names}, skipping.[/yellow]")
            return "warning"
        print(f"[red]Error: multiple .kmz files found in {metadata_dir}: {names}[/red]")
        raise typer.Exit(1)

    k = kmzs[0]
    target_kmz = metadata_dir / f"{survey_uid}.kmz"
    target_json = metadata_dir / f"{survey_uid}.json"

    if k != target_kmz:
        print(f"Renaming {k.name} -> {target_kmz.name}")
        k.rename(target_kmz)
        k = target_kmz

    if target_json.exists() and not overwrite:
        print(
            f"[green]{target_json.name} already exists, skipping. "
            f"Use --overwrite to re-extract.[/green]"
        )
        return "skipped"

    extract_and_save(k)
    return "written"


@app.command()
def kmz(
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
    """Extract DJI WPML KMZ metadata to GeoJSON from a file or directory."""
    title()

    if input.is_file():
        assert input.suffix == ".kmz", "If a file it must be a kmz file."
        extract_and_save(input)
    else:
        for k in input.rglob("*.kmz"):
            extract_and_save(k)


@app.command()
def survey(
    survey_uid: Annotated[
        str,
        typer.Argument(help='Survey UID in SITE_DATE_TAG format, or "all" to process every survey'),
    ],
    overwrite: Annotated[
        bool,
        typer.Option("--overwrite", help="Overwrite existing output files"),
    ] = False,
) -> None:
    """Extract KMZ metadata for a NatureScan survey using standard directory layout."""
    title()

    if survey_uid == "all":
        counts = {"written": 0, "skipped": 0, "warning": 0}
        # Glob survey_* dirs two levels deep; non-survey siblings are excluded by the prefix filter
        survey_dirs = sorted(NATURESCAN_DRONE_DIR.glob("*/*/survey_*"))
        for survey_dir in survey_dirs:
            if not survey_dir.is_dir():
                continue
            site = survey_dir.parent.parent.name
            date = survey_dir.parent.name
            tag = survey_dir.name[len("survey_"):]
            uid = f"{site}_{date}_{tag}"
            metadata_dir = survey_dir / "metadata"
            if not metadata_dir.is_dir():
                continue
            print(f"\n[bold]Processing {uid}[/bold]")
            result = _process_survey(uid, metadata_dir, overwrite, warn_only=True)
            counts[result] += 1
        print(
            f"\n[bold]Summary:[/bold] "
            f"{counts['written']} written, "
            f"{counts['skipped']} skipped, "
            f"{counts['warning']} warnings"
        )
        return

    site, date, tag = parse_survey_uid(survey_uid)
    metadata_dir = NATURESCAN_DRONE_DIR / site / date / f"survey_{tag}" / "metadata"
    if not metadata_dir.is_dir():
        print(f"[red]Error: metadata directory does not exist: {metadata_dir}[/red]")
        raise typer.Exit(1)

    _process_survey(survey_uid, metadata_dir, overwrite, warn_only=False)


USER_METADATA_EXCEL = NATURESCAN_DRONE_DIR / "user_metadata.xlsx"

_EXCEL_COLUMNS_TO_DROP = [
    "open_folder",
    "old_mission",
    "archive_mission",
    "open_old_mission_folder",
    "old_mission_file_name",
]


@app.command("user-metadata")
def user_metadata(
    overwrite: Annotated[
        bool,
        typer.Option("--overwrite", help="Overwrite existing output files"),
    ] = False,
) -> None:
    """Write user metadata from the Excel sheet to each survey's metadata folder."""
    title()

    if not USER_METADATA_EXCEL.exists():
        print(f"[red]Error: Excel file not found: {USER_METADATA_EXCEL}[/red]")
        raise typer.Exit(1)

    df = pd.read_excel(USER_METADATA_EXCEL, dtype={"date": str}).drop(
        columns=_EXCEL_COLUMNS_TO_DROP, errors="ignore"
    )

    counts = {"written": 0, "skipped": 0, "warning": 0}

    for row in df.itertuples(index=False):
        survey_uid = row.survey_uid
        print(f"\n[bold]Processing {survey_uid}[/bold]")

        metadata_dir = Path(row.folder) / "metadata"
        if not metadata_dir.is_dir():
            print(f"[yellow]Warning: metadata folder does not exist: {metadata_dir}, skipping.[/yellow]")
            counts["warning"] += 1
            continue

        output_file = metadata_dir / f"{survey_uid}_user.json"
        if output_file.exists() and not overwrite:
            print(f"[green]{output_file.name} already exists, skipping. Use --overwrite to rewrite.[/green]")
            counts["skipped"] += 1
            continue

        row_dict = row._asdict()
        row_dict.pop("folder", None)
        row_dict = {k: (None if pd.isna(v) else v) for k, v in row_dict.items()}

        old_file = metadata_dir / "user_metadata.json"
        if old_file.exists():
            old_file.unlink()

        output_file.write_text(json.dumps(row_dict, indent=4))
        print(f"Written {output_file.name}")
        counts["written"] += 1

    print(
        f"\n[bold]Summary:[/bold] "
        f"{counts['written']} written, "
        f"{counts['skipped']} skipped, "
        f"{counts['warning']} warnings"
    )


if __name__ == "__main__":
    app()
