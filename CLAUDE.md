# Recipe Importer

## Build & Install
```bash
uv venv .venv
uv pip install -e . --python .venv/bin/python
source .venv/bin/activate
```

## Run
```bash
# From URL
recipe-importer import --url <url>

# From image(s)
recipe-importer import --image photo1.jpg
recipe-importer import --image photo1.jpg --image photo2.jpg

# Options
recipe-importer import --url <url> --output /custom/path
recipe-importer import --url <url> --verbose
recipe-importer import --url <url> --sync   # Upload to Paprika cloud
```

## Setup
Copy `.env.example` to `.env` and add your API key:
```
ANTHROPIC_API_KEY=sk-ant-...
PAPRIKA_EMAIL=...        # For --sync
PAPRIKA_PASSWORD=...     # For --sync
```

## Architecture

```
src/recipe_importer/
├── cli.py            # Click CLI entry point
├── scraper.py        # URL fetch + recipe-scrapers + trafilatura fallback
├── image_reader.py   # Image loading + base64 encoding
├── formatter.py      # Claude API call + JSON response parsing
├── exporter.py       # .paprikarecipe file creation (gzipped JSON)
├── prompts.py        # System prompt with formatting rules
└── paprika_api.py    # Paprika 3 cloud sync client
```

### Pipeline
1. **Input**: URL → `scraper.py` or images → `image_reader.py`
2. **Format**: `formatter.py` sends to Claude with rules from `prompts.py`
3. **Export**: `exporter.py` creates gzipped `.paprikarecipe` in `~/paprika_recipes/`
4. **Sync** (optional): `paprika_api.py` uploads to Paprika cloud

### Key details
- Claude model: `claude-sonnet-4-5-20250929`
- Output: `~/paprika_recipes/` (default), override with `--output`
- Duplicate handling: auto-rename with `-2`, `-3` suffix
- API retries: 3 attempts with exponential backoff
