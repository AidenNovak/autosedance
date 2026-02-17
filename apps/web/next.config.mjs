/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  async rewrites() {
    // Best-practice for VM deploy: expose only the frontend, proxy /api to the backend
    // running on localhost (or any internal URL you configure).
    const raw =
      process.env.BACKEND_INTERNAL_URL ||
      process.env.NEXT_PUBLIC_BACKEND_URL ||
      "http://localhost:8000";
    const base = raw.replace(/\/+$/, "");
    return [
      {
        source: "/api/:path*",
        destination: `${base}/api/:path*`
      }
    ];
  }
};

export default nextConfig;
