# Decouple Web App from CLI — Inline Shared Modules into Backend

## Context

The web app currently imports from `src/recipe_importer/` (the CLI's package). This creates unwanted coupling — changes to the web app risk breaking the CLI. The CLI is kept for historic reference only. The goal is to make the backend fully self-contained by inlining the relevant logic into `backend/`, with zero imports from `recipe_importer`.

## What the backend currently imports from `src/recipe_importer/`

From `backend/services.py`:
- `scrape_url` from `scraper.py` — URL fetching + recipe-scrapers + trafilatura fallback
- `format_recipe` from `formatter.py` — Claude API call + JSON parsing (uses `prompts.py` internally)
- `build_paprika_json` from `exporter.py` — builds Paprika JSON schema
- `PaprikaClient` from `paprika_api.py` — only `upload_recipe()` method used

## Plan

### New backend file structure

```
backend/
├── __init__.py          # (unchanged)
├── main.py              # (unchanged)
├── api.py               # (unchanged)
├── auth.py              # (unchanged)
├── schemas.py           # (unchanged)
├── services.py          # Remove all recipe_importer imports, call new local modules
├── scraper.py           # NEW — inlined from src/recipe_importer/scraper.py
├── formatter.py         # NEW — inlined from src/recipe_importer/formatter.py + prompts.py merged in
├── paprika.py           # NEW — inlined from exporter.py (build_paprika_json) + paprika_api.py (upload only)
```

### File-by-file changes

#### 1. Create `backend/scraper.py`
- Copy `src/recipe_importer/scraper.py` logic
- Remove `download_photo` parameter and `_download_photo()` function entirely (web app doesn't use photos)
- Keep: `scrape_url()`, `_fetch_html()`, `_extract_structured()`, `_safe_call()`
- Still extract `image` URL from structured data (used as `image_url` in Paprika JSON, even if we can't upload the actual photo data)

#### 2. Create `backend/formatter.py`
- Merge `src/recipe_importer/formatter.py` and `src/recipe_importer/prompts.py` into one file
- Keep: `SYSTEM_PROMPT`, message builders, `format_recipe()`, `_parse_response()`, `_fix_json_newlines()`, `_get_client()`
- Remove: `_print_api_key_error()` (CLI-only)

#### 3. Create `backend/paprika.py`
- Combine the parts we need from `exporter.py` and `paprika_api.py`
- From `exporter.py`: `build_paprika_json()` only (not `export_recipe`, `_slugify`, `_unique_filename` — those are CLI file export)
- From `paprika_api.py`: `PaprikaClient` class with only `__init__` and `upload_recipe()` (not `get_existing_names`, `_fetch_names`, `_fetch_one_name` — duplicate checking removed)
- Remove: `_print_credentials_error()` (CLI-only)

#### 4. Update `backend/services.py`
- Change imports from `recipe_importer.*` to local `backend.*` modules:
  - `from .scraper import scrape_url`
  - `from .formatter import format_recipe`
  - `from .paprika import build_paprika_json, PaprikaClient`
- Remove `download_photo=False` parameter (no longer needed since local scraper won't download photos)

#### 5. Revert `src/recipe_importer/scraper.py`
- Remove the `download_photo` parameter added for the web app (restore original signature)

#### 6. Update `pyproject.toml`
- Remove `backend*` from package discovery (backend is no longer part of the installed package, it runs standalone)

### Files NOT changed
- `backend/main.py`, `backend/api.py`, `backend/auth.py`, `backend/schemas.py` — no changes needed
- `frontend/` — no changes needed
- `src/recipe_importer/` — revert the `download_photo` parameter on scraper.py, otherwise leave untouched
- `Dockerfile`, `docker-compose.yml`, `Caddyfile` — no changes needed

## Verification

1. Start backend: `DEV_MODE=1 uvicorn backend.main:app --reload`
2. Start frontend: `cd frontend && npm run dev`
3. Verify no imports from `recipe_importer` in backend: `grep -r "from recipe_importer" backend/`
4. Test URL import, image import, categories, and sync via the tunnel on phone
