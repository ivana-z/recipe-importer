# Recipe Importer

A tool that imports recipes from URLs or photos, reformats them using Gemini, and syncs to Paprika 3. Available as a web app (PWA) and a CLI.

## Features

- **URL import** — extracts recipes from any recipe website using [recipe-scrapers](https://github.com/hhursev/recipe-scrapers) (with `wild_mode` for sites not explicitly supported) and [trafilatura](https://github.com/adbar/trafilatura) fallback
- **Photo import** — extracts recipes from images using Gemini's vision API
- **Smart formatting** — translates to English, converts imperial to metric, structures directions into chapters, bolds ingredients on first mention
- **Paprika sync** — uploads recipes directly to Paprika 3 cloud
- **Android share sheet** — share a recipe URL or page (including Google app "title + link" shares) directly to the app (PWA)
- **Duplicate handling** — auto-renames local `.paprikarecipe` files if a file with the same name already exists

## Web App

The web app is a mobile-first PWA with Google OAuth login and per-user Paprika credentials.

### Running locally

```bash
# Backend (from project root)
DEV_MODE=1 uvicorn backend.main:app --reload

# Frontend (separate terminal)
cd frontend && npm run dev
```

Copy `.env.example` to `.env` and fill in:

```
GEMINI_API_KEY=...          # Google AI Studio
GOOGLE_CLIENT_ID=...        # Google OAuth
GOOGLE_CLIENT_SECRET=...
GOOGLE_REDIRECT_URI=...
JWT_SECRET=...              # Random secret for JWT signing
ENCRYPTION_KEY=...          # Fernet key for encrypting Paprika passwords
ALLOWED_EMAILS=...          # Comma-separated list of allowed Google accounts
FRONTEND_URL=...            # e.g. http://localhost:5173
DATABASE_URL=...            # PostgreSQL connection string
```

### Deployment

The app is designed to deploy on [Railway](https://railway.app):
- Connect your GitHub repo for auto-deploy on push to `master`
- Add a PostgreSQL add-on (DATABASE_URL is injected automatically)
- Set the environment variables listed above

### Android PWA

Install the web app from Chrome ("Add to Home Screen"). Once installed, it appears in Android's share sheet — you can share a recipe URL directly from Chrome, or use the Google app's share which sends a "title + link" text, and the app extracts the URL automatically.

---

## CLI

### Setup

```bash
uv venv .venv
uv pip install -e . --python .venv/bin/python
source .venv/bin/activate
```

Copy `.env.example` to `.env` and add:

```
GEMINI_API_KEY=...       # Google AI Studio
PAPRIKA_EMAIL=...        # For --sync
PAPRIKA_PASSWORD=...     # For --sync
```

### Usage

```bash
# Import from URL
recipe-importer import --url "https://www.seriouseats.com/some-recipe"

# Import from photo(s)  (.jpg, .jpeg, .png, .gif, .webp)
recipe-importer import --image photo.jpg
recipe-importer import --image page1.jpg --image page2.jpg

# Sync to Paprika cloud
recipe-importer import --url "https://example.com/recipe" --sync

# Custom output directory
recipe-importer import --url "https://example.com/recipe" --output ./my-recipes

# Verbose output
recipe-importer import --url "https://example.com/recipe" --verbose
```

Recipes are saved to `~/paprika_recipes/` by default as `.paprikarecipe` files (gzipped JSON).

---

## Formatting Rules

Applied automatically to all imported recipes:

- **Language**: translated to English regardless of source language
- **Ingredients**: one per line, quantity first, no bullets; ingredients with no specific quantity (q.b./as needed) listed by name only
- **Units**: tbsp/tsp stay as-is; butter converts to grams; pourable liquids in cups convert to ml; all other imperial (oz, lb, fl oz, pints, quarts, gallons) converts to metric
- **Temperatures**: Celsius only, Fahrenheit references removed
- **Directions**: structured into bold chapters (e.g. **Preparation**, **Cooking**); ingredients bolded with quantity on first mention
