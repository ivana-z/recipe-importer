# Recipe Importer

A CLI tool that imports recipes from URLs or photos, reformats them using Claude, and exports to Paprika 3 format.

## Features

- **URL scraping** — extracts recipes from any recipe website using [recipe-scrapers](https://github.com/hhursev/recipe-scrapers) with [trafilatura](https://github.com/adbar/trafilatura) fallback
- **Photo import** — extracts recipes from images using Claude's vision API
- **Smart formatting** — converts imperial to metric, structures directions into chapters, bolds ingredients
- **Paprika export** — generates `.paprikarecipe` files (gzipped JSON) ready for import
- **Cloud sync** — uploads recipes directly to Paprika 3 cloud (text only, photos require file import)
- **Duplicate handling** — auto-renames files and cloud recipes when duplicates exist

## Setup

```bash
# Clone and install
git clone https://github.com/ivana-z/recipe-importer.git
cd recipe-importer
uv venv .venv
uv pip install -e . --python .venv/bin/python
source .venv/bin/activate

# Configure API key
cp .env.example .env
# Edit .env and add your ANTHROPIC_API_KEY
```

## Usage

```bash
# Import from URL
recipe-importer import --url "https://www.seriouseats.com/some-recipe"

# Import from photo(s)
recipe-importer import --image photo.jpg
recipe-importer import --image page1.jpg --image page2.jpg

# It supports .jpg, .jpeg, .png, .gif, and .webp formats. Paths can be relative, absolute, or use ~ for your home directory (e.g., ~/Downloads/recipe.jpeg).

# Import and sync to Paprika cloud
recipe-importer import --url "https://example.com/recipe" --sync

# Custom output directory
recipe-importer import --url "https://example.com/recipe" --output ./my-recipes

# Debug output
recipe-importer import --url "https://example.com/recipe" --verbose
```

Recipes are saved to `~/paprika_recipes/` by default.

## Cloud Sync

To upload recipes directly to your Paprika 3 account, add your credentials to `.env`:

```
PAPRIKA_EMAIL=your@email.com
PAPRIKA_PASSWORD=your_password
```

Then use the `--sync` flag. Note: photos cannot be synced via the API — import the `.paprikarecipe` file directly in the Paprika app for photos.

## Formatting Rules

The tool applies these formatting rules automatically:

- **Ingredients**: metric conversions (except tbsp/tsp), butter always in grams, Celsius only
- **Directions**: structured into bold chapters, ingredients bolded with quantities on first mention
- **Units**: under 1L/1kg rounds to nearest 5 (ml/g), over 1L/1kg rounds to nearest 0.05 (L/kg)
