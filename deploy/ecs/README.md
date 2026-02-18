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
- `nginx/autosedance_domains_http.conf`:
  - example for **domain + HTTP** mode (temporary, before TLS)
  - includes optional Next.js reverse-proxy for a China-only frontend running on the ECS
- `nginx/autosedance_domains.conf`:
  - example for **domain + HTTPS** mode (includes `origin.<domain>` for Vercel back-to-origin rewrites)
  - includes optional Next.js reverse-proxy for a China-only frontend running on the ECS
- `systemd/autosedance-api-prod.service`
- `systemd/autosedance-api-staging.service`
- `systemd/autosedance-web.service` (optional; only if you also run the frontend on ECS)
- `env/prod.env.example`
- `env/staging.env.example`

## Vercel Environment Variables

Set these on Vercel (Project Settings -> Environment Variables):

- Preview:
  - `BACKEND_INTERNAL_URL=http://<ecs-ip>/api-staging`
- Production:
  - `BACKEND_INTERNAL_URL=http://<ecs-ip>/api`

Do **not** set `NEXT_PUBLIC_BACKEND_URL` on Vercel. The frontend should stay same-origin.

## Domain + HTTPS (recommended)

When you set up geo DNS (China -> ECS, overseas -> Vercel), **HTTP-01** TLS validation can break because the
domain may resolve to Vercel outside China. Use **DNS-01** to issue certificates for:

- `aiden-novak.com`
- `www.aiden-novak.com`
- `origin.aiden-novak.com` (IMPORTANT: this record must always point to ECS; no geo split)

Once certs are ready, switch Nginx to the template `nginx/autosedance_domains.conf` and update:

- `ssl_certificate` / `ssl_certificate_key` paths
- `server_name` domains
- Next.js upstream port if needed (default in template: `127.0.0.1:3612`)

Then update Vercel env vars to HTTPS:

- Preview: `BACKEND_INTERNAL_URL=https://origin.aiden-novak.com/api-staging`
- Production: `BACKEND_INTERNAL_URL=https://origin.aiden-novak.com/api`

### ICP / 备案 note (China mainland)

If your ECS is in mainland China, mapping a custom domain to it for public website access generally requires
ICP filing (备案). Without it, the provider/network may serve a block page for the domain even if the IP is reachable.

## ECS Checklist (cloud-only)

> Note (Aliyun): some Alibaba Cloud images ship with **Tengine** (an Nginx-compatible fork) listening on `:80`
> already. In that case:
> - Config root is typically `/etc/tengine/nginx.conf`
> - Site configs are typically in `/etc/tengine/conf.d/*.conf`
> - Reload with `systemctl reload tengine`
>
> The templates under `deploy/ecs/nginx/` are still applicable (syntax-compatible).

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

## Optional: Run the frontend on ECS (China traffic)

If you want China users to avoid Vercel entirely, you can also run the Next.js frontend on the ECS:

1. Install Node.js (recommend Node 20 LTS).
2. In `/srv/autosedance/apps/web`:
   - `npm ci`
   - `npm run build`
3. Install `systemd/autosedance-web.service` and enable it:
   - `systemctl enable --now autosedance-web`
4. Use `nginx/autosedance_domains.conf` which proxies `/` to Next.js and `/api/*` to FastAPI.
