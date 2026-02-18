# ECS + Nginx + systemd (Prod + Staging) with Vercel Frontend

This folder contains **templates** for running two isolated backend instances on a single ECS host:

- Prod API: `127.0.0.1:8000`
- Staging API: `127.0.0.1:8001`
- Public: only Nginx `:80` (and later `:443` once you have a domain + TLS)

Vercel should **not** talk to the backend directly from the browser. Keep the browser on same-origin `/api/*`
and let Next rewrites proxy requests to your ECS Nginx.

## Topology

- Browser -> `https://<vercel-domain>/api/...`
- Vercel Next rewrite -> `http://<ecs-ip>/api/...` (prod) or `http://<ecs-ip>/api-staging/...` (preview)
- ECS Nginx -> `http://127.0.0.1:8000/api/...` or `http://127.0.0.1:8001/api/...`
- Uvicorn -> FastAPI app

Because there is **no domain yet**, the `Vercel -> ECS` hop is **HTTP** (unencrypted). This is acceptable only
for short internal testing. Once you have a domain, switch Nginx to HTTPS and change Vercel rewrites to `https://`.

## Files

- `nginx/autosedance.conf`:
  - `/api/` -> prod
  - `/api-staging/` -> staging (prefix rewritten to `/api/`)
  - rate limits for auth endpoints
  - upload size/timeouts
- `systemd/autosedance-api-prod.service`
- `systemd/autosedance-api-staging.service`
- `env/prod.env.example`
- `env/staging.env.example`

## Vercel Environment Variables

Set these on Vercel (Project Settings -> Environment Variables):

- Preview:
  - `BACKEND_INTERNAL_URL=http://<ecs-ip>/api-staging`
- Production:
  - `BACKEND_INTERNAL_URL=http://<ecs-ip>/api`

Do **not** set `NEXT_PUBLIC_BACKEND_URL` on Vercel. The frontend should stay same-origin.

## ECS Checklist (cloud-only)

1. Put backend behind Nginx only.
   - Uvicorn binds to `127.0.0.1` only.
   - Security group / firewall allows `80` (and later `443`), blocks `8000/8001`.
2. Install templates.
   - Copy Nginx config to `/etc/nginx/conf.d/autosedance.conf`.
   - Copy systemd units to `/etc/systemd/system/`.
   - Create `/etc/autosedance/prod.env` and `/etc/autosedance/staging.env`.
3. Enable services.
   - `systemctl daemon-reload`
   - `systemctl enable --now autosedance-api-prod`
   - `systemctl enable --now autosedance-api-staging`
   - `nginx -t && systemctl reload nginx`
4. Verify.
   - `curl -sS http://127.0.0.1:8000/api/health`
   - `curl -sS http://127.0.0.1:8001/api/health`
   - `curl -sS http://127.0.0.1/api/health` (through Nginx)
   - `curl -sS http://127.0.0.1/api-staging/health`

