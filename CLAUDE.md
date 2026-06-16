# Visionnaire

ML-powered photo app: image captioning (BLIP) + semantic search (CLIP) via Triton Inference Server, Qdrant, FastAPI, and React.

## Architecture

| Layer | Service | Port |
|---|---|---|
| Inference | Triton (BLIP caption, CLIP encode) | 8000–8002 |
| Vector store | Qdrant | 6333 |
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

Run Triton, Qdrant, and backend in Docker with live code reload:

```bash
docker compose -f docker-compose.yml -f docker-compose.dev.yml up triton qdrant backend
```

Then in a separate terminal, run the frontend with Vite's dev server (HMR):

```bash
cd frontend && npm run dev
```

Frontend available at http://localhost:5173. API calls are proxied to `localhost:8080` automatically (see `vite.config.ts`). Backend Python changes trigger an automatic uvicorn reload via the mounted volume.

## Key design decisions

- **Captioning also indexes**: uploading an image on the Caption tab calls both `/api/caption` and `/api/photos/upload` in parallel. The Search tab is search-only.
- **Photos stored on disk**: uploaded images are saved to `./photos/` (mounted into the backend container as `/photos`).
- **Triton client has a connect timeout**: set to prevent backend startup crash when Triton isn't ready yet.

## Backend (`backend/`)

- `app/main.py` — FastAPI app, lifespan initializes Qdrant collection
- `app/routers/caption.py` — POST `/api/caption`
- `app/routers/photos.py` — POST `/api/photos/upload`, POST `/api/photos/search`, GET `/api/photos/{id}`
- `app/services/` — Triton client, Qdrant vector store

### Testing (backend)

External services (Triton, Qdrant) are mocked — tests run without Docker.

```bash
cd backend
python -m venv .venv
.venv/bin/pip install -r requirements.txt -r requirements-dev.txt
.venv/bin/pytest -v
```

## Frontend (`frontend/`)

- `src/pages/Caption.tsx` — drop/click to upload; calls caption + index in parallel
- `src/pages/Search.tsx` — text query → semantic photo search
- `src/index.css` — shared styles; `.dropzone` must be `display: block`

### Testing (frontend)

```bash
cd frontend
npm install
npm test
```

## Triton models (`triton/model_repository/`)

- `blip_caption/` — image → text caption
- `clip_encode/` — image or text → embedding vector

Models download from HuggingFace on first run (cached in `hf_cache` Docker volume).
