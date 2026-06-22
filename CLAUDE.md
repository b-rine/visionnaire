# Visionnaire

ML-powered photo app: image captioning + semantic search via a single CoCa ViT-L-14 model on Triton, Qdrant for vector search, FastAPI backend, and React frontend. Photos stored in Cloudflare R2.

## Architecture

| Layer          | Service                         | Port                 |
| -------------- | ------------------------------- | -------------------- |
| Inference      | Triton (CoCa ViT-L-14)          | 8000–8002            |
| Vector store   | Qdrant                          | 6333                 |
| Object storage | Cloudflare R2                   | (external)           |
| Backend        | FastAPI                         | 8080 (→ 8000 inside) |
| Frontend       | React + Vite (served via nginx) | 3000                 |

Everything runs via Docker Compose. GPU (NVIDIA) is required for Triton.

## Running

### Production (full Docker)

```bash
docker compose up --build
```

- Frontend: <http://localhost:3000>
- Backend API docs: <http://localhost:8080/docs>
- Qdrant dashboard: <http://localhost:6333/dashboard>

### Development (hot reload — no rebuild needed)

```bash
docker compose -f docker-compose.yml -f docker-compose.dev.yml up triton qdrant backend
cd frontend && npm run dev
```

Frontend at <http://localhost:5173>. API calls proxy to `localhost:8080` (see `vite.config.ts`). Backend reloads on Python file changes.

## Environment variables

Copy `.env.example` to `.env`. Docker Compose reads it automatically. See [`docs/self-hosting.md`](docs/self-hosting.md) for the production deployment runbook (Oracle Cloud + Cloudflare Tunnel).

## Key design decisions

- **Single model for caption + search**: CoCa ViT-L-14 (`mscoco_finetuned_laion2B-s13B-b90k`) replaces BLIP+CLIP. One Triton model handles captioning, image embedding, and text embedding in the same vector space — so searching with a generated caption gives consistent similarity scores. Originally used the base `laion2b_s13b_b90k` checkpoint, but that's trained only on raw LAION-2B web alt-text and produced tabloid-style hallucinated captions (e.g. inventing celebrity names/relationships) since that corpus is full of clickbait-style alt-text templates. Switched to the MS-COCO-finetuned checkpoint, which is what open_clip's own docs use for captioning — same architecture, fine-tuned on clean literal captions, still trains the contrastive objective alongside captioning so embedding/retrieval quality should hold.
- **Captioning also indexes**: Caption tab calls `/api/photos/upload`, which generates the caption (via `caption_image()`) and the embedding (via `encode_image()`) server-side and returns both. There's no standalone `/api/caption` endpoint — captioning and embedding are separate Triton forward passes (`mode="caption"` runs the decoder and zeroes the embedding output; `mode="encode_image"` does the reverse), so there's no way to get both from one inference call regardless of which endpoint orchestrates it; bundling them into the upload endpoint just means one HTTP round trip instead of two, and the caption is persisted instead of only displayed. Search tab is search-only.
- **Captions persisted in Qdrant payload**: stored on upload, returned by `/api/photos/search` and `GET /api/photos`. On a deduplicated re-upload (same image hash already in R2), the existing caption is read back from the stored payload (`get_photo()`) rather than regenerated.
- **Content-addressed photo IDs**: SHA-256 hash of image bytes → deterministic UUID. Same image uploaded twice returns the same ID without re-uploading (dedup via R2 `head_object`).
- **Photos stored in R2**: No local disk storage. `GET /api/photos/{id}` returns a 302 redirect to a 5-minute presigned R2 URL.
- **1 GB storage cap**: Upload endpoint sums `file_size` across all Qdrant points before accepting a new upload. Rejects with 400 if the new file would exceed 1 GiB.
- **Search score threshold & display rescale**: Raw cross-modal cosine similarity from CoCa is inherently compressed by the contrastive training's logit-scale temperature — unrelated pairs typically score ~0.05–0.15 raw, genuinely strong matches ~0.20–0.35. Results below `MIN_SCORE = 0.20` raw cosine are filtered out so unrelated queries return nothing. The remaining raw scores are then linearly rescaled from a fixed `[MIN_SCORE, SCORE_CEILING]` (0.20–0.35) range to 0–100% for display, so a confident match shows as a high percentage instead of a confusing ~30%. This is a **fixed** range, not relative to each query's own top result — commit `bd23094` tried top-result-relative normalization (best match always 100%) and `e30002b` reverted it because unrelated searches also showed 100%. `SCORE_CEILING` is a heuristic for the mscoco-finetuned checkpoint; revisit if real usage data suggests a different calibration.
- **Delete**: `DELETE /api/photos/{id}` removes from R2 first, then Qdrant. Frontend has a hover-to-reveal ✕ button with inline Confirm? step.
- **Gallery pagination**: `GET /api/photos` uses Qdrant's `scroll` cursor (not offset/limit math) — `next_offset` is an opaque point-ID string passed back verbatim on the next request. No sort order is applied (Qdrant scroll order, not upload time), acceptable for the current low-volume use case.
- **Manual caption editing via `caption_override`**: `PATCH /api/photos/{id}` (body: `{"caption": str}`) sets a `caption_override` payload field, stored separately from the auto-generated `caption` rather than overwriting it. Search embeddings come from `encode_image()` on the raw photo bytes, not the caption text, so editing a caption has zero effect on search ranking either way — but keeping the original CoCa output around preserves clean image→caption pairs for eventual fine-tuning. `_effective_caption()` (`caption_override or caption`) is applied everywhere a caption is returned (upload, search, list). An empty-string `caption` in the PATCH body clears the override and reverts display to the auto-generated caption. Frontend: edit affordance lives in `PhotoLightbox` (pencil icon → textarea + Save/Cancel); both `Gallery.tsx` and `Search.tsx` wire an `onCaptionUpdated` callback so the edit persists in their local list state across lightbox close/reopen without a full refetch.
- **Keyword search mode**: `POST /api/photos/search` takes an optional `mode: "semantic" | "keyword"` (default `"semantic"`). Keyword mode does a Qdrant `MatchText` payload filter (`scroll`, not vector `search`) across both `caption` and `caption_override`, OR'd together — a binary text match, not a cosine similarity, so results omit the `score` key entirely (not `null`) and the frontend only renders the score badge `if (score !== undefined)`. Result order is Qdrant scroll order, not relevance-ranked — acceptable since this is a recall backstop, not the primary ranked search. Requires a Qdrant payload text index on both fields, created in `init_collection()` via `create_payload_index` (idempotent, safe to call on every startup). **Tokenizer must be `WORD`, not `WHITESPACE`**: `WHITESPACE` treats `"Alex's"` as one unsplit token, so a query for `"Alex"` would never match it; `WORD` splits on non-alphanumeric characters, producing a separate `"alex"` token that the query can match. Confirmed by a live repro against Qdrant before settling on `WORD`. Frontend: explicit mode toggle on the Search page ("Search by similarity" / "Search by keyword"), not auto-merged with semantic results.
- **Gated Qdrant integration test**: `backend/tests/test_integration_qdrant.py` runs against a real Qdrant instance (Triton/R2 stay mocked — Triton needs a GPU + ~1.5GB model download, infeasible on GitHub-hosted CI runners). Marked `@pytest.mark.integration` (registered in `pytest.ini`) and excluded from the default `pytest -v -m "not integration"` run. Each test monkeypatches `vector_store.COLLECTION` to a random throwaway name and deletes it afterward, so it never touches the real `photos` collection. CI runs it as a separate `backend-integration` job using the `qdrant/qdrant` service container (no GPU needed, so this can run on hosted runners unlike a hypothetical Triton integration test).
- **All three containers run as non-root**: backend (`appuser`), frontend (nginx's own built-in `nginx` user), triton (the image's built-in `triton-server` user, uid 1000) — each Dockerfile now also has a `HEALTHCHECK`. Frontend's nginx had to move off port 80 (privileged, root-only) to `8080` — `frontend/nginx.conf` and the `3000:8080` mapping in `docker-compose.yml` both changed accordingly; the host-facing port (3000) is unchanged. Triton's `HOME` moves from `/root` to `/home/triton-server` under the new user, so the `hf_cache` volume mount in `docker-compose.yml` moved from `/root/.cache/huggingface` to `/home/triton-server/.cache/huggingface` to match — verified live that the existing cached model (root-owned from prior root-user runs) is still readable by the new user (world-readable perms), so this didn't force a re-download. If the cache is ever invalidated and Triton needs to _write_ a fresh model into that root-owned tree, it may hit a permission error — not hit yet, but worth knowing if a future model swap behaves oddly.
- **Removed a stray root-level `package.json`/`package-lock.json`**: an accidental `npm install` once run from the repo root (instead of `frontend/`) left a second, unused dependency tree committed to git, carrying an outdated vulnerable `form-data` transitive dependency. Nothing referenced it (`frontend/` has its own, already-current lockfile) — deleted rather than upgraded.
- **`python-multipart` bumped to `0.0.31`**: patches all four CVEs `osv-scanner` flagged on `0.0.27`. Note: `osv-scanner`'s resolution backend hasn't indexed `0.0.31` yet (confirmed by running it standalone, outside Trunk) and fails with an internal RPC error scanning `backend/requirements.txt` — a transient tooling gap, not a real issue; `0.0.30` resolves fine but leaves one advisory unpatched, so `0.0.31` was kept anyway. Expect this scanner failure to self-resolve as the upstream index catches up.
- **Qdrant healthcheck via bash `/dev/tcp`**: the official `qdrant/qdrant` image has neither `curl` nor `wget`, only `bash`. The compose healthcheck opens a raw TCP connection and sends a literal HTTP GET to `/readyz` via bash's `/dev/tcp` pseudo-device, then greps the response for `200 OK`. Must be invoked as `["CMD", "bash", "-c", "..."]`, not `CMD-SHELL` — Docker's `CMD-SHELL` form always runs via `/bin/sh` regardless of what other shells are in the image, and `/dev/tcp` is a bash-only feature (confirmed live: `CMD-SHELL` failed with `cannot create /dev/tcp/...: Directory nonexistent` under `/bin/sh`). `backend` now depends on `qdrant` with `condition: service_healthy` (was `service_started`), and `frontend` depends on `backend` the same way.
- **Structured logging**: `backend/app/logging_utils.py` — stdlib `logging` (no new dependency) with a custom `JsonFormatter` (one JSON line per record: timestamp/level/logger/message plus any `extra` fields) and a `log_call(operation, context_keys=())` async decorator applied to every Triton/Qdrant/R2 service function. The decorator only logs the explicitly named `context_keys` (e.g. `photo_id`, `mode`, `query`) pulled via `inspect.signature(...).bind()` — nothing is logged by default, so large payloads like image bytes or the 768-float embedding are never accidentally written to logs. Logs `"<operation> completed"` with `duration_ms` on success, `"<operation> failed"` with `duration_ms` and a full exception traceback on failure, then re-raises (logging adds visibility, never changes error-handling behavior). Configured once via `configure_logging()` at the top of `main.py`, reading `LOG_LEVEL` (default `INFO`) and writing to stdout. Scope is deliberately limited to the named service-call functions, not a general HTTP request/response middleware. Verified live by killing Qdrant mid-request: the resulting log line carries the operation name, duration, and full root-cause traceback instead of a bare unattributed stack trace.
- **API key auth on write endpoints only**: `backend/app/auth.py` — a single shared static key (`API_KEY` env var), checked via the `require_api_key` FastAPI dependency on `POST /api/photos/upload`, `PATCH /api/photos/{id}`, and `DELETE /api/photos/{id}`. Reads (gallery list, search, single-photo redirect, storage stats) stay open by design — matches personal/local-use scope, not a multi-tenant API. Frontend (`src/apiKey.ts`): no upfront login gate; an axios response interceptor watches for any 401 and surfaces a single global `ApiKeyPrompt` modal (mounted once in `App.tsx`), regardless of which page/action triggered it. The interceptor is installed once from `main.tsx`, not as a module-level side effect, so existing page-level tests (which render page components directly and never execute `main.tsx`) needed zero changes.
- **Rate limiting via `slowapi`**: `10/minute` on upload (Triton-expensive), `30/minute` on delete and caption-edit, `20/minute` on search (no auth, but still rate-limited — see Deploy prep below) — heuristics, same spirit as the `SCORE_CEILING` note above, revisit if real usage disagrees. Keyed by the `X-API-Key` header, falling back to client IP for unauthenticated requests (so brute-force key-guessing also gets capped, not just legitimate-but-overzealous use). slowapi was dormant for 2+ years between releases (`0.1.9` Feb 2024 → `0.1.10`, current) and has an open issue about breaking on newer Starlette — not a problem at this project's pinned versions (Starlette 0.37.2), but worth re-checking if FastAPI/Starlette ever get bumped. The in-memory limiter's counters are reset between tests via `limiter._storage.reset()` (a private attribute — slowapi has no public API for this, tracked as their own open issue #273) since the test suite's `app` instance, and the `Limiter` singleton inside it, persist across the whole pytest session via Python's module cache.
- **Deploy prep for Oracle Cloud + Cloudflare Tunnel**: decided on Oracle's Always Free Ampere A1 tier (1 of 2 free OCPUs/12GB RAM, comfortably under the 1,500 OCPU-hour/9,000 GB-hour monthly cap even running 24/7) for backend + frontend + Qdrant; account converts to Pay-As-You-Go specifically to dodge Oracle's idle-instance reclamation policy (PAYG doesn't change the free allotment, it only allows — and bills for — exceeding it). Triton stays on the local GTX 1060 rather than a rented GPU instance, reached over a private Cloudflare Tunnel; the public-facing app reaches the Oracle instance over a second Cloudflare Tunnel, so TLS is handled at Cloudflare's edge on both legs with no certs to manage anywhere in this stack. `docker-compose.prod.yml` is a standalone file (not a merge override of `docker-compose.yml`) since the topology genuinely differs — no `triton` service, no GPU block, and Qdrant has no host port mapping (closes a real gap: the base compose file publishes Qdrant's port with zero auth of its own, letting anyone who reaches it bypass the backend's API key and rate limiting entirely). `backend/app/services/triton_client.py` gained `TRITON_SSL` (the tunnel hostname is HTTPS) and `CF_ACCESS_CLIENT_ID`/`CF_ACCESS_CLIENT_SECRET` (sent as headers on every Triton call — confirmed `tritonclient`'s `infer()` forwards arbitrary custom headers, only `Transfer-Encoding` is blocked) to protect the private tunnel with a Cloudflare Access service token, since otherwise anyone who found that hostname could reach Triton directly. `ALLOWED_ORIGINS` env var replaces the hardcoded CORS `allow_origins=["*"]` (defaults to `*` so local dev needs no `.env` change). The manual account/console/DNS steps can't be done from this repo — see [`docs/self-hosting.md`](docs/self-hosting.md) for that runbook.

## Backend (`backend/`)

- `app/main.py` — FastAPI app, lifespan initializes Qdrant collection (recreates if vector size changed); wires up the `slowapi` limiter and rate-limit exception handler
- `app/auth.py` — `API_KEY` env var, `require_api_key` dependency (write endpoints), `slowapi` `Limiter` keyed by `X-API-Key` (falls back to client IP)
- `app/routers/photos.py` — POST `/api/photos/upload` (also captions, requires API key + rate-limited), POST `/api/photos/search` (`mode: semantic|keyword`, no auth), GET `/api/photos` (paginated list), GET `/api/storage` (usage stats), GET `/api/photos/{id}`, PATCH `/api/photos/{id}` (caption edit, requires API key + rate-limited), DELETE `/api/photos/{id}` (requires API key + rate-limited)
- `app/services/r2_client.py` — boto3 wrapper for R2 (upload, exists, presign, delete)
- `app/services/triton_client.py` — calls CoCa model with mode: `caption` | `encode_image` | `encode_text`; `TRITON_SSL`/`CF_ACCESS_CLIENT_ID`/`CF_ACCESS_CLIENT_SECRET` support reaching Triton over a Cloudflare Tunnel once deployed
- `app/services/vector_store.py` — Qdrant ops; VECTOR_SIZE=768 (CoCa embed dim); `get_photo()` retrieves a single point's payload (used for dedup caption lookup); `update_caption_override()` is a payload-only `set_payload` (no vector resend); `search_photos_keyword()` does a `MatchText` `scroll` filter against `caption`/`caption_override`

### Testing (backend)

External services (Triton, Qdrant, R2) are all mocked — tests run without Docker.

```bash
cd backend
python -m venv .venv
.venv/bin/pip install -r requirements.txt -r requirements-dev.txt
.venv/bin/pytest -v -m "not integration"
```

Gated integration suite (needs a real Qdrant): `docker compose up -d qdrant && QDRANT_HOST=localhost .venv/bin/pytest -v -m integration`.

## Frontend (`frontend/`)

- `src/pages/Caption.tsx` — drag/click to upload; single `/api/photos/upload` call returns id + filename + caption; shows caption + "Indexed: filename"; storage usage bar fetched from `/api/storage` on load and after each upload
- `src/pages/Search.tsx` — mode toggle ("Search by similarity" / "Search by keyword") above the search bar; text query → photo grid, similarity mode shows score %, keyword mode shows no score badge; hover-to-delete with confirmation; click a thumbnail to open it in `PhotoLightbox`
- `src/pages/Gallery.tsx` — paginates all indexed photos via `/api/photos` (Load more button), same hover-to-delete pattern as Search, same lightbox-on-click
- `src/components/PhotoLightbox.tsx` — shared modal: larger image, caption (if present) with a pencil-icon edit affordance (textarea + Save/Cancel, `PATCH /api/photos/{id}` on save), score badge (if present — Search passes it, Gallery doesn't), delete button (drives the parent page's existing confirm-step delete state, no delete logic of its own). An optional `onCaptionUpdated` callback lets the parent page (`Gallery`/`Search`) update its own list state so an edited caption persists across lightbox close/reopen. Closes on backdrop click or Escape.
- `src/apiKey.ts` — localStorage-backed API key get/set, `installApiKeyInterceptors()` (called once from `main.tsx`) attaches the key to outgoing requests and surfaces a global prompt on any 401
- `src/components/ApiKeyPrompt.tsx` — modal shown when `apiKey.ts`'s interceptor sees a 401; saves the key and dismisses
- `src/index.css` — shared styles

### Testing (frontend)

```bash
cd frontend
npm install
npm test
```

## Triton model (`triton/model_repository/coca/`)

Single Python backend model. `config.pbtxt` defines two inputs (`input_data` bytes, `input_mode` string) and two outputs (`embedding` FP32[768], `caption` string). Unused output is zeroed/empty per request.

Model downloads from HuggingFace on first run (~1.5 GB, cached in `hf_cache` Docker volume). First startup after a fresh build will be slow.

## TODO

### ML improvements

- **Fine-tune CoCa** — once enough photos are indexed, use the image-caption pairs to fine-tune the model for better domain-specific consistency

### Production readiness

- **GPU memory guardrails for Triton** — nothing caps or monitors GPU memory use; given the GTX 1060 6GB dev constraint, add a memory limit/monitoring before running unattended
- **Deploy** — Oracle instance is provisioned and `docker-compose.prod.yml` is ready. Remaining steps are DNS record creation and Cloudflare Tunnel setup — see [`docs/self-hosting.md`](docs/self-hosting.md).
