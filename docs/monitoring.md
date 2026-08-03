# Monitoring Visionnaire

Visionnaire exposes two backend health endpoints:

- `/api/health/live` confirms that the API process is running.
- `/api/health/ready` confirms that the API can reach both Qdrant and Triton.

The production deployment verifies the public site and readiness endpoint after every release.
If either check fails, it restores the images that were running before the deployment.

## Uptime Kuma

Run Uptime Kuma on a machine independent from the Oracle production instance. An independent
monitor can still alert when the production host or its network is unavailable.

```bash
cd monitoring
docker compose up -d
ssh -L 3001:127.0.0.1:3001 user@monitor-host
```

Open `http://127.0.0.1:3001`, create the administrator account, and enable two-factor
authentication. The bundled Compose file binds the dashboard to localhost, so use the SSH
tunnel above or put it behind an authenticated HTTPS reverse proxy. Keep its named Docker
volume on local storage; do not place Uptime Kuma's data on NFS.

Create these HTTP monitors with a 60-second heartbeat:

| Name                     | URL                                                    | Expected result              |
| ------------------------ | ------------------------------------------------------ | ---------------------------- |
| Visionnaire site         | `https://visionnaire.nguyenbrian.dev/`                 | HTTP 200                     |
| Visionnaire API process  | `https://visionnaire.nguyenbrian.dev/api/health/live`  | HTTP 200                     |
| Visionnaire dependencies | `https://visionnaire.nguyenbrian.dev/api/health/ready` | HTTP 200 and keyword `ready` |

Configure at least one notification channel under **Settings → Notifications**, attach it to
all three monitors, and enable notifications for both failure and recovery. The dependency
monitor is the most diagnostic: its response identifies whether Qdrant or Triton is unavailable.

Do not add a separate monitor for the private Triton hostname unless the Uptime Kuma host has
its own Cloudflare Access service token. Never commit that token to this repository.

## Updating Uptime Kuma

```bash
cd monitoring
docker compose pull
docker compose up -d --force-recreate
```

The configuration follows Uptime Kuma's official version-2 Docker image and stores its state in
the `uptime-kuma-data` volume.
