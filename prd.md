# Recipe Importer — Product Requirements Document

## Overview
A Python CLI tool that takes a recipe from a URL or photo(s), reformats it using the Claude API according to specific editing rules, and exports a `.paprikarecipe` file. Phase 2 adds direct upload to Paprika 3 cloud. Phase 3 adds a web UI as a PWA for mobile use.

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

## Phase 3: Web App (PWA)

A mobile-friendly web UI deployed on a cloud VPS, installable as a PWA on Android (Add to Home Screen, no app store).

### Key Decisions
- **Backend:** FastAPI (async Python, reuses existing pipeline modules)
- **Frontend:** React + Vite + TypeScript
- **PWA:** `vite-plugin-pwa` for service worker and manifest generation
- **Deployment:** Single Docker container (FastAPI serves built frontend as static files), Caddy reverse proxy for automatic HTTPS
- **Auth:** Shared secret (`APP_SECRET` in `.env`), sent as `Authorization: Bearer <token>`. Stored in `localStorage` on the frontend after one-time login.
- **Categories:** Fetched from Paprika API (`/sync/categories/`), user selects before saving

### Features
1. **Import from URL** — paste a recipe URL
2. **Import from image upload** — upload or take photo(s) from phone camera (`capture="environment"`)
3. **Edit name and source** — editable fields on the preview screen
4. **Category picker** — multi-select from the user's existing Paprika categories
5. **Recipe preview** — see formatted ingredients/directions before saving
6. **Quick import** — optional checkbox to skip preview and sync directly to Paprika

### User Flow
1. Login: enter `APP_SECRET` once (stored in `localStorage`)
2. Import screen: toggle URL / Photo, optional "Quick Import" checkbox
3. Loading: backend scrapes URL or processes images, then calls Claude API
4. Preview screen (unless quick import): edit name, source, pick categories, review formatted recipe
5. Confirm → sync to Paprika → success → "Import Another"

### Architecture

```
Android (PWA) → Caddy (HTTPS/Let's Encrypt) → FastAPI (uvicorn :8000)
                                                  ├── POST /api/import/url
                                                  ├── POST /api/import/images
                                                  ├── GET  /api/categories
                                                  ├── POST /api/sync
                                                  └── GET  / (static React build)
```

### API Endpoints

#### `POST /api/import/url`
- Body: `{ "url": "https://...", "quick": false }`
- Calls `scraper.scrape_url()` → `formatter.format_recipe()`
- Returns: `{ "recipe": { name, ingredients, directions, prep_time, cook_time, servings, notes, source_url, source, photo_data, image_url } }`
- If `quick: true`: also syncs to Paprika, returns `{ "recipe": ..., "synced": true }`

#### `POST /api/import/images`
- Multipart form: `images` (multiple files) + `quick` (boolean)
- Reads uploaded bytes → base64 → `formatter.format_recipe(images=...)`
- Returns same shape as URL import

#### `GET /api/categories`
- Calls Paprika API `GET /sync/categories/`
- Returns: `{ "categories": ["Breakfast", "Dinner", ...] }`

#### `POST /api/sync`
- Body: `{ "name", "source", "source_url", "categories", "ingredients", "directions", "prep_time", "cook_time", "servings", "notes", "photo_data", "image_url" }`
- Builds Paprika JSON via `build_paprika_json()`, checks for duplicate names, uploads
- Returns: `{ "success": true, "name": "final name" }`

### Project Structure
```
backend/
├── __init__.py
├── main.py              # FastAPI app, static file mount, CORS (dev)
├── api.py               # Route definitions
├── auth.py              # Bearer token middleware
├── schemas.py           # Pydantic models
└── services.py          # Wraps existing modules for async web use

frontend/
├── vite.config.ts       # Vite + PWA plugin config
├── public/              # Icons (192x192, 512x512)
└── src/
    ├── App.tsx
    ├── api.ts           # Fetch wrapper with auth header
    ├── components/
    │   ├── ImportForm.tsx
    │   ├── RecipePreview.tsx
    │   ├── CategoryPicker.tsx
    │   └── StatusBar.tsx
    ├── hooks/
    │   └── useImport.ts # State machine: idle→loading→preview→syncing→success
    └── types.ts

Dockerfile               # Multi-stage: Node build → Python runtime
docker-compose.yml       # App + Caddy
Caddyfile
```

### Changes to Existing Modules
- `exporter.py`: Make `_build_paprika_json()` public, add optional `categories` parameter
- `formatter.py`: Replace `sys.exit(1)` with raised exceptions (web process must not exit)
- All other modules used as-is, wrapped with `asyncio.to_thread()` in the backend services layer

### New Dependencies
```toml
# pyproject.toml
"fastapi>=0.115.0",
"uvicorn[standard]>=0.32.0",
"python-multipart>=0.0.12",
```

### PWA Config
- `display: "standalone"`, `theme_color`, app icons
- Service worker: NetworkFirst for API calls, CacheFirst for static assets
- HTTPS required (Caddy handles this automatically)
