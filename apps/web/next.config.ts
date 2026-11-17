import path from "node:path";
import type { NextConfig } from "next";

// Temporarily hardcoding localhost for Docker testing. 
// Remove the localhost URLs before you deploy to Railway.
const cspHeader = `
  default-src 'self';
  script-src 'self' 'unsafe-eval' 'unsafe-inline' https://apis.google.com https://www.gstatic.com;
  style-src 'self' 'unsafe-inline' https://api.mapbox.com;
  img-src 'self' blob: data: https://res.cloudinary.com https://api.mapbox.com https://*.tiles.mapbox.com;
  font-src 'self';
  object-src 'none';
  base-uri 'self';
  form-action 'self';
  frame-ancestors 'none';
  worker-src 'self' blob:;
  connect-src 'self' http://localhost:8001 http://127.0.0.1:8001 https://api.mapbox.com https://events.mapbox.com https://securetoken.googleapis.com https://identitytoolkit.googleapis.com;
  frame-src https://*.firebaseapp.com https://accounts.google.com;
`.replace(/\s{2,}/g, " ").trim();

const config: NextConfig = {
  output: "standalone",
  outputFileTracingRoot: path.join(import.meta.dirname, "../.."),
  transpilePackages: ["@spotfinder/shared-types"],
  poweredByHeader: false,
  reactStrictMode: true,
  images: {
    remotePatterns: [{ protocol: "https", hostname: "res.cloudinary.com" }],
  },
  async headers() {
    return [
      {
        source: "/:path*",
        headers: [
          { key: "Content-Security-Policy", value: cspHeader },
          { key: "X-Content-Type-Options", value: "nosniff" },
          { key: "X-Frame-Options", value: "DENY" },
          { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
          { key: "Permissions-Policy", value: "camera=(), microphone=(), geolocation=(self)" },
        ],
      },
    ];
  },
};

export default config;