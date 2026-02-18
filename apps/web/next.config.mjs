/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  async rewrites() {
    // Best-practice for deploys: expose only the frontend and proxy `/api/*` to the backend.
    //
    // IMPORTANT (cookies): do NOT set `NEXT_PUBLIC_BACKEND_URL` on Vercel. Keep the browser
    // on same-origin `/api/*` and use this rewrite to reach your backend; otherwise cookie
    // sessions can break due to cross-origin credentials.

    const raw = (process.env.BACKEND_INTERNAL_URL || process.env.NEXT_PUBLIC_BACKEND_URL || "").trim();

    // Allow both styles for convenience:
    // - API prefix: http://<host>/api or http://<host>/api-staging
    // - Host base : http://<host>  (we'll append /api)
    function normalizeApiBase(s) {
      const base = (s || "").replace(/\/+$/, "");
      if (!base) return "";
      if (base.endsWith("/api") || base.endsWith("/api-staging")) return base;
      return `${base}/api`;
    }

    // Local dev fallback (no env set): backend runs on localhost:8000 with `/api/*`.
    // On Vercel, if you don't set env vars, we simply won't rewrite.
    const apiBase = normalizeApiBase(raw) || (process.env.VERCEL ? "" : "http://localhost:8000/api");

    if (!apiBase) return [];

    return [{ source: "/api/:path*", destination: `${apiBase}/:path*` }];
  }
};

export default nextConfig;
