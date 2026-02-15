# Recipe Importer — Product Requirements Document

## Overview
A Python CLI tool that takes a recipe from a URL or photo(s), reformats it using the Claude API according to specific editing rules, and exports a `.paprikarecipe` file. Phase 2 adds direct upload to Paprika 3 cloud.

## Key Decisions
- **Output folder:** `~/paprika_recipes/` (fixed default, overridable with `--output`)
- **Claude model:** Sonnet 4.5 (`claude-sonnet-4-5-20250929`)
- **API key:** `.env` file in project root via `python-dotenv` (also for Paprika creds in Phase 2)
- **Photos:** Download & embed as base64 `photo_data` in the `.paprikarecipe` file
- **Multiple images:** Combine into one recipe (all images sent to Claude together)
- **Duplicates:** Auto-rename with numeric suffix (`recipe-name-2.paprikarecipe`)
- **Error recovery:** Retry Claude API calls up to 3 times with exponential backoff
- **Formatting rules:** Fixed/hardcoded (no customization)
- **Categories/tags:** Skip — core fields only
- **HTML fallback:** Extract main content with `trafilatura` before sending to Claude
- **Missing API key:** Clear error message with setup instructions, then exit
- **HTTP library:** `httpx`
- **Verbosity:** Clean output by default, `--verbose` flag for debug details

## Recipe Formatting Rules

### Ingredients
- Each ingredient on its own line, no bullet points
- Format: quantity first, then ingredient name
- Multi-part recipes (marinade, sauce, dressing): list ingredients under each part title
- Abbreviations: `tbsp` for tablespoons, `tsp` for teaspoons
- Show only one unit of measurement + quantity per ingredient
- Do NOT convert tbsp/tsp quantities, EXCEPT for butter (convert to grams)
- Non-liquid ingredients: keep quantity in cups
- Unit conversions for all other imperial units:
  - Under 1L / 1kg: convert to millilitres (ml) and grams (g), round up to nearest 5
  - Over 1L / 1kg: convert to litres (L) and kilograms (kg), round up to nearest 0.05
- Temperatures: Celsius only (°C), delete any gas mark references

### Directions
- Structure into chapters with bold titles (e.g., `**Soaking**`)
- Convert amounts in directions using same rules as ingredients
- Bold each ingredient name when mentioned, include quantity

## Paprika Recipe Schema
The `.paprikarecipe` file is gzipped JSON with these fields:
- `uid` — UUID4 string
- `name` — recipe title
- `ingredients` — formatted ingredients text
- `directions` — formatted directions text
- `source` — original URL (if from URL)
- `photo_data` — base64-encoded image
- `prep_time` — preparation time string
- `cook_time` — cooking time string
- `servings` — servings string
- `notes` — additional notes
- `created` — ISO 8601 timestamp
- `hash` — SHA-256 hash of the JSON content

## CLI Interface
```
recipe-importer import --url <url>
recipe-importer import --image <path> [--image <path2>]
recipe-importer import --url <url> --sync          # Phase 2
recipe-importer import --url <url> --output <dir>
recipe-importer import --url <url> --verbose
```

## Phase 1: Core Pipeline
1. URL scraping with `recipe-scrapers` + `trafilatura` fallback
2. Image loading and base64 encoding
3. Claude API formatting with retry logic
4. `.paprikarecipe` export with gzip

## Phase 2: Paprika Cloud Sync
1. `PaprikaClient` with HTTP Basic Auth
2. `--sync` flag on CLI
3. Credentials from `.env`: `PAPRIKA_EMAIL`, `PAPRIKA_PASSWORD`
