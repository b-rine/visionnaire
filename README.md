# Visionnaire

Photo app for image captioning and semantic search, built on CoCa served by Triton with Qdrant vector search

## Overview

### Features

- **Caption and index in one step.** An upload generates a natural-language caption and a
  768-dimensional image embedding. Both are persisted to Qdrant.
- **Semantic search.** Search photos with plain text using similarity between text and image embeddings.
- **Keyword search.** Run a full-text search across stored captions.
- **Gallery.** Browse indexed photos with cursor pagination.
- **Caption editing.** Edit a caption inline. The edit is stored in `caption_override`,
  preserving the original CoCa caption for future fine-tuning.
- **Deduplication.** A SHA-256 hash determines each photo's UUID. Re-uploading an indexed
  photo returns its existing record.
- **Pluggable storage.** Store photos on local disk by default or in Cloudflare R2.
- **API key authentication and rate limiting.** Writes require a shared key. Reads are public
  for personal or local use, and search is public and rate-limited. See [Security](#security).
- **Health checks.** Use `/api/health/live` for liveness and `/api/health/ready` for Qdrant
  and Triton readiness. The deployment script checks readiness after a deploy.

### Architecture

```text
[browser] → CF edge → [Oracle cloudflared] → frontend:8080 → backend:8000 → qdrant:6333
                                                                   ↓
[Oracle backend] → CF edge → CF Access policy → [Home cloudflared] → triton:8000
```

The diagram shows the [production topology](#deployment) and internal container ports.
The local app services communicate over the Compose network.

#### Why one model for both caption and search

Visionnaire uses one CoCa ViT-L-14 checkpoint (`mscoco_finetuned_laion2B-s13B-b90k`) for
captioning, image embedding, and text embedding. Images and text share a vector space,
so a generated caption can serve as a query for similar photos.

## Tech stack

| Layer          | Technology                                 | Local host port            |
| -------------- | ------------------------------------------ | -------------------------- |
| Inference      | Triton Inference Server with CoCa ViT-L-14 | 8000–8002                  |
| Vector store   | Qdrant                                     | 6333                       |
| Object storage | Local disk or Cloudflare R2                | —                          |
| Backend        | FastAPI                                    | 8080 (container port 8000) |
| Frontend       | React and Vite, served by nginx in Docker  | 3000 (container port 8080) |

### Project Structure

```text
visionnaire/
├── backend/                        # FastAPI app
│   ├── app/
│   │   ├── routers/                # photos.py and health.py
│   │   ├── services/               # triton_client, vector_store, storage, r2_client
│   │   ├── auth.py                 # API key dependency and rate limiter
│   │   └── logging_utils.py
│   └── tests/
├── frontend/                       # React and Vite
│   └── src/
│       ├── pages/                  # Home, Caption, Search, Gallery
│       └── components/             # PhotoLightbox, ApiKeyPrompt
├── triton/model_repository/coca/   # CoCa Python-backend model
├── docs/                           # self-hosting.md, monitoring.md
├── monitoring/                     # Standalone Uptime Kuma Compose stack
├── scripts/                        # deploy-production.sh
└── docker-compose*.yml
```

### Acknowledgments

- [open_clip](https://github.com/mlfoundations/open_clip) for the CoCa ViT-L-14 implementation
  and pretrained checkpoints.
- [Triton Inference Server](https://github.com/triton-inference-server/server) for model serving.
- [Qdrant](https://github.com/qdrant/qdrant) for vector search.

## Getting started

### Prerequisites

- Docker with the Compose plugin
- An NVIDIA GPU and drivers
- [NVIDIA Container Toolkit](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/install-guide.html)
  for GPU passthrough

For local development and tests outside Docker, CI uses Python 3.14 and Node.js 26.

### Quick Start

1. Clone the repository and open its root directory.
2. Copy `.env.example` to `.env` and set `API_KEY` for writes. See [Configuration](#configuration).
3. Build and start the local app services.

   ```bash
   docker compose up --build triton qdrant backend frontend
   ```

| Service          | URL                               |
| ---------------- | --------------------------------- |
| Frontend         | <http://localhost:3000>           |
| Backend API docs | <http://localhost:8080/docs>      |
| Qdrant dashboard | <http://localhost:6333/dashboard> |

On first startup, Triton loads the pretrained checkpoint and caches the download in a Docker volume.

### Development

Run Triton, Qdrant, and the backend in Docker from the repository root. Run the frontend
with Vite for hot reload.

```bash
docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d triton qdrant backend
cd frontend
npm ci
npm run dev
```

Open <http://localhost:5173>. Vite proxies API requests to `localhost:8080`.
The backend reloads on Python file changes.

### Deployment

The reference production setup runs the backend, frontend, and Qdrant on an Oracle Cloud
Ampere A1 instance. Triton runs on a local GPU machine and is reached through a private
Cloudflare Tunnel protected by a Cloudflare Access service token. Cloudflare terminates
public HTTPS at its edge.

See [self-hosting](docs/self-hosting.md) for the one-time setup and
[monitoring](docs/monitoring.md) for independent uptime alerts.

### CI/CD

Pushes to `main` and pull requests targeting `main` run
[Trunk linting](https://github.com/b-rine/visionnaire/actions/workflows/ci.yml) first.
After lint passes, the backend unit suite, Qdrant integration suite, frontend unit suite
with [Codecov](https://codecov.io/gh/b-rine/visionnaire) coverage, and Playwright suite run in parallel.

On pushes to `main`, two jobs run after the tests pass.

- `build-push` builds ARM64 backend and frontend images and publishes them to GHCR with
  `latest` and commit SHA tags.
- `deploy` copies the production Compose file and deployment script to the host and runs
  the script over SSH. The script verifies the public site and `/api/health/ready`. If
  verification fails, it attempts to restore the prior backend and frontend images when both
  are available.

Third-party GitHub Actions are pinned to commit SHAs.

## Usage

Use the [deployed app](https://visionnaire.nguyenbrian.dev) to browse and search photos.
In the local app, use Caption to upload a photo, Search for semantic or keyword queries,
and Gallery to browse indexed photos or edit captions. Enter your API key when prompted
to make a change.

## Configuration

Copy `.env.example` to `.env` for Docker Compose. Generate the shared `API_KEY` for writes
with `openssl rand -hex 24`.

| Purpose                                                | Variables                                                                     |
| ------------------------------------------------------ | ----------------------------------------------------------------------------- |
| Write authentication                                   | `API_KEY`                                                                     |
| CORS allowed origins                                   | `ALLOWED_ORIGINS`                                                             |
| Storage selection and local photo directory            | `STORAGE_BACKEND`, `LOCAL_PHOTOS_DIR`                                         |
| Required for Cloudflare R2 storage                     | `R2_ACCOUNT_ID`, `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY`, `R2_BUCKET_NAME` |
| Triton connection                                      | `TRITON_HOST`, `TRITON_PORT`, `TRITON_SSL`                                    |
| Cloudflare Access service token pair for remote Triton | `CF_ACCESS_CLIENT_ID`, `CF_ACCESS_CLIENT_SECRET`                              |
| Cloudflare Tunnel connectors                           | `CLOUDFLARE_TUNNEL_TOKEN`, `TRITON_TUNNEL_TOKEN`                              |
| Qdrant connection                                      | `QDRANT_HOST`, `QDRANT_PORT`                                                  |
| Backend JSON log level                                 | `LOG_LEVEL`                                                                   |

Compose sets the local photo directory to its mounted volume and points the backend at the
Qdrant service. Set `LOCAL_PHOTOS_DIR` or `LOG_LEVEL` in the process environment when running
the backend directly.

### Security

- Upload, caption edit, and delete require the shared key in the `X-API-Key` header.
  Gallery listing, single-photo fetch, storage stats, search, and health endpoints are public.
- SlowAPI applies limits per API key header when present and per client IP otherwise.
  Upload allows 10 requests per minute, caption edit and delete each allow 30, and search
  allows 20. Gallery listing, single-photo fetch, storage stats, and health are unthrottled.
- The backend, frontend, and Triton containers run as non-root users.
- In the production Compose stack, Qdrant is on the Compose network and has no published host port.

Report security issues through a private GitHub security advisory.

## Testing

Backend unit tests mock Triton, Qdrant, and storage, so they run without Docker or a GPU.

```bash
cd backend
python -m venv .venv
.venv/bin/pip install -r requirements.txt -r requirements-dev.txt
.venv/bin/pytest -v -m "not integration"
```

For the integration suite, start Qdrant from the repository root and wait for
`http://localhost:6333/readyz` to return HTTP 200.

```bash
docker compose up -d qdrant
```

Then enter the backend directory and run the suite using the virtual environment created above.

```bash
cd backend
.venv/bin/pytest -v -m integration
```

### Frontend unit tests

```bash
cd frontend
npm ci
npm test
```

### Frontend end-to-end tests in Chromium

```bash
cd frontend
npm ci
npx playwright install --with-deps chromium
npm run test:e2e
```

## License

This project is licensed under the MIT License. See [LICENSE](LICENSE) for details.
