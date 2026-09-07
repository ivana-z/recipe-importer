# M1 OMP Playbook — Additional PWA Recipe Sources

## Status

Ready to execute after the user starts Session 1 and answers its required `Should I proceed?` confirmation.

This playbook implements one milestone: add pasted-text, YouTube-description/captions, Instagram-caption, and multiple-recipe inputs to the existing PWA. It also repairs the narrow security and correctness issues that those sources depend on.

Read `APPLICATION-FINDINGS.md` before executing any session.

## Outcome

After M1, an authenticated PWA user can import a recipe from:

- A conventional recipe-page URL.
- One or more images.
- Pasted recipe text.
- A YouTube URL whose public description or captions contain recipe content.
- An Instagram post/Reel URL whose public caption contains recipe content.

Every successful source returns one or more normalized recipes. A single recipe goes directly to review; multiple recipes go through explicit selection and a sequential review/sync queue. Unsupported, inaccessible, empty, unsafe, over-limit, or over-count sources produce actionable errors.

## Fixed scope

### Included

- PWA and FastAPI backend only.
- Existing URL and image behavior retained.
- A new Text source in the PWA.
- YouTube public description plus available captions.
- Instagram public post caption only.
- Source-independent detection, selection, and sequential review of up to 10 recipes from one input.
- URL request safety.
- Bounded source content.
- Source-specific error messages.
- False Paprika-success notification repair.
- OAuth state validation and safer OAuth token redirect transport.
- Removal of user-sensitive API runtime caching.
- Targeted regression coverage for security and extractor boundaries.
- Backend prompt ownership made explicit and easy to change later.

### Excluded

- CLI feature parity or CLI deletion.
- Audio or video download.
- Audio transcription.
- Frame extraction, OCR, or visual analysis of social media.
- Instagram authentication cookies or private posts.
- Paid social extraction providers.
- Browser automation against social sites.
- Recipe drafts or import history.
- Full recipe-field editing.
- Paprika duplicate/update behavior.
- New AI formatting rules that have not yet been specified.
- A general frontend redesign.

## Architecture decisions

These decisions are inputs to implementation sessions, not questions for delegated models.

### Product ownership

- `backend/` and `frontend/` are authoritative for M1.
- `src/recipe_importer/` remains untouched and receives no new sources.
- No effort is spent preserving CLI/PWA prompt parity.
- The runtime Gemini model remains `gemini-2.5-flash`.

### API and formatter shape

Keep the existing source endpoints and add one endpoint:

```text
POST /api/import/url     existing; dispatch by validated URL type
POST /api/import/images  existing
POST /api/import/text    new; JSON body {"text": "..."}
POST /api/sync           existing; uploads one reviewed recipe at a time
```

All import endpoints make a clean cutover to:

```json
{
  "recipes": [
    {
      "name": "Recipe name",
      "ingredients": "...",
      "directions": "...",
      "prep_time": "",
      "cook_time": "",
      "servings": "",
      "notes": "",
      "source_url": "",
      "source": ""
    }
  ]
}
```

The singular `recipe` response and dormant import-time `quick`/`synced` behavior are removed. The current frontend never requests quick sync, and its semantics become ambiguous for a recipe list. Paprika sync remains the separate existing endpoint and still accepts exactly one reviewed recipe.

The normalized recipe fields do not change.

### Multiple-recipe contract

Gemini returns one batch envelope for every source:

```json
{
  "recipes": [],
  "has_more": false
}
```

Rules:

- `recipes` must contain 1–10 complete recipe objects.
- `has_more` must be `true` when the source appears to contain more than 10 distinct recipes.
- If `has_more` is true or more than 10 recipes are returned, reject the whole import with `too_many_recipes`; never silently truncate.
- If no recipe is found, return `no_recipe_found`.
- If any returned recipe is malformed, reject the batch rather than dropping only that recipe.
- Apply scraped/extracted `source` and `source_url` metadata to every recipe in the batch.
- Do not merge distinct recipes, sauces, variants, or menus into one recipe. A component that is explicitly part of one recipe remains part of that recipe.
- This envelope applies identically to URL, image, pasted-text, YouTube, and Instagram imports.

Frontend behavior:

- One recipe bypasses selection and opens the existing review screen.
- Two to ten recipes open a title-based selection screen.
- Nothing is preselected. Continue is disabled until at least one recipe is selected.
- The user may select one or more recipes, including Select all.
- Selected recipes enter a stable sequential queue and are reviewed/synced one at a time.
- A successful sync advances exactly once and records that recipe as complete.
- A failed sync leaves the current edited recipe retryable and does not resend completed recipes or discard remaining recipes.
- After the queue completes, show the number successfully sent and allow a new import.

### URL dispatch

`POST /api/import/url` classifies a validated HTTP(S) URL:

```text
youtube.com / youtu.be / youtube-nocookie.com
  -> YouTube metadata extractor

instagram.com
  -> Instagram metadata extractor

all other public hosts
  -> existing recipe-page scraper
```

Supported YouTube paths include individual watch, Shorts, and `youtu.be` URLs. Supported Instagram paths include individual `/p/`, `/reel/`, and `/tv/` items. Profiles, tags, playlists, feeds, stories, and unrelated platform URLs are rejected rather than expanded into bulk imports.

Never fall back from a failed YouTube/Instagram extraction to the generic HTML scraper. Login/consent/error HTML is not recipe content.

### Social extraction dependency

Use the embedded Python API of `yt-dlp`, not a shell subprocess:

```python
with yt_dlp.YoutubeDL(options) as ydl:
    info = ydl.extract_info(url, download=False)
```

Install the current compatible `yt-dlp` with its `default` and `deno` extras. The extras supply the EJS component and recommended JavaScript runtime needed for current YouTube metadata support. Do not install `ffmpeg`; M1 never downloads or processes media.

Required options/invariants include:

- `skip_download=True`
- `noplaylist=True`
- Quiet/no-warning operation through application logging
- A finite socket timeout
- No output template, postprocessor, media format, cookie, or browser-cookie option
- `download=False` on extraction

External-site support is best-effort. yt-dlp itself warns that listed sites can break as websites change; failure must become an actionable application response, not a crash.

### YouTube content selection

Build formatter input from available fields in this order:

1. Video title, for context.
2. Complete public description, if nonblank.
3. One caption track, if available.

Caption selection precedence:

1. Human-provided captions before automatic captions.
2. Exact English language tag, then English-prefixed tag.
3. Any remaining non-live-chat language, because Gemini translates to English.
4. Within the selected track, prefer JSON3, then WebVTT, then another text caption representation that can be parsed without media tools.

Normalize caption whitespace and remove consecutive duplicate caption chunks. Keep description and captions under separate labels so Gemini can distinguish them. Do not combine multiple translated caption tracks.

If both description and usable captions are absent, return `source_unavailable`. A title alone is not usable recipe input.

### Instagram content selection

Use only the extracted public `description`/caption field. The title or uploader alone is not recipe content. Do not inspect subtitle, thumbnail, format, audio, or video fields.

If the public caption is absent or the post requires login, return `source_unavailable` with an Instagram-specific message that recommends the Text source.

### Content limits

Use named constants, enforced before a Gemini call:

```text
MAX_SOURCE_TEXT_CHARS = 100_000
MAX_CAPTION_RESPONSE_BYTES = 2_000_000
SOCIAL_EXTRACTION_TIMEOUT_SECONDS = 30
MAX_REDIRECTS = 5
MAX_RECIPES_PER_SOURCE = 10
```

Reject over-limit content with `source_too_large`; do not silently truncate a recipe. Reject pasted content that is blank after trimming.

### Source errors

Use a small domain exception with stable code and safe user message. Map it to a structured FastAPI error detail:

```json
{
  "detail": {
    "code": "source_unavailable",
    "message": "No public YouTube description or captions were available. Extract the recipe separately and paste it into Text."
  }
}
```

Required codes:

| Code | HTTP status | Meaning |
|---|---:|---|
| `invalid_source_url` | 400 | Unsupported scheme, platform path, or malformed source URL |
| `unsafe_source_url` | 400 | URL resolves to a non-public destination or an unsafe redirect |
| `source_too_large` | 413 | Pasted or extracted source exceeds a fixed limit |
| `source_unavailable` | 422 | Public description/caption/transcript is absent or inaccessible |
| `no_recipe_found` | 422 | Gemini found no complete recipe in otherwise usable source content |
| `too_many_recipes` | 422 | Source appears to contain more than the supported 10 recipes |
| `source_fetch_failed` | 502 | A supported upstream source failed unexpectedly |
| `import_failed` | 500 | Formatting or an unclassified internal failure |

Do not expose upstream response bodies, credentials, yt-dlp diagnostics, local network details, or stack traces to the browser. Log the underlying exception server-side.

### Generic URL safety

For non-social recipe pages:

- Allow only `http` and `https`.
- Require a hostname.
- Resolve and reject loopback, private, link-local, multicast, reserved, unspecified, and otherwise non-global addresses for IPv4 and IPv6.
- Reject `localhost` and credentials embedded in URLs.
- Disable automatic redirects.
- Follow at most five redirects manually.
- Resolve and revalidate every redirect target before requesting it.
- Reject non-HTTP redirect targets.
- Preserve the existing timeout and browser-like user agent.

Tests must cover raw private IPs, DNS resolving to private IPs, IPv6 loopback, and a public URL redirecting to a private destination.

### Prompt ownership

- Move the PWA prompt and message builders from the merged `backend/formatter.py` into `backend/prompts.py`.
- Preserve all existing measurement, translation, chapter, and recipe-field semantics while intentionally changing the formatter envelope from one recipe object to `{"recipes": [...], "has_more": false}`.
- Add pasted/extracted-text message construction without changing source-content semantics.
- Social and pasted text use the same text-message builder.
- Leave `src/recipe_importer/prompts.py` untouched and explicitly out of scope.
- Do not change the recipe object fields or the `gemini-2.5-flash` runtime model in M1.

### Verification strategy

- External network and Gemini calls are mocked in permanent tests.
- Tests defend observable source selection, safety, limits, errors, and output—not source-code wording or private helper wiring.
- Browser smoke verification exercises the built PWA with intercepted API responses.
- Optional live extraction uses user-supplied public URLs and never calls Gemini or Paprika.
- Session 8 is the only milestone-completion gate.

## OMP model assignments

The exact selectors below were available in this workstation's OMP registry on 2026-09-07.

| Session | Suggested model | Relative use | Why |
|---|---|---|---|
| 1 | `openai-codex/gpt-5.6-sol` | Strong | OAuth, token transport, service-worker privacy, React state semantics |
| 2 | `openai-codex/gpt-5.6-terra` | Medium/strong | SSRF boundary, redirects, DNS/IP validation, error contract |
| 3 | `openai-codex/gpt-5.6-terra` | Medium/strong | Core formatter/API list cutover and strict batch invariants |
| 4 | `openai-codex/gpt-5.4-mini` | Economical | Frozen frontend selection and sequential queue behavior |
| 5 | `openai-codex/gpt-5.6-luna` | Lowest cost | Pasted-text wiring after plural contracts are established |
| 6 | `openai-codex/gpt-5.4-mini` | Economical | Well-specified yt-dlp metadata adapter and deterministic parsing tests |
| 7 | `openai-codex/gpt-5.6-luna` | Lowest cost | Mechanical frontend error propagation and social-source copy |
| 8 | `openai-codex/gpt-5.6-sol` | Strong | Cross-session integration, security review, browser/Docker verification |

If an exact selector is unavailable, use `@slow` for Sessions 1 and 8, `@default` for Sessions 2 and 3, and `@smol` for Sessions 4–7. Check `/models` rather than silently choosing a model with unknown tool support.

## Execution order

```text
Session 1: authentication/cache/sync correctness
    |
Session 2: URL safety and error contract
    |
Session 3: multi-recipe backend and formatter contract
    |
Session 4: multi-recipe selection and sync queue
    |
Session 5: pasted text end to end
    |
Session 6: YouTube/Instagram backend extraction
    |
Session 7: social-source frontend errors and copy
    |
Session 8: integration, cleanup, and completion gate
```

Run sessions sequentially. They intentionally overlap central files such as `backend/api.py`, `backend/services.py`, `frontend/src/App.tsx`, and `frontend/src/hooks/useImport.ts`. Parallel sessions would create merge risk and make cheaper models reason against stale contracts.

Before every session:

1. Start OMP from the repository root.
2. Select the specified model.
3. Paste the session prompt verbatim.
4. Answer `yes` when the session asks `Should I proceed?`.
5. Do not start the next session until the current session's acceptance checks pass or its blocker is documented.

---

## Session 1 — Authentication, PWA cache, and sync correctness

**Model:** `openai-codex/gpt-5.6-sol`

**Start:**

```bash
omp --model openai-codex/gpt-5.6-sol
```

**Prompt:**

```text
Work in the recipe-importer repository. This is Session 1 of M1.

First read CLAUDE.md, APPLICATION-FINDINGS.md, and M1-OMP-PLAYBOOK.md. Then inspect only the authentication, top-level frontend state, service-worker caching, sync notification, and current lint-related files needed for this session. Summarize your understanding and ask exactly: "Should I proceed?" Do not edit until I answer yes. After approval, complete the entire session without asking again unless repository evidence exposes a materially different product choice.

Goal:
Repair the existing OAuth-state, OAuth-token-redirect, user-sensitive API-cache, false sync-success, and React lint problems before adding more recipe sources. Do not implement any new source in this session.

Required changes:
1. Bind each Google OAuth login start to its callback with a short-lived random state stored in an HttpOnly, SameSite=Lax cookie. Compare with secrets.compare_digest before exchanging the authorization code. Reject a missing/mismatched/expired state. Clear the cookie on a successful callback. Use Secure cookies outside DEV_MODE and permit local HTTP development.
2. Redirect the issued application JWT in the URL fragment, not the query string. Update the frontend to consume the fragment token once, save the existing localStorage key, and immediately remove the fragment from browser history. Do not introduce a second token storage system.
3. Preserve the current Google login and email allowlist behavior.
4. Remove service-worker runtime caching for all /api responses. Ensure the legacy api-cache is deleted when the app initializes and on sign-out so user-specific categories/credential status cannot survive an account change.
5. Fix the Paprika sync promise/toast contract: a success toast must appear only after a successful sync. A failed sync must enter the error state without a success toast.
6. Make npm run lint pass by correcting the existing set-state-in-effect problems in App.tsx and CategoryPicker.tsx. Do not disable rules or add eslint suppressions.
7. Add only high-value regression tests for OAuth state acceptance/rejection and token redirect placement. Establish a minimal pytest development dependency/configuration if required; do not create broad plumbing tests.
8. Update affected environment documentation only if a cookie/security setting is newly required. Do not add database schema changes.

Likely files:
- backend/oauth.py
- backend/auth_routes.py
- frontend/src/App.tsx
- frontend/src/api.ts
- frontend/src/hooks/useImport.ts
- frontend/src/components/CategoryPicker.tsx
- frontend/src/components/Settings.tsx
- frontend/vite.config.ts
- pyproject.toml
- targeted tests under tests/

Non-goals:
- No JWT cookie migration.
- No OAuth provider addition.
- No source import changes.
- No CLI edits.
- No UI redesign.

Acceptance:
- A callback without the matching state cookie is rejected before Google exchange.
- A matching state succeeds through the mocked exchange and redirects with #token=, never ?token=.
- The frontend consumes and removes #token without an effect-driven state update.
- No service-worker route caches authenticated API GET responses.
- Sync failure cannot display the success toast.
- Existing login, settings, category picker, and import screen behavior remains usable.

Verification:
- Install the project development extras into .venv only if needed.
- Run the targeted authentication tests.
- Run npm run lint in frontend/.
- Run npm run build in frontend/.
- Serve the production frontend and use the browser tool at a mobile viewport to verify login, fragment consumption, settings, and the category drawer. Use mocked API responses; do not call Google or Paprika.

Finish by reporting exact changed files, commands and results, browser states exercised, and any unverified external behavior. Do not claim M1 complete; only Session 1 is complete.
```

---

## Session 2 — Safe URL fetching and source-error contract

**Model:** `openai-codex/gpt-5.6-terra`

**Start:**

```bash
omp --model openai-codex/gpt-5.6-terra
```

**Prompt:**

```text
Work in the recipe-importer repository. This is Session 2 of M1; Session 1 is already applied.

First read CLAUDE.md, APPLICATION-FINDINGS.md, and M1-OMP-PLAYBOOK.md. Inspect the current backend URL request, scraper, schemas, routes, services, and tests. Summarize your understanding and ask exactly: "Should I proceed?" Do not edit until I answer yes. After approval, complete the entire session.

Goal:
Make conventional recipe URL imports reject unsafe destinations and establish the structured source-error contract that later Text, YouTube, and Instagram sources will reuse.

Required changes:
1. Introduce one small backend domain exception carrying a stable error code, safe browser message, and intended HTTP status. Do not build an exception framework.
2. Validate ImportUrlRequest as an HTTP(S) URL with a hostname. Reject credentials in URLs.
   Keep the body field as a string if necessary so malformed/unsupported URLs can use the required `invalid_source_url` HTTP 400 contract; do not accidentally delegate this contract to FastAPI's default HTTP 422 validation response.
3. Move generic page retrieval behind a safe fetch helper. Resolve hostnames and reject every non-global IPv4/IPv6 result, including loopback, private, link-local, multicast, reserved, and unspecified addresses.
4. Disable automatic redirects. Follow no more than MAX_REDIRECTS=5 manually and revalidate every target before the next request.
5. Preserve the current 30-second timeout, user agent, recipe-scrapers path, trafilatura fallback, and raw-HTML last resort for safe conventional recipe pages.
6. Map expected source errors from /api/import/url to the structured detail contract documented in the playbook. Keep unexpected internal failures generic and logged.
7. Ensure the same validation helper can later identify approved social hosts without weakening generic URL safety, but do not implement social extraction yet.
8. Add deterministic tests with mocked DNS and HTTP. Cover a safe public URL, raw private IP, DNS-to-private address, IPv6 loopback, embedded credentials, a public redirect to private space, redirect loops/overflow, and upstream fetch failure.

Likely files:
- backend/schemas.py
- backend/api.py
- backend/services.py
- backend/scraper.py
- new focused modules such as backend/source_errors.py and backend/url_safety.py
- targeted tests under tests/

Constraints:
- Never make live requests in tests.
- Never special-case only localhost; validate resolved addresses generally.
- Never expose resolver/upstream exception text to the client.
- No YouTube, Instagram, Text, frontend, CLI, OAuth, or Paprika changes.
- Do not add retries.

Acceptance:
- Unsafe direct and redirected URLs are blocked before their HTTP request.
- Safe public URLs retain current structured/trafilatura/raw fallback behavior.
- Expected errors have stable code/message/status.
- Unexpected errors remain a logged generic import failure.

Verification:
- Run only the targeted URL safety, scraper, and route error tests.
- Import backend.main and list the OpenAPI paths to confirm existing routes remain.
- Run the full Python test set only after targeted tests pass.

Finish by reporting exact changed files and exact verification output. Do not claim M1 complete.
```

---

## Session 3 — Multi-recipe backend and formatter contract

**Model:** `openai-codex/gpt-5.6-terra`

**Start:**

```bash
omp --model openai-codex/gpt-5.6-terra
```

**Prompt:**

```text
Work in the recipe-importer repository. This is Session 3 of M1; Sessions 1 and 2 are already applied.

First read CLAUDE.md, APPLICATION-FINDINGS.md, and M1-OMP-PLAYBOOK.md. Inspect the current backend formatter, prompt, import schemas, routes, services, URL/image flows, frontend API call sites, and tests. This session owns the backend contract only, but you must identify every frontend caller that Session 4 will migrate. Summarize your understanding and ask exactly: "Should I proceed?" Do not edit until I answer yes. After approval, complete the entire session.

Goal:
Make every backend import return a strict batch of one to ten normalized recipes. Preserve recipe object fields and formatting rules while removing the obsolete singular and quick-import contracts.

Fixed response contract:
{
  "recipes": [RecipeResponse, ...]
}

Fixed Gemini envelope:
{
  "recipes": [recipe objects],
  "has_more": false
}

Required changes:
1. Change the PWA backend formatter to request and parse the Gemini batch envelope for every existing URL and image source.
2. Move the PWA system prompt, reminder, and message builders from backend/formatter.py into backend/prompts.py.
3. Preserve existing measurement, translation, chapter, ingredient, and recipe-field rules. Change only singular/plural extraction instructions and response envelope semantics.
4. Instruct Gemini to return every distinct complete recipe found, up to MAX_RECIPES_PER_SOURCE=10. A component explicitly belonging to one recipe remains inside that recipe; genuinely distinct recipes/variants remain separate.
5. Require 1–10 complete recipe objects. Reject an empty list as no_recipe_found. Reject has_more=true or more than 10 returned recipes as too_many_recipes. Reject the complete response if any recipe is malformed; never drop or truncate entries silently.
6. Change ImportResult from recipe plus synced to recipes only.
7. Apply source/source_url metadata to every recipe in each service result.
8. Remove the dormant quick field from URL/image requests and remove import-time quick-sync branches. Keep POST /api/sync unchanged as the one-recipe upload boundary.
9. Migrate every backend caller to the plural contract. Do not modify frontend code in this session; explicitly report the known frontend compile break for Session 4.
10. Add high-value formatter/service/API tests for one recipe, several recipes, no recipe, malformed member, exactly 10, 11, and has_more=true. Tests must observe returned contracts and errors, not private field-copy implementation.

Likely files:
- backend/prompts.py (new)
- backend/formatter.py
- backend/schemas.py
- backend/api.py
- backend/services.py
- backend/source_errors.py
- tests/test_formatter.py
- tests/test_import_contract.py

Non-goals:
- No frontend migration.
- No Text, YouTube, or Instagram source.
- No recipe object field changes.
- No Gemini model change.
- No Paprika batch endpoint or duplicate handling.
- No CLI synchronization.

Acceptance:
- Existing URL and image services return one or more recipes under recipes.
- Singular recipe, quick, and synced import contracts are gone from the backend/OpenAPI schema.
- Exactly 10 recipes succeeds.
- Empty, malformed, over-10, and has_more responses fail with the fixed safe error codes.
- Source metadata is present on every returned recipe.
- POST /api/sync remains singular and unchanged.

Verification:
- Run targeted formatter and import-contract tests.
- Run the complete Python test suite.
- Import backend.main and inspect /api/import/url and /api/import/images OpenAPI request/response schemas.
- Do not run frontend build as a pass criterion: the frontend is intentionally migrated in Session 4. Report the exact known TypeScript contract mismatch rather than hiding it with a compatibility alias.

Finish by reporting exact files, tests/results, OpenAPI observations, and the frontend call sites Session 4 must migrate. Do not claim M1 complete.
```

---

## Session 4 — Multi-recipe selection and sequential sync queue

**Model:** `openai-codex/gpt-5.4-mini`

**Start:**

```bash
omp --model openai-codex/gpt-5.4-mini
```

**Prompt:**

```text
Work in the recipe-importer repository. This is Session 4 of M1; Sessions 1–3 are already applied.

First read CLAUDE.md, APPLICATION-FINDINGS.md, and M1-OMP-PLAYBOOK.md. Read skill://frontend-design because this session adds a user-facing selection and queue flow. Inspect the plural OpenAPI/backend contract, frontend types, API wrapper, useImport, App, EditRecipe, CategoryPicker, StatusBar, and existing visual conventions. Summarize your understanding and ask exactly: "Should I proceed?" Do not edit until I answer yes. After approval, complete the entire session.

Goal:
Migrate the PWA to the plural import contract and implement explicit multi-recipe selection, review, and one-at-a-time Paprika sync without redesigning the application.

Required data/state behavior:
1. Replace ImportResult.recipe/synced with ImportResult.recipes everywhere in the frontend.
2. Add a selection state between loading and preview. One imported recipe bypasses selection; two to ten recipes enter selection.
3. Selection shows each recipe title with accessible checkbox semantics. Nothing is selected initially. Continue is disabled until at least one item is selected. Include Select all and Clear actions without adding a component library.
4. Freeze the selected recipes into a stable queue in source order.
5. Review and sync one queued recipe at a time through the existing singular POST /api/sync.
6. After a successful sync, record completion and advance exactly once to the next selected recipe. Give each next EditRecipe instance fresh editable state and fresh category selection.
7. On sync failure, keep the current edited values visible and retryable. Do not advance, resend already-completed recipes, or discard remaining recipes.
8. After the final selected recipe succeeds, show a completion summary with the number sent and New Import.
9. Import failure remains an import-level error/reset flow; sync failure is presented with the current recipe so Retry is possible.
10. Reset clears the imported batch, selection, queue, completed count, current edits, and errors.

Implementation constraints:
- Keep useImport as the single workflow owner; do not add Redux, a router, server persistence, or a generic state-machine dependency.
- A focused RecipeSelection component is allowed and expected.
- Do not create a batch Paprika API.
- Do not automatically sync any selected recipe.
- Do not auto-select every recipe.
- Do not persist a recipe queue across refresh.
- Do not change backend contracts unless they demonstrably violate the playbook; report such a blocker before editing backend files.

Likely files:
- frontend/src/types.ts
- frontend/src/api.ts
- frontend/src/hooks/useImport.ts
- frontend/src/App.tsx
- frontend/src/components/RecipeSelection.tsx (new)
- frontend/src/components/EditRecipe.tsx
- frontend/src/components/StatusBar.tsx

Acceptance:
- One recipe follows the old direct-review path.
- Three recipes show all three titles and no initial selection.
- Selecting recipes 1 and 3 reviews/syncs 1 then 3; recipe 2 is never sent.
- A failure on recipe 3 leaves it retryable and does not resend recipe 1.
- Retrying recipe 3 successfully finishes with “2 recipes sent” or equivalent accurate copy.
- Editing recipe 1 cannot leak name/source/categories into recipe 3.
- Reset from completion returns to a clean import form.

Verification:
- Run npm run lint and npm run build.
- Serve the production frontend and use browser request interception at 390x844.
- Exercise one-result bypass, multi-result selection, Select all/Clear, sparse selection, sequential review, partial sync failure/retry, accurate completion count, and reset.
- Confirm API request logs show exactly one POST /api/sync per successful queue item plus explicit failed retries; no unselected or completed recipe is resent.

Finish by reporting exact files, commands/results, browser scenarios, and observed sync request order. Do not claim M1 complete.
```

---

## Session 5 — Pasted text end to end

**Model:** `openai-codex/gpt-5.6-luna`

**Start:**

```bash
omp --model openai-codex/gpt-5.6-luna
```

**Prompt:**

```text
Work in the recipe-importer repository. This is Session 5 of M1; Sessions 1–4 are already applied.

First read CLAUDE.md, APPLICATION-FINDINGS.md, and M1-OMP-PLAYBOOK.md. Read skill://frontend-design because this session changes the source form. Inspect the current plural formatter/API contract, prompt builders, services, frontend API/hook, App, ImportForm, and tests. Summarize your understanding and ask exactly: "Should I proceed?" Do not edit until I answer yes. After approval, complete the entire session.

Goal:
Add pasted recipe text as a complete PWA source using the established plural import and selection/queue behavior.

Fixed contract:
- POST /api/import/text
- JSON request: {"text": string}
- Response: {"recipes": [RecipeResponse, ...]}
- Blank-after-trim input is invalid.
- MAX_SOURCE_TEXT_CHARS=100000.
- Over-limit input returns source_too_large with HTTP 413.

Required backend changes:
1. Add the request schema, authenticated route, service function, and formatter text-message builder.
2. Reuse the Session 3 formatter batch parser and existing source-error mapping; do not create a text-specific recipe contract.
3. Enforce blank and length limits before any Gemini client/model call.
4. Keep source and source_url empty for pasted text so users can supply source during review.
5. Preserve all formatting rules and the gemini-2.5-flash model.

Required frontend changes:
1. Add Text beside URL and Images in the existing source selector.
2. Add an accessible multiline input, clear helper copy, and accurate character count/limit indication.
3. Add api.ts/useImport wiring through the existing import path.
4. Disable source controls while loading so repeated submissions cannot overlap.
5. Do not persist pasted recipe text to localStorage or sessionStorage.
6. A one-recipe response goes directly to review; a multi-recipe response uses the Session 4 selection/queue unchanged.
7. Preserve the mobile-first dark/amber visual language and ensure three source choices fit at 390px.

Likely files:
- backend/prompts.py
- backend/formatter.py
- backend/schemas.py
- backend/api.py
- backend/services.py
- frontend/src/types.ts
- frontend/src/api.ts
- frontend/src/hooks/useImport.ts
- frontend/src/App.tsx
- frontend/src/components/ImportForm.tsx
- targeted tests under tests/

Non-goals:
- No new recipe fields or formatting rules.
- No YouTube/Instagram implementation.
- No CLI synchronization.
- No persistence for pasted text or queues.
- No general redesign.

Acceptance:
- Blank text cannot be submitted in the UI or API.
- Exactly 100000 characters is accepted; 100001 is rejected before Gemini.
- Pasted text returning one recipe reaches review.
- Pasted text returning multiple recipes reaches selection and the existing queue.
- URL and image sources still work.
- Loading blocks duplicate requests.

Verification:
- Run targeted text API/service boundary tests and the complete Python test suite.
- Run npm run lint and npm run build.
- Serve the production frontend and use the browser tool at 390x844 to exercise URL, Images, and Text, including one- and multi-recipe pasted-text responses.

Finish by reporting exact files, commands/results, and browser states. Do not claim M1 complete.
```

---

## Session 6 — YouTube and Instagram metadata extraction

**Model:** `openai-codex/gpt-5.4-mini`

**Start:**

```bash
omp --model openai-codex/gpt-5.4-mini
```

**Prompt:**

```text
Work in the recipe-importer repository. This is Session 6 of M1; Sessions 1–5 are already applied.

First read CLAUDE.md, APPLICATION-FINDINGS.md, and M1-OMP-PLAYBOOK.md. Inspect the current dependency configuration, safe URL validation, source errors, URL service, plural formatter text path, and tests. Consult the official yt-dlp embedding and supported-sites documentation if repository state or installed API behavior is uncertain. Summarize your understanding and ask exactly: "Should I proceed?" Do not edit until I answer yes. After approval, complete the entire session.

Goal:
Make the existing URL endpoint import public YouTube descriptions/captions and public Instagram captions without downloading or processing media. Social content may yield one or several recipes through the established plural formatter.

Required dependency:
- Add yt-dlp with the default and deno extras so the Python runtime has yt-dlp-ejs and its recommended JavaScript runtime.
- Do not add ffmpeg or invoke a yt-dlp subprocess.
- Verify the final Docker runtime, not only the local virtual environment, can import yt_dlp and discover the Deno runtime.

Required URL classification:
1. Recognize supported individual YouTube URLs on youtube.com, youtu.be, and youtube-nocookie.com.
2. Recognize supported individual Instagram /p/, /reel/, and /tv/ URLs.
3. Reject profiles, feeds, tags, stories, and playlists as invalid_source_url.
4. Route all other safe public hosts through the existing recipe-page scraper.
5. Never fall back from a failed social extractor to generic page scraping.

Required YouTube behavior:
1. Call the embedded YoutubeDL API with skip_download=True, noplaylist=True, finite timeout, quiet/no-warning behavior, and extract_info(..., download=False).
2. Use title only as context; it cannot make an otherwise empty source usable.
3. Include full nonblank description when available.
4. Select at most one caption track: human before automatic; exact/prefixed English before any other non-live-chat language; JSON3 before WebVTT when available.
5. Fetch only the selected caption text representation with a 2,000,000-byte response ceiling and finite timeout.
6. Parse JSON3 and WebVTT deterministically, normalize whitespace, decode text entities as needed, and remove consecutive duplicate chunks.
7. Send labeled title/description/captions through the Session 5 formatter text path.
8. If both description and usable captions are absent, return source_unavailable with the exact fallback intent documented in the playbook.

Required Instagram behavior:
1. Use only the public description/caption returned by metadata extraction.
2. Do not access or process formats, media URLs, subtitles, thumbnails, or comments.
3. Do not add cookies, user credentials, browser automation, or paid providers.
4. If the caption is absent or anonymous access fails, return source_unavailable with a message directing the user to Text.

Shared behavior:
- Use MAX_SOURCE_TEXT_CHARS=100000 and reject rather than truncate.
- Set source on every returned recipe to uploader/channel/account when available, otherwise YouTube or Instagram.
- Preserve the submitted source URL on every recipe.
- Allow the plural formatter to identify up to 10 recipes in social text; preserve no_recipe_found and too_many_recipes.
- Translate known yt-dlp availability/private/login failures into safe source_unavailable responses.
- Translate unexpected upstream failures into source_fetch_failed and log details server-side.

Implementation shape:
- Prefer one focused backend/social_extractor.py with small pure helpers for classification, caption choice, parsing, and normalization.
- Keep service/route orchestration thin.
- Do not create a plugin framework or base extractor hierarchy.

Testing:
- Mock YoutubeDL and caption HTTP responses; never contact YouTube or Instagram in permanent tests.
- Cover YouTube description only, human captions preferred, automatic fallback, non-English fallback, JSON3 parsing, WebVTT parsing, duplicate removal, no content, oversized caption response, oversized combined text, private/unavailable video, and playlist rejection.
- Cover Instagram public caption, absent caption, private/login-required post, unsupported path, and confirmation that media fields are ignored.
- Cover one and multiple formatted recipes with source metadata applied to every item.
- Cover conventional URL dispatch remains on the recipe scraper.
- Tests must fail if any code attempts a media download.

Likely files:
- pyproject.toml
- backend/social_extractor.py (new)
- backend/services.py
- backend/api.py only if established error mapping requires it
- backend/source_errors.py and URL helper only for necessary supported-host integration
- targeted tests under tests/
- Dockerfile only if dependency installation alone does not provide the required JavaScript runtime

Non-goals:
- No frontend layout work.
- No media download/transcription/OCR.
- No social authentication.
- No Gemini formatting-rule changes.
- No CLI edits.

Verification:
- Install updated dependencies into .venv.
- Run targeted social extraction/dispatch tests, then the complete Python test suite.
- Run extraction-only smoke only if YOUTUBE_SMOKE_URL or INSTAGRAM_SMOKE_URL is already supplied. Never invent a third-party URL or call Gemini/Paprika.
- Build the Docker image far enough to prove yt_dlp plus the JavaScript runtime are available in the final Python stage.

Finish by reporting files, exact results, whether optional live extraction was skipped, and external limitations. Do not claim M1 complete.
```

---

## Session 7 — Social-source frontend errors and guidance

**Model:** `openai-codex/gpt-5.6-luna`

**Start:**

```bash
omp --model openai-codex/gpt-5.6-luna
```

**Prompt:**

```text
Work in the recipe-importer repository. This is Session 7 of M1; Sessions 1–6 are already applied.

First read CLAUDE.md, APPLICATION-FINDINGS.md, and M1-OMP-PLAYBOOK.md. Read skill://frontend-design because this session changes user-facing copy and states. Inspect only the frontend API wrapper, import hook, App, ImportForm, StatusBar, selection/queue components, and backend error examples needed to consume the frozen contract. Summarize your understanding and ask exactly: "Should I proceed?" Do not edit until I answer yes. After approval, complete the session.

Goal:
Expose social URL behavior clearly and preserve actionable backend source/batch errors through the PWA.

Required changes:
1. Keep YouTube and Instagram links in URL; do not add social tabs.
2. Update URL label/placeholder/helper copy to name recipe pages, YouTube, and Instagram.
3. Parse structured FastAPI error detail in apiFetch. Preserve its safe message in a typed frontend error and retain a generic fallback for malformed/non-JSON failures.
4. Make useImport display the safe backend message instead of replacing every failure with “Whoops! Try again.”
5. Ensure YouTube/Instagram unavailable errors direct the user to Text.
6. Give no_recipe_found and too_many_recipes clear import-level messages. The over-10 case must not enter selection with a truncated list.
7. Preserve 401 logout, loading, one-result bypass, multi-selection/queue, partial sync retry, settings, and Paprika behavior.
8. Keep source selection and long errors legible at 390px. Do not redesign the application.

Likely files:
- frontend/src/api.ts
- frontend/src/hooks/useImport.ts
- frontend/src/components/ImportForm.tsx
- frontend/src/components/StatusBar.tsx
- frontend/src/App.tsx only if required

Non-goals:
- No backend changes unless its implemented response violates the playbook; report that blocker before changing the contract.
- No navigation library, social tab, persisted error, CLI edit, or AI prompt edit.

Acceptance:
- Mocked YouTube and Instagram unavailable responses show the Text fallback guidance.
- no_recipe_found shows a useful source-level error.
- too_many_recipes shows the 10-recipe limit and no selection screen.
- A malformed 500 shows a generic safe fallback.
- A 401 still clears auth and redirects.
- URL, Images, Text, one-result review, and multi-result selection remain usable.

Verification:
- Run npm run lint and npm run build.
- Serve the production frontend and use request interception at 390x844 for generic URL success, multi-recipe URL success, YouTube unavailable, Instagram unavailable, no recipe, too many recipes, pasted-text success, malformed server failure, and 401 logout.
- Capture visual confirmation of source selection, multi-recipe selection, and a long error message.

Finish by reporting files, commands/results, and browser scenarios. Do not claim M1 complete.
```

---

## Session 8 — Integration, cleanup, and completion gate

**Model:** `openai-codex/gpt-5.6-sol`

**Start:**

```bash
omp --model openai-codex/gpt-5.6-sol
```

**Prompt:**

```text
Work in the recipe-importer repository. This is Session 8, the M1 integration and completion gate. Sessions 1–7 are already applied.

First read CLAUDE.md, APPLICATION-FINDINGS.md, and M1-OMP-PLAYBOOK.md. Inspect the complete diff and all affected call sites, tests, dependencies, Docker configuration, API contracts, formatter contracts, and frontend flows. Use language-server references before changing exported symbols. Summarize your understanding, list contract deviations, and ask exactly: "Should I proceed?" Do not edit until I answer yes. After approval, integrate and verify the complete milestone without broadening scope.

Goal:
Prove every M1 source and single/multiple-recipe flow works end to end, repair only integration defects, remove M1 scaffolding, and leave a production-buildable repository.

Required review:
1. Confirm every import endpoint returns recipes only; singular recipe, quick, and synced import contracts are removed from all backend/frontend callers.
2. Confirm the formatter always uses the strict recipes/has_more envelope and rejects empty, malformed, over-10, or has_more batches without truncation.
3. Confirm one result bypasses selection and multiple results require explicit selection.
4. Confirm queue order, fresh per-recipe edits/categories, partial sync retry, completed-item tracking, and final count are correct.
5. Confirm conventional URLs use safe recipe scraping and social domains never fall back to generic HTML.
6. Confirm pasted/social text shares the PWA prompt path and source metadata is applied to every recipe.
7. Confirm neither src/recipe_importer nor the CLI was modified for parity.
8. Confirm no path downloads media, invokes ffmpeg, passes social cookies, processes Instagram media fields, or submits multiple caption tracks.
9. Confirm every count/size/timeout/redirect limit is named and enforced before Gemini where applicable.
10. Confirm OAuth state, fragment token handling, API-cache removal, source errors, and sync notifications remain correct.
11. Remove permanent tests that only assert source wording, field forwarding, mock echoes, or implementation details.

Required automated verification:
- Run targeted auth, URL safety, formatter batch, selection-relevant API, pasted text, social extraction, and dispatch tests.
- Run the complete Python test suite.
- Inspect generated OpenAPI: /api/import/text exists; all import responses are plural; quick/synced are absent; /api/sync remains singular.
- Run npm run lint and npm run build.
- Build the production Docker image and run a container-level check for backend.main, yt_dlp, yt-dlp-ejs, and its JavaScript runtime.

Required browser smoke at a mobile viewport with deterministic intercepted APIs:
1. Login and OAuth fragment consumption.
2. URL, Images, and Text source controls.
3. Single-result direct review.
4. Three-result selection with none selected, Select all/Clear, and sparse selection.
5. Sequential sync in source order.
6. Partial failure/retry without resending completed or unselected recipes.
7. Fresh edits/categories per queued recipe and accurate completion count.
8. Pasted-text multi-result response.
9. YouTube/Instagram unavailable guidance.
10. no_recipe_found, too_many_recipes, malformed server failure, Settings, and logout.
11. No api-cache reuse across a simulated account change.

Optional live extraction:
- If YOUTUBE_SMOKE_URL or INSTAGRAM_SMOKE_URL is supplied, run extraction only and report metadata obtained.
- Do not call Gemini or Paprika.
- Treat live-site failure as an external limitation, not a passing or failing deterministic application test.

Cleanup:
- Remove temporary scripts, smoke files, stale comments, and untracked build artifacts.
- Update existing relevant configuration/docs for dependencies, source/batch limits, response cutover, and best-effort social behavior. Do not create extra planning documents.
- Keep APPLICATION-FINDINGS.md as the pre-M1 baseline and M1-OMP-PLAYBOOK.md as the execution record unless a factual correction is necessary.

Completion criteria:
- Every fixed-scope source works through the plural contract and correct PWA flow.
- All targeted and complete checks pass.
- Production build and container dependency check pass.
- Browser smoke covers every named state and queue invariant.
- No stubs, TODOs, compatibility aliases, unused imports, singular import callers, or duplicate new source implementations remain.
- Unavailable live verification is reported exactly, never presented as passed.

Finish with a concise M1 delivery report: behavior, files grouped by backend/frontend/config/tests, exact commands/results, browser scenarios, queue request evidence, and remaining external limitations. Only this session may state M1 is complete.
```

## Expected file impact

This is a forecast, not permission to create every file regardless of need.

### Existing files likely modified

```text
pyproject.toml
Dockerfile                         only if the yt-dlp Deno extra is insufficient
backend/api.py
backend/auth_routes.py
backend/formatter.py
backend/oauth.py
backend/schemas.py
backend/scraper.py
backend/services.py
frontend/src/App.tsx
frontend/src/api.ts
frontend/src/hooks/useImport.ts
frontend/src/types.ts
frontend/src/components/CategoryPicker.tsx
frontend/src/components/EditRecipe.tsx
frontend/src/components/ImportForm.tsx
frontend/src/components/Settings.tsx
frontend/src/components/StatusBar.tsx
frontend/vite.config.ts
```

### Focused files likely added

```text
backend/prompts.py
backend/social_extractor.py
backend/source_errors.py
backend/url_safety.py
frontend/src/components/RecipeSelection.tsx
tests/test_auth.py
tests/test_formatter.py
tests/test_import_contract.py
tests/test_social_extractor.py
tests/test_text_import.py
tests/test_url_safety.py
```

Do not add an extractor registry, abstract base classes, server-side/background job queue, database model, routing library, state-management library, media utility, or separate YouTube/Instagram frontend component. The required in-memory frontend review queue remains owned by `useImport`.

## Final acceptance matrix

| Scenario | Expected observable result |
|---|---|
| Import endpoint response | `recipes` list only; no singular `recipe`, import `quick`, or `synced` |
| One detected recipe | Selection is bypassed; recipe opens in review |
| Three detected recipes | Selection displays all titles with none selected |
| Select all then Clear | All selections toggle accurately; Continue disables after Clear |
| Select recipes 1 and 3 | Review/sync order is 1 then 3; recipe 2 is never sent |
| Sync recipe 1, fail recipe 3 | Recipe 1 stays complete; recipe 3 remains edited and retryable |
| Retry recipe 3 | Only recipe 3 is resent; completion count is 2 |
| Per-recipe edits/categories | State is fresh for each queued recipe and never leaks forward |
| Exactly 10 formatted recipes | Batch is accepted and selection shows 10 |
| 11 recipes or `has_more=true` | Whole import rejected as `too_many_recipes`; no truncated selection |
| Empty recipe batch | `no_recipe_found`; no selection |
| One malformed batch member | Whole import rejected; valid siblings are not silently retained |
| Conventional public recipe URL | Safe scrape and one/multiple recipe formatting works |
| URL resolves to private network | Rejected before HTTP fetch with safe error |
| Public URL redirects to private network | Redirect target rejected before fetch |
| Blank pasted text | Submission blocked/rejected; no Gemini call |
| 100,000-character pasted text | Accepted |
| 100,001-character pasted text | HTTP 413 `source_too_large`; no Gemini call |
| Pasted text with multiple recipes | Same selection and queue behavior |
| YouTube description only | Description formatted into one/multiple recipes |
| YouTube human and automatic captions | One human caption track used |
| YouTube automatic captions only | One automatic track used |
| YouTube non-English caption only | Caption used; Gemini translation rules retained |
| YouTube title only | `source_unavailable` with Text fallback guidance |
| YouTube playlist/profile URL | `invalid_source_url` |
| Instagram public caption | Caption formatted into one/multiple recipes |
| Instagram post without accessible caption | `source_unavailable` with Text fallback guidance |
| Instagram media fields present | Fields ignored; no media request |
| Social extraction upstream failure | Safe structured error; diagnostics only in server log |
| Paprika sync failure | Current recipe remains retryable; no success toast or queue advance |
| OAuth callback state mismatch | Rejected before code exchange |
| OAuth success redirect | JWT appears in fragment and is removed after consumption |
| Logout/account change | Legacy API cache removed; no prior-user API data reused |
| Mobile 390px source and selection screens | Controls remain usable without overflow |

## Known external limitation

YouTube and Instagram can change anonymous extraction behavior independently of this application. M1 guarantees controlled failure and a Text fallback, not permanent access to every public post.

Primary implementation references:

- yt-dlp embedding: <https://github.com/yt-dlp/yt-dlp#embedding-yt-dlp>
- yt-dlp supported sites and reliability warning: <https://github.com/yt-dlp/yt-dlp/blob/master/supportedsites.md>
- yt-dlp EJS/runtime dependencies: <https://github.com/yt-dlp/yt-dlp#dependencies>

## Future AI-formatting changes

Do not change formatting rules during M1. Once exact rules and before/after examples are supplied, create a separate milestone. That work should modify only the authoritative PWA prompt path, define representative evaluation cases, compare observable recipe output, and use a strong model for prompt/evaluation design rather than delegating semantic decisions to a mechanical session.