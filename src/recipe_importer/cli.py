"""Click CLI for recipe-importer."""

import logging
import sys
from pathlib import Path

import click
from dotenv import load_dotenv

from .exporter import DEFAULT_OUTPUT_DIR, export_recipe
from .formatter import format_recipe
from .image_reader import read_images
from .scraper import scrape_url


@click.group()
def cli():
    """Import recipes from URLs or photos into Paprika format."""
    pass


@cli.command("import")
@click.option("--url", default=None, help="URL of a recipe to import.")
@click.option(
    "--image",
    multiple=True,
    type=click.Path(exists=True),
    help="Path to a recipe image. Can be specified multiple times.",
)
@click.option(
    "--output",
    default=None,
    type=click.Path(),
    help=f"Output directory (default: {DEFAULT_OUTPUT_DIR}).",
)
@click.option("--verbose", is_flag=True, help="Show detailed debug output.")
@click.option("--sync", is_flag=True, help="Upload recipe to Paprika cloud.")
def import_recipe(url, image, output, verbose, sync):
    """Import a recipe from a URL or image(s)."""
    # Setup
    load_dotenv()
    _setup_logging(verbose)

    # Validate inputs
    if not url and not image:
        click.echo("Error: Provide --url or at least one --image.", err=True)
        sys.exit(1)
    if url and image:
        click.echo("Error: Provide --url or --image, not both.", err=True)
        sys.exit(1)

    output_dir = Path(output).expanduser() if output else None

    try:
        recipe_data = None
        images = None
        photo_data = None
        image_url = None
        source_name = None

        if url:
            click.echo("Scraping recipe...")
            recipe_data = scrape_url(url)
            photo_data = recipe_data.pop("photo_data", None)
            image_url = recipe_data.pop("image", None)
            source_name = recipe_data.pop("site_name", None)

        if image:
            click.echo("Reading images...")
            images = read_images(list(image))

        if not source_name:
            source_name = click.prompt("Enter the recipe source", default="", show_default=False).strip() or ""

        click.echo("Formatting with Claude...")
        formatted = format_recipe(
            recipe_data=recipe_data,
            images=images,
            source_url=url,
        )

        click.echo("Exporting recipe...")
        output_path = export_recipe(
            recipe=formatted,
            source_url=url,
            source_name=source_name,
            photo_data=photo_data,
            image_url=image_url,
            output_dir=output_dir,
        )

        click.echo(f"Saved to {output_path}")

        if sync:
            from .paprika_api import PaprikaClient

            import gzip
            import json

            with gzip.open(output_path, "rb") as f:
                paprika_data = json.loads(f.read())

            client = PaprikaClient()

            click.echo("Checking for duplicates in Paprika cloud...")
            existing_names = client.get_existing_names()
            recipe_name = paprika_data["name"]
            unique_name = _unique_cloud_name(recipe_name, existing_names)
            if unique_name != recipe_name:
                click.echo(f"Renamed to '{unique_name}' (duplicate in Paprika cloud)")
                paprika_data["name"] = unique_name

            click.echo("Uploading to Paprika cloud...")
            client.upload_recipe(paprika_data)
            click.echo("Uploaded to Paprika cloud.")
            if photo_data:
                click.echo("Note: Photos cannot be synced via the API. Import the .paprikarecipe file in the app for photos.")

    except KeyboardInterrupt:
        click.echo("\nAborted.", err=True)
        sys.exit(130)
    except Exception as e:
        if verbose:
            raise
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


def _unique_cloud_name(name: str, existing_names: set[str]) -> str:
    """Generate a unique recipe name for Paprika cloud."""
    if name.lower() not in existing_names:
        return name
    counter = 2
    while True:
        candidate = f"{name} ({counter})"
        if candidate.lower() not in existing_names:
            return candidate
        counter += 1


def _setup_logging(verbose: bool):
    """Configure logging based on verbosity."""
    level = logging.DEBUG if verbose else logging.WARNING
    logging.basicConfig(
        level=level,
        format="%(name)s: %(message)s",
    )
