# Visionnaire

ML-powered photo app: image captioning + semantic search via a single CoCa ViT-L-14 model on Triton, Qdrant for vector search, FastAPI backend, and React frontend. Photos stored in Cloudflare R2.

## Architecture

| Layer | Service | Port |
|---|---|---|
| Inference | Triton (CoCa ViT-L-14) | 8000–8002 |
| Vector store | Qdrant | 6333 |
| Object storage | Cloudflare R2 | (external) |
| Backend | FastAPI | 8080 (→ 8000 inside) |
| Frontend | React + Vite (served via nginx) | 3000 |

Everything runs via Docker Compose. GPU (NVIDIA) is required for Triton.

## Running

### Production (full Docker)

```bash
docker compose up --build
```

- Frontend: http://localhost:3000
- Backend API docs: http://localhost:8080/docs
- Qdrant dashboard: http://localhost:6333/dashboard

### Development (hot reload — no rebuild needed)

```bash
docker compose -f docker-compose.yml -f docker-compose.dev.yml up triton qdrant backend
cd frontend && npm run dev
```

Frontend at http://localhost:5173. API calls proxy to `localhost:8080` (see `vite.config.ts`). Backend reloads on Python file changes.

## Environment variables

Copy `.env.example` to `.env` and fill in values. Docker Compose reads `.env` automatically.

Required R2 vars: `R2_ACCOUNT_ID`, `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY`, `R2_BUCKET_NAME`

## Key design decisions

- **Single model for caption + search**: CoCa ViT-L-14 (`laion2b_s13b_b90k`) replaces BLIP+CLIP. One Triton model handles captioning, image embedding, and text embedding in the same vector space — so searching with a generated caption gives consistent similarity scores.
- **Captioning also indexes**: Caption tab calls `/api/caption` and `/api/photos/upload` in parallel. Search tab is search-only.
- **Content-addressed photo IDs**: SHA-256 hash of image bytes → deterministic UUID. Same image uploaded twice returns the same ID without re-uploading (dedup via R2 `head_object`).
- **Photos stored in R2**: No local disk storage. `GET /api/photos/{id}` returns a 302 redirect to a 5-minute presigned R2 URL.
- **1 GB storage cap**: Upload endpoint sums `file_size` across all Qdrant points before accepting a new upload. Rejects with 400 if the new file would exceed 1 GiB.
- **Search score threshold**: Results below 0.20 cosine similarity are filtered out so unrelated queries return nothing.
- **Delete**: `DELETE /api/photos/{id}` removes from R2 first, then Qdrant. Frontend has a hover-to-reveal ✕ button with inline Confirm? step.

## Backend (`backend/`)

- `app/main.py` — FastAPI app, lifespan initializes Qdrant collection (recreates if vector size changed)
- `app/routers/caption.py` — POST `/api/caption`
- `app/routers/photos.py` — POST `/api/photos/upload`, POST `/api/photos/search`, GET `/api/photos/{id}`, DELETE `/api/photos/{id}`
- `app/services/r2_client.py` — boto3 wrapper for R2 (upload, exists, presign, delete)
- `app/services/triton_client.py` — calls CoCa model with mode: `caption` | `encode_image` | `encode_text`
- `app/services/vector_store.py` — Qdrant ops; VECTOR_SIZE=768 (CoCa embed dim)

### Testing (backend)

External services (Triton, Qdrant, R2) are all mocked — tests run without Docker.

```bash
cd backend
python -m venv .venv
.venv/bin/pip install -r requirements.txt -r requirements-dev.txt
.venv/bin/pytest -v
```

## Frontend (`frontend/`)

- `src/pages/Caption.tsx` — drag/click to upload; calls caption + index in parallel; shows caption + "Indexed: filename"
- `src/pages/Search.tsx` — text query → photo grid with similarity %, hover-to-delete with confirmation
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

### UX gaps
- **Gallery/browse page** — no way to see all indexed photos without searching; add a third tab that paginates through all Qdrant points
- **Storage usage indicator** — show "X MB of 1 GB used" on the Caption page so the cap doesn't come as a surprise

### ML improvements
- **Store captions in Qdrant payload** — captions are generated but discarded; storing them enables showing captions under search results and keyword-based fallback search
- **Fine-tune CoCa** — once enough photos are indexed, use the image-caption pairs to fine-tune the model for better domain-specific consistency

### Production readiness
- **Authentication** — any user with the URL can upload/delete; add at minimum an API key check on write endpoints
- **Deploy** — backend + frontend + Qdrant can run on a small VPS; Triton stays local or moves to a rented GPU instance
