import type { NextConfig } from "next";

// The browser only talks to this app. /api/* is forwarded to the route API, which holds
// the OneMap token; nothing else is forwarded.
const apiUrl = process.env.API_URL ?? "http://127.0.0.1:8000";

const nextConfig: NextConfig = {
  async rewrites() {
    return [{ source: "/api/:path*", destination: `${apiUrl}/api/:path*` }];
  },
};

export default nextConfig;
