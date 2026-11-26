# Visionnaire

[![CI](https://github.com/b-rine/visionnaire/actions/workflows/ci.yml/badge.svg)](https://github.com/b-rine/visionnaire/actions/workflows/ci.yml)
[![codecov](https://codecov.io/gh/b-rine/visionnaire/branch/main/graph/badge.svg)](https://codecov.io/gh/b-rine/visionnaire)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

An ML-powered photo app for image captioning and semantic search, built on a single CoCa
ViT-L-14 model served by Triton Inference Server, with Qdrant for vector search, a FastAPI
backend, and a React frontend.

## Table of Contents

- [Features](#features)
- [Architecture](#architecture)
- [Prerequisites](#prerequisites)
- [Quick Start](#quick-start)
- [Environment Variables](#environment-variables)
- [Development](#development)
- [Testing](#testing)
- [Project Structure](#project-structure)
- [CI/CD](#cicd)
- [Deployment](#deployment)
- [Security](#security)
- [License](#license)
- [Acknowledgments](#acknowledgments)

## Features

- **Caption + index in one step** — upload an image and CoCa generates a natural-language
  caption and a 768-dim embedding in the same request; both are persisted immediately.
- **Semantic search** — query photos with plain text using cross-modal vector similarity
  (CoCa embeds text and images into the same space, so a caption-like query matches similar
  photos directly).
- **Keyword search** — a full-text fallback mode across stored captions, for when you know
  roughly what a photo's caption says but similarity search isn't surfacing it.
- **Gallery** — cursor-paginated browsing of every indexed photo.
- **Caption editing** — edit an auto-generated caption inline; the original CoCa output is
  preserved separately (`caption_override`) so it stays available for future fine-tuning.
- **Content-addressed dedup** — photos are hashed (SHA-256 → deterministic UUID), so
  re-uploading the same image is a no-op instead of a duplicate.
- **Pluggable storage** — local disk by default (zero cloud signup required to run this
  project), or Cloudflare R2 for production.
- **API key auth + rate limiting** — write endpoints (upload/edit/delete) require a shared key.
  Reads (gallery, single-photo, storage stats) stay open, matching a personal/local-use threat
  model rather than a multi-tenant one; search is also open but still rate-limited (see
  [Security](#security)) so it can't be used to brute-force the API key.
- **Health checks** — `/api/health/live` and `/api/health/ready` (the latter checks Qdrant and
  Triton connectivity), used by CI to verify a deploy before leaving it live.

## Architecture

```text
[browser] → CF edge → [Oracle cloudflared] → frontend:8080 → backend:8000 → qdrant:6333
                                                                   ↓
[Oracle backend] → CF edge → CF Access policy → [Home cloudflared] → triton:8000
```

The diagram above is the production topology (see [Deployment](#deployment)), labeled with the
ports each service listens on _inside_ its own container. Running locally, everything runs on
one Docker network with no tunnels involved — the table below lists the **host-facing** ports
`docker compose up` publishes, which is what you'll actually connect to.

| Layer          | Technology                              | Host port (local `docker compose up`)   |
| -------------- | --------------------------------------- | --------------------------------------- |
| Inference      | Triton Inference Server (CoCa ViT-L-14) | 8000–8002 (not published in production) |
| Vector store   | Qdrant                                  | 6333 (not published in production)      |
| Object storage | Local disk (default) or Cloudflare R2   | (local) or (external)                   |
| Backend        | FastAPI                                 | 8080 (container listens on 8000)        |
| Frontend       | React + Vite, served via nginx          | 3000 (container listens on 8080)        |

### Why one model for both caption and search

Most photo apps pair a captioning model with a separate CLIP model for search embeddings.
Visionnaire uses a single CoCa ViT-L-14 checkpoint (`mscoco_finetuned_laion2B-s13B-b90k`) for
both: one Triton model handles captioning, image embedding, and text embedding in the same
vector space, so searching with a generated caption gives consistent similarity scores instead
of comparing across two unrelated embedding spaces.

## Prerequisites

- Docker with the Compose plugin
- An NVIDIA GPU with drivers installed (Triton needs a GPU for inference)
- [nvidia-container-toolkit](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/install-guide.html)
  for GPU passthrough into containers

Only needed for local development or running the test suites outside Docker (matches the
versions CI uses):

- Python 3.12
- Node.js 22 (includes `npm`/`npx`)

## Quick Start

1. Clone the repo.
2. Copy `.env.example` to `.env` and fill in the required values (see
   [Environment Variables](#environment-variables) below).
3. Start everything:

   ```bash
   docker compose up --build
   ```

| Service          | URL                               |
| ---------------- | --------------------------------- |
| Frontend         | <http://localhost:3000>           |
| Backend API docs | <http://localhost:8080/docs>      |
| Qdrant dashboard | <http://localhost:6333/dashboard> |

The Triton model (~1.5 GB) downloads from Hugging Face on first run and is cached in a Docker
volume. First startup will be slow; subsequent ones are fast.

## Environment Variables

Copy `.env.example` to `.env` — Docker Compose reads it automatically.

**Required:**

| Variable  | Default | Description                                                                                          |
| --------- | ------- | ---------------------------------------------------------------------------------------------------- |
| `API_KEY` | —       | Shared key for write endpoints (upload, delete, caption edit). Generate with `openssl rand -hex 24`. |

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
| `LOG_LEVEL`               | `INFO`     | Backend log level (structured JSON logs to stdout).                                       |
| `STORAGE_BACKEND`         | `local`    | `local` (photos on disk, no signup needed) or `r2` (Cloudflare R2).                       |

## Development

Runs Triton, Qdrant, and the backend in Docker while serving the frontend with Vite for instant
hot reload — no container rebuilds needed.

```bash
docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d triton qdrant backend
cd frontend && npm run dev
```

The frontend dev server runs at <http://localhost:5173> and proxies API calls to
`localhost:8080`. The backend reloads automatically on Python file changes.

## Testing

**Backend** — Triton, Qdrant, and the storage backend are all mocked; no Docker or GPU needed:

```bash
cd backend
python -m venv .venv
.venv/bin/pip install -r requirements.txt -r requirements-dev.txt
.venv/bin/pytest -v -m "not integration"
```

A separate, gated suite runs against a real Qdrant instance:

```bash
docker compose up -d qdrant
QDRANT_HOST=localhost .venv/bin/pytest -v -m integration
```

**Frontend unit tests:**

```bash
cd frontend
npm install
npm test
```

**Frontend end-to-end tests** (Playwright, runs against a real browser):

```bash
cd frontend
npm install
npx playwright install chromium
npm run test:e2e
```

## Project Structure

```text
visionnaire/
├── backend/                # FastAPI app
│   ├── app/
│   │   ├── routers/        # photos.py (upload/search/list/edit/delete), health.py
│   │   ├── services/       # triton_client, vector_store, storage, r2_client
│   │   ├── auth.py         # API key dependency + rate limiter
│   │   └── logging_utils.py
│   └── tests/
├── frontend/                # React + Vite
│   └── src/
│       ├── pages/           # Home, Caption, Search, Gallery
│       └── components/      # PhotoLightbox, ApiKeyPrompt
├── triton/model_repository/coca/   # CoCa Python-backend model
├── docs/                     # self-hosting.md, monitoring.md
├── monitoring/                # standalone Uptime Kuma compose stack
├── scripts/                   # deploy-production.sh
└── docker-compose*.yml
```

## CI/CD

Every push and pull request against `main` runs linting (Trunk) first. Once lint passes, four
jobs run in parallel: backend unit tests, a gated backend integration suite against a real
Qdrant container, frontend unit tests with coverage (uploaded to Codecov), and a Playwright
end-to-end suite.

On a push to `main` only, once all of the above pass, two more jobs run:

- **build-push** — cross-compiles ARM64 Docker images for both backend and frontend and pushes
  them to GHCR, tagged `:latest` and `:<sha>`.
- **deploy** — copies the production compose file to the host over SSH and redeploys, then
  verifies the public site and `/api/health/ready`; if verification fails, it automatically
  restores the previously running images.

All third-party GitHub Actions are pinned to a resolved commit SHA (not a floating tag) as a
supply-chain security measure.

## Deployment

The reference production setup runs the backend, frontend, and Qdrant on an Oracle Cloud
Always Free Ampere A1 instance, with Triton running on a local GPU machine reached over a
private Cloudflare Tunnel protected by a Cloudflare Access service token. All TLS is handled at
Cloudflare's edge — no certificates to manage anywhere in the stack.

See [`docs/self-hosting.md`](docs/self-hosting.md) for the full one-time setup runbook, and
[`docs/monitoring.md`](docs/monitoring.md) for setting up independent uptime alerts.

## Security

- Write endpoints (`upload`, `edit caption`, `delete`) require a shared `API_KEY` header; reads
  are open by design (see [Features](#features)).
- Rate limits (`slowapi`, keyed by API key when present and falling back to client IP
  otherwise): `10/minute` on upload, `30/minute` on edit and delete, `20/minute` on search — so
  unauthenticated brute-force key-guessing against search is capped too. Gallery listing,
  single-photo fetch, storage stats, and the health endpoints are not rate-limited.
- All three containers (backend, frontend, Triton) run as non-root users.
- Qdrant has no host port mapping in the production compose file, so it's unreachable from
  outside the host entirely — no external caller can bypass the API key and rate limiting by
  hitting it directly. (It shares Docker's default network with the other containers, same as
  any Compose service; nothing besides the backend is coded to talk to it.)

If you spot a security issue, please open a private security advisory on GitHub rather than a
public issue.

## License

This project is licensed under the [MIT License](LICENSE).

## Acknowledgments

- [open_clip](https://github.com/mlfoundations/open_clip) for the CoCa ViT-L-14 implementation
  and pretrained checkpoints.
- [Triton Inference Server](https://github.com/triton-inference-server/server) for model serving.
- [Qdrant](https://github.com/qdrant/qdrant) for vector search.
