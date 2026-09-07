# Recipe Importer — Application Findings

## Purpose of this document

This is a pre-feature implementation assessment of the repository as it exists. It records the current behavior, architecture, extension points, constraints, and verified baseline so a later feature definition can be converted into `M1-OMP-PLAYBOOK.md` without rediscovering the application.

No application code was changed during this assessment.

## What the application does

Recipe Importer converts recipes from either a web URL or one or more images into a normalized recipe and sends that recipe to Paprika 3. It has two user interfaces:

1. A Python CLI that can create a local `.paprikarecipe` file and optionally upload it to Paprika Cloud.
2. A mobile-first React PWA that signs users in with Google, imports a recipe, allows limited review, and uploads it to Paprika Cloud.

The common conceptual pipeline is:

```text
URL or images
  -> scrape/read source
  -> Gemini extraction and normalization
  -> recipe fields
  -> Paprika JSON
  -> local .paprikarecipe file (CLI) or Paprika Cloud (CLI/web)
```

## Current user flows

### CLI

Entry point: `recipe-importer`, registered in `pyproject.toml` as `recipe_importer.cli:cli`.

Supported command:

```bash
recipe-importer import --url <url>
recipe-importer import --image <path> [--image <path> ...]
```

Options:

- `--output`: override the default `~/paprika_recipes/` destination.
- `--verbose`: expose detailed exceptions/logging.
- `--sync`: upload the generated recipe to Paprika Cloud after writing the local file.

Behavior:

- Exactly one source type is required: one URL or one-or-more images.
- URL imports scrape recipe data and attempt to infer the source site.
- Image imports read and base64-encode supported image types.
- If a source name was not scraped, the CLI interactively asks for it.
- Gemini normalizes the recipe.
- The exporter writes gzipped JSON with a `.paprikarecipe` extension.
- Local filename collisions receive `-2`, `-3`, and subsequent suffixes.
- Optional cloud sync queries existing Paprika recipes and renames duplicate recipe names with `(2)`, `(3)`, and subsequent suffixes.

### Web/PWA

The frontend is a React 19, TypeScript, Vite, Tailwind CSS v4, shadcn/Radix-style mobile interface.

Primary flow:

1. Sign in with Google.
2. Choose URL or Images.
3. Submit the source.
4. Wait while the backend scrapes/reads and Gemini formats it.
5. Review the recipe name and source.
6. Optionally select Paprika categories.
7. Send the recipe to Paprika.
8. Start a new import.

Additional behavior:

- The PWA registers as a Web Share Target at `/share` and extracts a URL from `url` or `text` query parameters.
- The selected import tab and pending image data are stored in `sessionStorage`.
- Authentication JWTs are stored in `localStorage`.
- Settings allow a signed-in user to save Paprika email/password credentials and sign out.
- Paprika passwords are sent over the authenticated HTTPS API and Fernet-encrypted before database storage.
- The frontend state machine is `idle -> loading -> preview -> syncing -> success`, with an `error` branch and reset to `idle`.

Despite the name `EditRecipe`, the review screen currently edits only:

- Recipe name
- Source
- Categories

Ingredients, directions, preparation time, cooking time, servings, notes, and source URL are not shown or editable before sync.

## Recipe contract

The normalized recipe shared by the web API and frontend contains:

```text
name
ingredients
directions
prep_time
cook_time
servings
notes
source_url
source
```

`name`, `ingredients`, and `directions` are required after Gemini formatting. Other formatter fields default to empty strings. The Paprika payload adds identifiers, timestamps, hashes, category data, and Paprika-specific fields with empty/default values.

Web API routes:

| Method | Route | Purpose |
|---|---|---|
| GET | `/api/auth/login` | Return the Google authorization URL and generated OAuth state |
| GET | `/api/auth/callback` | Exchange the Google code, upsert a user, issue a JWT, and redirect |
| POST | `/api/import/url` | Import and format a URL recipe |
| POST | `/api/import/images` | Import and format uploaded recipe images |
| GET | `/api/categories` | Fetch the signed-in user's Paprika category hierarchy |
| POST | `/api/sync` | Build and upload a Paprika recipe |
| GET | `/api/me/credentials` | Return saved-credential status and Paprika email |
| POST | `/api/me/credentials` | Encrypt and save Paprika credentials |

All routes except the two Google authentication routes require a bearer JWT.

The backend import routes support a `quick` flag that attempts immediate Paprika sync and returns `synced`. The current frontend never sends `quick=true` and ignores the `synced` result in its state transitions.

## Source acquisition and model behavior

### URL source

`src/recipe_importer/scraper.py` and `backend/scraper.py` currently contain the same scraping implementation:

1. Fetch with `httpx`, redirects enabled, a browser-like user agent, and a 30-second timeout.
2. Try `recipe-scrapers` structured extraction.
3. Require a title plus ingredients or directions.
4. Fall back to `trafilatura` main-content extraction.
5. Fall back again to passing the complete raw HTML to Gemini.

Structured extraction includes title, ingredients, directions, prep/cook/total time, servings, and site name.

### Image source

Supported types are JPEG, PNG, GIF, and WebP. Images are held as base64 strings before being decoded into Gemini image parts. The web API infers media type from the filename and defaults unknown extensions to JPEG; the CLI rejects unsupported extensions.

### Gemini normalization

Both application paths use `gemini-2.5-flash`, JSON response mode, three attempts, and exponential delays of two then four seconds.

The prompt requires:

- English output.
- One ingredient per line with no bullets.
- Prescribed tbsp/tsp, metric, temperature, length, and rounding rules.
- Chapter-style bold headings in directions.
- First ingredient mentions bolded with quantities.
- No invented ingredients or steps.
- JSON-only output.

There are two maintained copies of the formatter contract:

- CLI: `src/recipe_importer/formatter.py` plus `src/recipe_importer/prompts.py`
- Web: a merged implementation and prompt in `backend/formatter.py`

Feature work affecting extraction, recipe fields, prompt behavior, retries, or model selection must account for both paths or first establish one shared implementation.

## Backend architecture

### FastAPI application

`backend/main.py`:

- Loads `.env`.
- Creates database tables at startup.
- Enables CORS for `http://localhost:5173` when `DEV_MODE` is set.
- Registers authentication and application routers.
- Serves `frontend/dist` as a static SPA in production.

### Service layer

`backend/services.py` moves blocking scraper, Gemini, and Paprika calls to worker threads with `asyncio.to_thread`. Category retrieval uses an async `httpx` client directly.

The web path has its own copies of scraper, formatter, Paprika payload builder, and Paprika client rather than importing the package implementations under `src/recipe_importer/`.

### Authentication and persistence

- Google OAuth supplies identity and email.
- `ALLOWED_EMAILS` optionally restricts access.
- Users are keyed by Google subject and have unique emails.
- The application issues HS256 JWTs valid for 30 days.
- JWT subject is the database user ID.
- Paprika passwords are encrypted with a single environment-provided Fernet key.
- SQLAlchemy supports a configured `DATABASE_URL`; production expects PostgreSQL.
- Schema creation uses `Base.metadata.create_all`; there is no migration framework.
- The only persisted entity is `User`.

### Paprika integration

- Paprika v1 API requests use HTTP Basic Auth.
- Recipe JSON is gzipped and uploaded as multipart data.
- Every web sync creates a new UUID.
- The web sync path does not perform the CLI's duplicate-name query/rename behavior.
- Categories are fetched as a flat Paprika response and transformed into one parent/child level for the UI.

## Frontend architecture

Key files:

- `frontend/src/App.tsx`: authentication gate and top-level state rendering.
- `frontend/src/hooks/useImport.ts`: import/sync state and API orchestration.
- `frontend/src/api.ts`: bearer-token fetch wrapper and endpoint functions.
- `frontend/src/types.ts`: recipe, category, result, and application-state contracts.
- `frontend/src/components/ImportForm.tsx`: URL/image input and session persistence.
- `frontend/src/components/EditRecipe.tsx`: limited review plus sync action.
- `frontend/src/components/CategoryPicker.tsx`: Paprika category drawer.
- `frontend/src/components/Settings.tsx`: Paprika credentials and logout.
- `frontend/src/components/StatusBar.tsx`: loading, syncing, success, and error messages.
- `frontend/vite.config.ts`: Vite, PWA manifest, API proxy, service worker, and share target.

Routing is state-based inside `App.tsx`; there is no router library. Settings is a boolean branch. Refreshing loses an in-progress normalized recipe and returns to the import screen, while pending images can survive a refresh through `sessionStorage`.

## Deployment and required services

### Production image

The Dockerfile:

1. Builds the frontend with Node 22.
2. Builds a Python 3.12 runtime image.
3. Installs the Python project and backend dependencies.
4. Copies the frontend build into `frontend/dist`.
5. Runs Uvicorn on port 8000.

`docker-compose.yml` runs the app behind Caddy with automatic HTTP/HTTPS exposure.

### Required external configuration

Web operation depends on:

- Gemini API key.
- Google OAuth client ID, secret, and redirect URI.
- PostgreSQL-compatible `DATABASE_URL`.
- JWT signing secret.
- Fernet encryption key.
- Frontend base URL.
- Optional email allowlist.
- Paprika credentials, either per-user or as environment fallback.

CLI imports require Gemini. CLI cloud sync additionally requires environment Paprika credentials.

### External systems that cannot be exercised offline

- Google OAuth authorization and token exchange.
- Gemini extraction/normalization.
- Paprika category reads and recipe upload.
- Production PostgreSQL persistence.

Plans touching these boundaries need explicit fakes or controlled integration credentials for deterministic verification.

## Existing concerns relevant to feature planning

These are current implementation characteristics, not proposed scope. They should be considered when a feature intersects the named area.

### 1. Duplicated core implementations

Scraping is duplicated verbatim. Formatting/prompt behavior and Paprika payload/client behavior are separately maintained in CLI and backend code. A feature can appear complete in one interface while silently remaining absent in the other.

Planning question: must the feature support CLI, web, or both? If both, decide whether consolidation is part of the feature before assigning file-level work.

### 2. No automated test suite or database migrations

No test/spec files or test-runner configuration were found. Database evolution currently relies on `create_all`, which creates missing tables but does not migrate existing columns or constraints.

Any persistent feature needs an explicit migration decision. Any high-risk behavior needs targeted contract verification rather than assuming a repository test safety net.

### 3. OAuth state is generated but not validated

`/api/auth/login` generates and returns a state value. The callback accepts a `state` parameter but does not compare it with server-side or signed client state. This removes the CSRF/login-binding protection that OAuth state is intended to provide.

The callback also places the application JWT in the redirect query string before the frontend moves it to `localStorage` and removes it from browser history.

Authentication-related features require a stronger-model security pass.

### 4. Arbitrary server-side URL fetching

The authenticated URL import accepts a string and follows redirects without blocking loopback, link-local, private-network, or non-HTTP destinations. This is a server-side request forgery boundary if users are not fully trusted or the allowlist broadens.

The Pydantic request field is an unconstrained string rather than a validated HTTP URL.

### 5. Upload limits and validation differ by interface

The CLI rejects unsupported image suffixes. The web backend accepts uploaded bytes without content validation, file-count limits, per-file size limits, or total-request limits and defaults unknown filename extensions to JPEG. The frontend stores full base64 images in `sessionStorage`, where quota failure is silently ignored.

Image-related features need explicit limits, accepted formats, persistence behavior, and retry behavior.

### 6. Category value semantics are inconsistent in comments/code

`SelectedCategory.value` is documented as an actual Paprika category name, and `EditRecipe` says it sends category names. `CategoryPicker` actually stores each category UID in `value`, and those UIDs are sent in the Paprika payload.

The expected Paprika API representation should be verified before changing category behavior; current names/comments cannot be treated as the contract.

### 7. Sync success toast can be false

`useImport.sync` catches sync errors and resolves rather than rethrowing. `App.tsx` attaches `.then(...)` and therefore displays “Recipe sent to Paprika!” even after the hook has entered the error state.

Features that modify sync or notifications should correct or preserve intentional promise semantics explicitly.

### 8. Frontend errors discard actionable backend information

The API wrapper captures the response body, but the import hook maps every import/sync failure to `Whoops! Try again.`. Backend routes also map broad exception categories to generic HTTP 500 responses. Users cannot distinguish invalid input, missing Paprika credentials, authentication failure, unsupported content, source-site failure, Gemini failure, or Paprika failure.

### 9. Quick-import capability is dormant

The backend implements quick URL/image sync, including a graceful `synced=false` response when sync fails. The frontend exposes neither the option nor the result. This is an existing latent capability, not a completed end-to-end feature.

### 10. Duplicate behavior differs

CLI sync avoids duplicate names by listing all Paprika recipe names. Web sync always creates a new UUID with the submitted name. A cross-interface feature involving re-import, updates, history, or idempotency must define duplicate semantics.

### 11. PWA API caching is user-sensitive

The service worker config uses `NetworkFirst` runtime caching for HTTPS API URLs. GET responses such as categories, credential status, and potentially login metadata are cached by URL, not bearer identity. On a shared browser profile, cached user-specific data may survive logout or account changes.

Offline/caching/authentication features need an explicit cache policy and logout cleanup.

### 12. Concurrency and recovery are minimal

- The import form remains visible and enabled during `loading`, so repeat submissions can overlap.
- Pending images are removed from `sessionStorage` before the API request completes, so an import failure loses the stored selection.
- A refresh loses the preview recipe and selected categories.
- There is no cancellation, request identity, progress detail, queue, or persisted job state.

### 13. Documentation terminology is stale

Several docstrings still refer to Claude even though both implementations use Gemini. This matters when future model/prompt changes are delegated: agents should follow imports and runtime configuration, not the stale wording.

## Extension points by feature type

### New input sources

Likely touch:

- CLI options and validation in `src/recipe_importer/cli.py`.
- Web input component in `frontend/src/components/ImportForm.tsx`.
- Frontend API wrapper and types.
- FastAPI schema/route.
- Backend service orchestration.
- Formatter message construction and prompt contract.

### New recipe fields or editable content

Likely touch:

- Both formatter prompts and response parsing.
- Backend Pydantic schemas.
- Frontend `Recipe` type.
- `EditRecipe` rendering/state and sync override semantics.
- Sync request construction.
- Both Paprika payload builders.
- CLI export behavior.
- Persistence only if drafts/history are requested.

A field change is an end-to-end contract change; changing only a prompt or only the UI is incomplete.

### Model or formatting-rule changes

Likely touch both formatter implementations and prompt copies. Changes should be evaluated with representative structured, raw-page, multilingual, and image inputs. Deterministic unit-conversion logic may be safer outside the prompt if exactness becomes an acceptance criterion.

### Import history, drafts, or user preferences

Likely require:

- New SQLAlchemy entities/columns.
- A real migration mechanism or an explicit deployment migration.
- User-scoped API endpoints.
- Frontend navigation beyond the current single state machine.
- Retention/deletion rules.
- Authentication and authorization checks on every record operation.

### Paprika behavior

Likely touch category retrieval, payload semantics, duplicate handling, upload behavior, credential errors, and possibly both Paprika clients. Paprika is an external, unofficially represented API boundary in this repository; exact request/response behavior should be captured before implementation.

### UI-only workflow changes

Likely touch `App.tsx`, `useImport.ts`, and one or more components. Because state routing is centralized and recipes are not persisted, additions such as back navigation, resumable drafts, or multiple previews may justify revisiting the state model rather than adding more booleans.

### Authentication, sharing, or multi-user changes

Must account for OAuth state, JWT transport/storage, email allowlisting, service-worker caching, per-user Paprika secrets, database authorization, and logout cleanup. These are not safe mechanical-only assignments.

## Model assignment guidance for the later playbook

The final `M1-OMP-PLAYBOOK.md` should assign work based on coupling and risk, not file size.

### Good cheaper-model tasks

Use cheaper models where the feature contract is already fixed and the task is locally verifiable:

- Mechanical Pydantic/TypeScript field parity.
- Small presentational component changes following an existing pattern.
- Adding a fixed API-client function after the route contract is settled.
- Updating environment examples and user-facing command documentation.
- Straightforward fixture construction or deterministic boundary tests.
- Renaming stale Claude terminology after runtime ownership is clear.
- Running specified builds, lint checks, and smoke commands and reporting exact output.

Each such task should name exact files, input/output contracts, non-goals, and a narrow verification command.

### Keep on stronger models

Use stronger models for:

- Feature decomposition and cross-interface contract ownership.
- Prompt/model behavior and evaluation design.
- Shared-module consolidation across CLI/backend.
- Authentication, OAuth, JWT, credential storage, SSRF, caching, or authorization work.
- Database schema and migration design.
- Async state, retries, cancellation, idempotency, duplicate handling, and error taxonomy.
- Changes spanning input, model output, API schema, editor state, and Paprika payload.
- Final integration review and end-to-end acceptance verification.

### Playbook task boundary rule

A delegated task is cheap-model-safe only when:

1. Its upstream contract is frozen.
2. It owns non-overlapping files or an explicitly isolated symbol range.
3. It has no hidden external-service decision.
4. Failure is detectable by a narrow deterministic check.
5. It cannot silently produce CLI/web schema divergence.

## Verified baseline

Assessment date: 2026-09-07.

The following were exercised without changing source files:

- `npm run build` in `frontend/`: passed; TypeScript and Vite production build completed, PWA service worker generated.
- `npm run lint` in `frontend/`: failed with three existing `react-hooks/set-state-in-effect` diagnostics:
  - `frontend/src/App.tsx:51`
  - `frontend/src/components/CategoryPicker.tsx:44`
  - `frontend/src/components/CategoryPicker.tsx:50`
- `.venv/bin/recipe-importer --help`: passed and exposed the `import` command.
- `.venv/bin/recipe-importer import` without inputs: rejected the invocation with the expected source-required error.
- Importing `backend.main`: passed and produced the `Recipe Importer` FastAPI app.
- Generated OpenAPI paths matched the seven routes documented above.
- A local exporter smoke run created `smoke-recipe.paprikarecipe`; gzip decompression returned the expected recipe name and ingredients.
- The production frontend build was served and visually inspected at a 390 × 844 mobile viewport.
- Visually inspected screens/states: Google login, authenticated URL import, image-source selection, settings, and mocked recipe preview.

Not verified against live services:

- Google login callback.
- PostgreSQL startup/schema behavior.
- Live URL scraping.
- Gemini output quality.
- Paprika credential validation, categories, or upload.
- Full Docker/Caddy deployment.

## Finalized feature scope for `M1-OMP-PLAYBOOK.md`

The first implementation milestone is limited to extending recipe input sources in the PWA and making the directly affected paths safe and maintainable.

### Product boundary

- The React PWA and FastAPI backend are the product.
- Existing recipe-page URL and image imports remain supported.
- The CLI receives no new source features and has no parity requirement.
- CLI deletion is not required for this milestone because it adds no user-visible value; future PWA work must treat `backend/` as authoritative.

### New pasted-text source

- Add a Text source beside URL and Images.
- Users paste recipe content and send it directly to the backend Gemini normalization path.
- Empty and over-limit submissions are rejected before the model call.
- Pasted text is the manual fallback for social content that cannot be retrieved.

### YouTube source

- YouTube links continue through the URL input.
- Extract only the public video description and available human or automatic captions.
- Do not download video/audio, transcribe audio, extract frames, or run OCR.
- Prefer human captions over automatic captions and English over other available languages, while allowing non-English captions because Gemini already translates recipe content to English.
- If neither description nor usable captions is available, show a specific message directing the user to obtain the recipe separately and paste it into Text.

### Instagram source

- Instagram post/Reel links continue through the URL input.
- Extract only a publicly accessible post caption.
- Do not download media, inspect frames, transcribe audio, run OCR, use account cookies, or add a paid extraction provider.
- If no public caption is available, show a specific message directing the user to paste the caption or separately extracted recipe into Text.
- This is explicitly best-effort because Instagram may block anonymous metadata retrieval.

### Multiple recipes from one source

- Every formatter result becomes a bounded recipe list, regardless of source type.
- A single detected recipe continues directly to preview.
- Multiple detected recipes produce a selection screen showing recipe titles.
- Users may select one or more recipes and review/sync the selection sequentially.
- Each recipe is uploaded to Paprika with its own existing sync request; there is no batch Paprika API contract.
- Successful recipes are not retried if a later recipe fails. The failed recipe remains retryable and unsynced recipes remain queued.
- A source may return at most 10 recipes. An over-limit result is reported explicitly rather than silently truncated.
- This contract also applies when pasted text, images, YouTube content, or Instagram captions contain multiple recipes; URL-specific singular and plural response shapes are prohibited.

### AI formatting

- Preserve the current `gemini-2.5-flash` model and recipe-formatting semantics in this milestone.
- Make the PWA backend prompt path the clear single authority for future formatting-rule changes.
- Do not invent formatting changes before the user supplies exact rules and examples.

### Directly related remediation

The milestone may fix source URL safety, source/upload limits, actionable import errors, repeated submissions, false sync-success notifications, OAuth state handling, and user-sensitive API caching. It must not expand into drafts, history, full recipe editing, media processing, Paprika duplicate handling, or a general redesign.