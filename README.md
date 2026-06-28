# visionnaire

An ML-powered photo app for image captioning and semantic search, built with CoCa ViT-L-14 on Triton Inference Server, Qdrant, FastAPI, and React.

## Features

- **Caption** — upload an image; a CoCa ViT-L-14 model generates a natural-language caption and indexes the photo in one step
- **Semantic search** — query photos with plain text using cross-modal vector similarity (CoCa embeddings stored in Qdrant)
- **Keyword search** — full-text fallback search across stored captions
- **Gallery** — paginated browsing of all indexed photos with hover-to-delete
- **Caption editing** — edit auto-generated captions inline; originals are preserved separately for future fine-tuning

## Architecture

| Layer          | Technology                              |
| -------------- | --------------------------------------- |
| Inference      | Triton Inference Server (CoCa ViT-L-14) |
| Vector store   | Qdrant                                  |
| Object storage | Cloudflare R2                           |
| Backend        | FastAPI                                 |
| Frontend       | React + Vite (served via nginx)         |

## Prerequisites

- Docker with the Compose plugin
- NVIDIA GPU with drivers installed
- [nvidia-container-toolkit](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/install-guide.html) for GPU passthrough into containers

## Quick Start

1. Clone the repo
2. Copy `.env.example` to `.env` and fill in the required values (see [Environment Variables](#environment-variables) below)
3. Start everything:
   ```bash
   docker compose up --build
   ```

| Service          | URL                               |
| ---------------- | --------------------------------- |
| Frontend         | <http://localhost:3000>           |
| Backend API docs | <http://localhost:8080/docs>      |
| Qdrant dashboard | <http://localhost:6333/dashboard> |

The Triton model (~1.5 GB) downloads from HuggingFace on first run and is cached in a Docker volume. First startup will be slow.

## Environment Variables

Copy `.env.example` to `.env`. Docker Compose reads it automatically.

**Required:**

| Variable          | Default | Description                                                                                         |
| ----------------- | ------- | --------------------------------------------------------------------------------------------------- |
| `STORAGE_BACKEND` | `local` | Storage backend: `local` (photos on disk, no signup needed) or `r2` (Cloudflare R2).                |
| `API_KEY`         | —       | Shared key for write endpoints (upload, delete, caption edit). Generate with `openssl rand -hex 24` |

**Required when `STORAGE_BACKEND=r2`:**

| Variable               | Description                      |
| ---------------------- | -------------------------------- |
| `R2_ACCOUNT_ID`        | Cloudflare R2 account ID         |
| `R2_ACCESS_KEY_ID`     | R2 access key ID                 |
| `R2_SECRET_ACCESS_KEY` | R2 secret access key             |
| `R2_BUCKET_NAME`       | R2 bucket name for photo storage |

**Optional:**

| Variable                  | Default    | Description                                                                               |
| ------------------------- | ---------- | ----------------------------------------------------------------------------------------- |
| `LOCAL_PHOTOS_DIR`        | `./photos` | Photo storage directory (local backend only). Docker Compose sets this to `/data/photos`. |
| `ALLOWED_ORIGINS`         | `*`        | Comma-separated CORS allowed origins. Set to your public domain in production.            |
| `TRITON_HOST`             | `triton`   | Triton hostname. Override when reaching Triton remotely (e.g. over a Cloudflare Tunnel).  |
| `TRITON_SSL`              | `false`    | Set to `true` when connecting to Triton over HTTPS.                                       |
| `CF_ACCESS_CLIENT_ID`     | —          | Cloudflare Access service token client ID for Triton tunnel auth.                         |
| `CF_ACCESS_CLIENT_SECRET` | —          | Cloudflare Access service token secret.                                                   |

## Development

Runs Triton, Qdrant, and the backend in Docker while serving the frontend with Vite for instant hot reload — no container rebuilds needed.

```bash
docker compose -f docker-compose.yml -f docker-compose.dev.yml up triton qdrant backend
cd frontend && npm run dev
```

Frontend dev server runs at <http://localhost:5173> and proxies API calls to `localhost:8080`.

## Testing

**Backend** (Triton, Qdrant, and R2 are mocked — no Docker or GPU needed):

```bash
cd backend
python -m venv .venv
.venv/bin/pip install -r requirements.txt -r requirements-dev.txt
.venv/bin/pytest -v -m "not integration"
```

**Frontend:**

```bash
cd frontend
npm install
npm test
```

## Deployment

The production setup runs the backend, frontend, and Qdrant on an Oracle Cloud Always Free Ampere A1 instance, with Triton running on a local GPU machine reached over a private Cloudflare Tunnel. See [docs/self-hosting.md](docs/self-hosting.md) for the full runbook.

## License

This project is licensed under the [MIT License](LICENSE).
