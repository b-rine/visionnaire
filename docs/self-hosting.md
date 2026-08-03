# Deploying Visionnaire

## Architecture

```text
[browser] → CF edge → [Oracle cloudflared] → frontend:8080 → backend:8000 → qdrant:6333
                                                                    ↓
[Oracle backend] → CF edge → CF Access policy → [Home cloudflared] → triton:8000
```

Oracle Cloud runs the full app stack (Qdrant, backend, frontend, cloudflared public connector).
Triton stays on the home GPU machine and is reached over a private Cloudflare Tunnel protected
by a Cloudflare Access service token. All TLS is handled at Cloudflare's edge — no certificates
to manage anywhere.

Deploys are fully automated: push to `main` → CI runs → images built and pushed to GHCR →
SSH deploy to Oracle. The manual steps below are one-time only.

See the "Deploy prep for Oracle Cloud + Cloudflare Tunnel" design decision in `CLAUDE.md` for
the reasoning behind these choices (free-tier limits, PAYG billing, why two tunnels).

---

## Step 1 — GitHub Actions secrets

Add these at **Settings → Secrets and variables → Actions → New repository secret**:

| Secret            | Value                                                                                                                                                                                                                                                                                                                                                                                     |
| ----------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `ORACLE_SSH_HOST` | Oracle instance public IP address                                                                                                                                                                                                                                                                                                                                                         |
| `ORACLE_SSH_USER` | `ubuntu` (Oracle Ubuntu default)                                                                                                                                                                                                                                                                                                                                                          |
| `ORACLE_SSH_KEY`  | Full PEM private key for SSH access. Generate a dedicated deploy keypair — never reuse a personal key: `ssh-keygen -t ed25519 -f deploy_key -N "" -C "github-actions-deploy"`. Add `deploy_key.pub` to Oracle's `~/.ssh/authorized_keys`. Paste the contents of `deploy_key` here.                                                                                                        |
| `GHCR_PAT`        | GitHub Personal Access Token (classic) with **`read:packages`** scope only. Used by Oracle to pull images from GHCR. Create at GitHub → Settings → Developer settings → Personal access tokens → Tokens (classic). Alternatively, make both GHCR packages public (GitHub → each package → Package settings → Change visibility) and omit this secret — Oracle can then pull without auth. |

`GITHUB_TOKEN` is automatic and handles image pushes — no manual secret needed for that.

---

## Step 2 — One-time Oracle instance setup

SSH into the instance and run:

```bash
# Install Docker (official convenience script — includes Compose plugin)
curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker ubuntu
# Log out and back in, then verify:
docker run --rm hello-world

# Create the deploy directory. CI will copy docker-compose.prod.yml here automatically.
mkdir -p ~/visionnaire

# Create the production .env — leave CLOUDFLARE_TUNNEL_TOKEN and Triton/Access values
# blank for now; they come from steps 3 and 4 below.
nano ~/visionnaire/.env
chmod 600 ~/visionnaire/.env
```

**Required `.env` values on Oracle:**

| Variable                  | Value                                                 |
| ------------------------- | ----------------------------------------------------- |
| `TRITON_HOST`             | Set in step 4 (e.g. `triton-internal.yourdomain.com`) |
| `TRITON_PORT`             | `443`                                                 |
| `TRITON_SSL`              | `true`                                                |
| `CF_ACCESS_CLIENT_ID`     | Set in step 4                                         |
| `CF_ACCESS_CLIENT_SECRET` | Set in step 4                                         |
| `STORAGE_BACKEND`         | `r2`                                                  |
| `R2_ACCOUNT_ID`           | Cloudflare dashboard → R2 → Account ID                |
| `R2_ACCESS_KEY_ID`        | From R2 API token (see note below)                    |
| `R2_SECRET_ACCESS_KEY`    | From R2 API token                                     |
| `R2_BUCKET_NAME`          | Your R2 bucket name                                   |
| `API_KEY`                 | Generate: `openssl rand -hex 24`                      |
| `ALLOWED_ORIGINS`         | `https://photos.yourdomain.com`                       |
| `CLOUDFLARE_TUNNEL_TOKEN` | Set in step 3                                         |

**R2 API token:** Cloudflare dashboard → R2 → Manage R2 API tokens → Create API token.
Scope: Object Read & Write on your bucket. Copy the Access Key ID and Secret Access Key.

**Security list:** Oracle's Security List should allow only port 22 inbound. Cloudflare Tunnel
uses outbound HTTPS (443) — no inbound ports are needed for app traffic. Quick check:

```bash
sudo iptables -L OUTPUT -n | grep -E '443|REJECT|DROP'
```

OCI Ubuntu defaults allow all outbound, so this should be clear.

---

## Step 3 — Cloudflare: public ingress tunnel

This tunnel routes `photos.yourdomain.com` → `frontend:8080` on Oracle.

1. [one.dash.cloudflare.com](https://one.dash.cloudflare.com) → **Networks → Tunnels → Create a tunnel**
2. Connector type: **Cloudflared**. Name: `visionnaire-public`. Click **Save tunnel**.
3. On the "Install connector" screen, select **Docker**. The page shows a `docker run` command
   containing `--token <long-string>`. Copy that token value — this is `CLOUDFLARE_TUNNEL_TOKEN`.
   Add it to Oracle's `~/visionnaire/.env`.
4. Click **Next** → **Public Hostnames** tab → **Add a public hostname**:
   - Subdomain: `photos` (or your choice)
   - Domain: your Cloudflare-managed domain
   - Service type: `HTTP`
   - URL: `frontend:8080`
     (cloudflared runs on the same Docker network as `frontend`; Docker DNS resolves the name)
5. Click **Save tunnel**. Cloudflare automatically creates a CNAME DNS record — no manual
   DNS step required.

---

## Step 4 — Cloudflare: private Triton bridge + Access policy

This tunnel routes `triton-internal.yourdomain.com` → `triton:8000` on the home machine.
A Cloudflare Access service token ensures only your Oracle backend can reach it.

### 4a. Create the tunnel

1. **Networks → Tunnels → Create a tunnel**. Name: `visionnaire-home-triton`. Save.
2. Select **Docker**, extract the token from the `docker run` command — this is `TRITON_TUNNEL_TOKEN`.
   Add it to the **home machine's** `.env`.
3. **Public Hostnames** → Add hostname:
   - Subdomain: `triton-internal` (keep it non-guessable)
   - Domain: your Cloudflare-managed domain
   - Service type: `HTTP`
   - URL: `triton:8000`
4. Save tunnel.

### 4b. Create the Access service token

1. **Access → Service Auth → Service Tokens → Create Service Token**
2. Name: `visionnaire-oracle-backend`. TTL: 1 year (or non-expiring if your plan allows).
3. Click **Generate token**. **Values shown exactly once** — save both immediately:
   - `CF-Access-Client-Id` → `CF_ACCESS_CLIENT_ID` in Oracle's `~/visionnaire/.env`
   - `CF-Access-Client-Secret` → `CF_ACCESS_CLIENT_SECRET` in Oracle's `~/visionnaire/.env`

### 4c. Protect the tunnel hostname with an Access application

1. **Access → Applications → Add an application → Self-hosted**
2. Name: `Triton internal`. Application domain: `triton-internal.yourdomain.com`. Click **Next**.
3. Add a policy:
   - Name: `Service token only`
   - Action: Allow
   - Include rule: Selector = **Service Token**, Value = `visionnaire-oracle-backend`
4. Save. The hostname now rejects any request missing the correct headers. The backend sends
   them on every Triton call (`backend/app/services/triton_client.py`).

### 4d. Finish Oracle .env

Set `TRITON_HOST=triton-internal.yourdomain.com` in Oracle's `~/visionnaire/.env`.

---

## Step 5 — Home machine: start the Triton bridge

`docker-compose.yml` includes a `cloudflared` service for the private Triton tunnel. Add
`TRITON_TUNNEL_TOKEN` to the home machine's `.env`, then:

```bash
docker compose up -d
```

The cloudflared container starts once Triton passes its healthcheck (~90s on first run).
Verify the tunnel shows **Healthy** in the Zero Trust dashboard under Networks → Tunnels.

---

## Step 6 — Trigger the first deploy

Push any commit to `main` (or re-run the CI workflow from the Actions tab). Watch three stages:

1. **CI jobs** (`lint`, `backend`, `backend-integration`, `frontend`) — all must pass
2. **build-push** — cross-compiles ARM64 images and pushes to GHCR
3. **deploy** — deploys images tagged with the exact commit SHA, verifies the public site and
   dependency health, and automatically restores the previous images if verification fails

After the deploy job finishes, SSH into Oracle and confirm:

```bash
cd ~/visionnaire
docker compose -f docker-compose.prod.yml ps
```

All four services (`qdrant`, `backend`, `frontend`, `cloudflared`) should show `healthy`.

---

## Step 7 — Smoke test

- Load `https://photos.yourdomain.com` in a browser — gallery and search should work without a key.
- Try uploading/deleting/editing without a key — should get 401.
- Upload/delete/edit with the real `API_KEY` — should succeed; caption confirms the round-trip
  through both tunnels to home Triton and back.
- Hit search repeatedly (>20 requests/min) — should get 429 past the rate limit.
- Zero Trust dashboard: both tunnels show green **Healthy** connector status.

---

## Ongoing updates

All changes pushed to `main` auto-deploy via CI — no manual steps needed.

**Updating `.env` on Oracle** (e.g. rotating `API_KEY`): SSH in, edit `~/visionnaire/.env`,
then `cd ~/visionnaire && docker compose -f docker-compose.prod.yml up -d`. Or push a dummy
commit to `main` to let CI re-run `up -d` automatically.

The last successfully deployed commit is recorded in `~/visionnaire/.deployed-image-tag`.

**Rolling back:** push a revert commit to `main` (CI handles it), or on Oracle directly:

```bash
cd ~/visionnaire
# Replace <sha> with any commit SHA from the GHCR package page
IMAGE_TAG=<sha> docker compose -f docker-compose.prod.yml pull backend frontend
IMAGE_TAG=<sha> docker compose -f docker-compose.prod.yml up -d --remove-orphans
```

For independent uptime alerts, follow [the Uptime Kuma setup](monitoring.md).
