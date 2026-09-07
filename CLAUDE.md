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
GEMINI_API_KEY=...          # Google AI Studio
GOOGLE_CLIENT_ID=...        # Google OAuth
GOOGLE_CLIENT_SECRET=...
GOOGLE_REDIRECT_URI=...
JWT_SECRET=...              # JWT signing secret
ENCRYPTION_KEY=...          # Fernet key for Paprika passwords
ALLOWED_EMAILS=...          # Comma-separated Google account allowlist
FRONTEND_URL=...            # e.g. http://localhost:5173
DATABASE_URL=...            # PostgreSQL connection string
```

## Architecture

```
src/recipe_importer/
├── cli.py            # Click CLI entry point
├── scraper.py        # URL fetch + recipe-scrapers + trafilatura fallback
├── image_reader.py   # Image loading + base64 encoding
├── formatter.py      # Gemini API call + JSON response parsing
├── exporter.py       # .paprikarecipe file creation (gzipped JSON)
├── prompts.py        # System prompt with formatting rules
└── paprika_api.py    # Paprika 3 cloud sync client

backend/
├── main.py              # FastAPI app, static file serving, CORS
├── api.py               # Import, category, sync, and credential routes
├── formatter.py         # PWA Gemini call and strict plural response parsing
├── prompts.py           # Shared URL/image/text formatting rules
├── scraper.py           # Safe conventional recipe-page extraction
├── social_extractor.py  # YouTube/Instagram public metadata extraction
├── url_safety.py        # DNS, address, and redirect validation
├── auth.py              # Bearer token authentication
├── schemas.py           # Pydantic request/response models
└── services.py          # Async orchestration and import limits

frontend/              # React + Vite + TypeScript + shadcn/ui PWA
├── src/
│   ├── App.tsx        # Main app with state-based routing
│   ├── api.ts         # Fetch wrapper (Bearer token)
│   ├── types.ts       # TypeScript types
│   ├── hooks/useImport.ts  # Import, selection, review queue, and sync state
│   └── components/    # Login, import, selection, review, categories, status
└── vite.config.ts     # Vite + PWA + Tailwind v4
```

### Web pipeline
1. **Input**: safe recipe page, YouTube/Instagram public metadata, images, or pasted text
2. **Format**: `backend/formatter.py` applies the shared PWA prompt and validates a strict plural batch
3. **Review**: one recipe opens directly; multiple recipes use selection and a source-ordered in-memory queue
4. **Sync**: `/api/sync` uploads exactly one reviewed recipe per request

The CLI remains separate and continues to export `.paprikarecipe` files through `src/recipe_importer`.

### Key details
- Gemini model: `gemini-2.5-flash`
- Output: `~/paprika_recipes/` (default), override with `--output`
- Duplicate handling: auto-rename with `-2`, `-3` suffix
- API retries: 3 attempts with exponential backoff
- Web app: dark theme, golden/amber accent, mobile-first PWA
- Deployment: Docker multi-stage build + Caddy for HTTPS
- Web import limits: 10 images, 10 MiB per image, 100,000 source characters, and 10 recipes per source
- Social imports are best effort, use anonymous public metadata only, and never download media
- Production installs `yt-dlp-ejs` and Deno through `yt-dlp[default,deno]`
