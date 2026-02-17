# Recipe Importer

## Build & Install
```bash
uv venv .venv
uv pip install -e . --python .venv/bin/python
source .venv/bin/activate
```

## Run (CLI)
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

## Run (Web App)
```bash
# Backend (from project root)
DEV_MODE=1 uvicorn backend.main:app --reload

# Frontend (separate terminal)
cd frontend && npm run dev

# Production (Docker)
docker compose up --build
```

## Setup
Copy `.env.example` to `.env` and add your keys:
```
ANTHROPIC_API_KEY=sk-ant-...
PAPRIKA_EMAIL=...        # For --sync and web app
PAPRIKA_PASSWORD=...     # For --sync and web app
APP_SECRET=...           # For web app auth
DOMAIN=recipes.example.com  # For production deployment
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

backend/
├── main.py           # FastAPI app, static file serving, CORS
├── api.py            # API route definitions (/api/import/url, /api/import/images, /api/categories, /api/sync)
├── auth.py           # Bearer token auth (APP_SECRET)
├── schemas.py        # Pydantic request/response models
└── services.py       # Orchestration: wraps existing modules for async web use

frontend/              # React + Vite + TypeScript + shadcn/ui PWA
├── src/
│   ├── App.tsx        # Main app with state-based routing
│   ├── api.ts         # Fetch wrapper (Bearer token)
│   ├── types.ts       # TypeScript types
│   ├── hooks/useImport.ts  # State machine: idle→loading→preview→syncing→success
│   └── components/    # Login, ImportForm, EditRecipe, CategoryPicker, StatusBar
└── vite.config.ts     # Vite + PWA + Tailwind v4
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
- Web app: dark theme, golden/amber accent, mobile-first PWA
- Deployment: Docker multi-stage build + Caddy for HTTPS
