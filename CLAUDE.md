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

Copy `.env.example` to `.env` and fill in values. Docker Compose reads `.env` automatically.

Required R2 vars: `R2_ACCOUNT_ID`, `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY`, `R2_BUCKET_NAME`

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

## Backend (`backend/`)

- `app/main.py` — FastAPI app, lifespan initializes Qdrant collection (recreates if vector size changed)
- `app/routers/photos.py` — POST `/api/photos/upload` (also captions), POST `/api/photos/search` (`mode: semantic|keyword`), GET `/api/photos` (paginated list), GET `/api/storage` (usage stats), GET `/api/photos/{id}`, PATCH `/api/photos/{id}` (caption edit), DELETE `/api/photos/{id}`
- `app/services/r2_client.py` — boto3 wrapper for R2 (upload, exists, presign, delete)
- `app/services/triton_client.py` — calls CoCa model with mode: `caption` | `encode_image` | `encode_text`
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

## Notes for next session

- Need a full `docker compose up --build` after the CoCa + R2 changes before testing end-to-end
- Existing photos in `./photos` are not in R2 — start fresh (re-upload anything needed)
- Qdrant collection auto-recreates if VECTOR_SIZE changed (512→768 already handled)
- Stale `blip_caption/` and `clip_encode/` dirs in `triton/model_repository/` have root-owned `__pycache__` files that need `sudo rm -rf` to fully remove; workaround is `--model-control-mode=explicit --load-model=coca` in the Triton command

## TODO

### ML improvements

- **Fine-tune CoCa** — once enough photos are indexed, use the image-caption pairs to fine-tune the model for better domain-specific consistency

### Production readiness

- **Authentication** — any user with the URL can upload/delete; add at minimum an API key check on write endpoints
- **Rate limiting** — no endpoint is throttled; `/api/photos/upload` can be hammered to force repeated Triton inference; pair with the auth item above (e.g. API key + per-key rate limit)
- **Complete docker-compose health checks** — only Triton has a healthcheck; Qdrant and backend use default `depends_on: service_started`, so backend can start before Qdrant is ready
- **GPU memory guardrails for Triton** — nothing caps or monitors GPU memory use; given the GTX 1060 6GB dev constraint, add a memory limit/monitoring before running unattended
- **Structured logging** — no logging currently wraps Triton/Qdrant/R2 calls in `backend/app/services/`, so failures surface as bare stack traces with no request context
- **Deploy** — backend + frontend + Qdrant can run on a small VPS; Triton stays local or moves to a rented GPU instance
