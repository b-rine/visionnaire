# Deploying Visionnaire

Architecture: backend + frontend + Qdrant run on an Oracle Cloud "Always
Free" Ampere A1 instance. Triton stays on the local GTX 1060 (no rented GPU
instance) and is reached from the Oracle instance over a private Cloudflare
Tunnel. Public traffic also reaches the Oracle instance through a separate
Cloudflare Tunnel, so TLS is handled by Cloudflare's edge on both legs — no
certificates to manage anywhere in this stack.

See the "Deploy prep for Oracle Cloud + Cloudflare Tunnel" design decision
in `CLAUDE.md` for the reasoning behind these choices (free-tier limits,
PAYG billing, why two tunnels).

## 1. Oracle Cloud instance

1. Create an Oracle Cloud account.
2. Provision an Ampere A1 instance: 1 OCPU / 6GB RAM (half the 2 OCPU / 12GB
   Always Free allotment — leaves headroom and comfortably avoids ever
   approaching the 1,500 OCPU-hour / 9,000 GB-hour monthly cap even running
   continuously).
3. Convert the account to Pay-As-You-Go billing. This does **not** change
   the free allotment or start charging for normal usage — it only avoids
   Oracle's idle-instance reclamation policy (Free Tier-only accounts get
   idle compute stopped after ~7 days under ~15-20% CPU utilization), and
   would only result in charges if usage ever exceeds the Always Free caps.
4. Install Docker + the Docker Compose plugin on the instance.
5. Clone this repo onto the instance.
6. Create `.env` on the instance (copy `.env.example`, fill in real values):
   `API_KEY`, R2 vars, `ALLOWED_ORIGINS` (the real public domain, e.g.
   `https://photos.yourdomain.com`), and leave `TRITON_HOST` /
   `CF_ACCESS_CLIENT_ID` / `CF_ACCESS_CLIENT_SECRET` for step 3 below.

## 2. Cloudflare: public ingress tunnel

Run on the Oracle instance, following the setup comment in
`cloudflared/public-ingress.yml`. Fill in the tunnel ID and your real domain
in that file, then run `cloudflared tunnel --config cloudflared/public-ingress.yml run`
(or install it as a systemd service so it survives reboots — `cloudflared
service install` after the config file is in place).

## 3. Cloudflare: private Triton bridge

Run on the **home machine** (where `docker compose up` already runs Triton
locally), following the setup comment in `cloudflared/home-triton.yml`. This
step also creates a Cloudflare Access service token — put the resulting
Client ID/Secret into the Oracle instance's `.env` as `CF_ACCESS_CLIENT_ID`
/ `CF_ACCESS_CLIENT_SECRET`, and set `TRITON_HOST` there to the tunnel
hostname (e.g. `triton-internal.yourdomain.com`).

Without the Access policy on this hostname, Triton would be reachable by
anyone who finds it, not just your backend — don't skip it.

## 4. Bring up the app

On the Oracle instance:

```bash
docker compose -f docker-compose.prod.yml up --build -d
```

This is a standalone compose file (not merged with the local
`docker-compose.yml`) — it omits Triton entirely (no GPU on this instance)
and doesn't publish Qdrant's port to the host.

## 5. Smoke test

- Load the public domain in a browser — gallery and search should work
  with no key.
- Try uploading/deleting/editing without a key — should 401.
- Upload/delete/edit with the real `API_KEY` — should succeed, and the
  caption should come back correctly (confirms the request round-tripped
  through both tunnels to home Triton and back).
- Hit search repeatedly — should 429 past the configured threshold
  (`backend/app/routers/photos.py`).
