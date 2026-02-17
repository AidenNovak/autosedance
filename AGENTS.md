# Cloud-Only Checklist (do not run locally)

## Exposure Model
- Public: expose only the frontend domain/port.
- Private: backend listens on `127.0.0.1:8000` only.
- Proxy: route `/api/*` from frontend domain to backend.

## Nginx Reverse Proxy
- `location /api/ { proxy_pass http://127.0.0.1:8000; }`
- Set headers: `Host`, `X-Real-IP`, `X-Forwarded-For`, `X-Forwarded-Proto`
- Upload: `client_max_body_size` (match `MAX_UPLOAD_MB`), increase proxy timeouts for video upload.
- Rate limit: stricter for `/api/auth/request_code` and `/api/auth/verify_code`.

## TLS + Network
- HTTPS via Let's Encrypt (certbot) + auto-renew.
- Firewall: allow 80/443 only; block backend port 8000 from public.

## systemd + Secrets
- `autosedance-api.service`: uvicorn (ENV: `AUTH_SECRET_KEY`, SMTP auth code, API keys).
- `autosedance-web.service`: `next start`.
- When behind Nginx, set `TRUST_PROXY_HEADERS=1` and `TRUSTED_PROXY_IPS=127.0.0.1`.

## Ops
- Logs: Nginx access/error + journald; logrotate as needed.
- Backups: `output/autosedance.sqlite3` + `output/projects/` scheduled snapshots.
