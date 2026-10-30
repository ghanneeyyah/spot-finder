// Next.js only inlines NEXT_PUBLIC_* variables when they are read as literal property accesses,
// so each one is read explicitly here, never through a dynamic key.
const API = process.env.NEXT_PUBLIC_API_URL;
const SITE = process.env.NEXT_PUBLIC_SITE_URL;
const MAPBOX = process.env.NEXT_PUBLIC_MAPBOX_TOKEN;

const isProduction = process.env.NODE_ENV === "production";

function requiredInProduction(name: string, value: string | undefined): string {
  if (value) return value;
  if (isProduction) throw new Error(`${name} must be set when building for production`);
  return "";
}

export const API_URL = (
  requiredInProduction("NEXT_PUBLIC_API_URL", API) || "http://localhost:8000"
).replace(/\/$/, "");

export const SITE_URL = (
  requiredInProduction("NEXT_PUBLIC_SITE_URL", SITE) || "http://localhost:3000"
).replace(/\/$/, "");

export const MAPBOX_TOKEN = requiredInProduction("NEXT_PUBLIC_MAPBOX_TOKEN", MAPBOX);

export const FIREBASE_CONFIG = {
  apiKey: process.env.NEXT_PUBLIC_FIREBASE_API_KEY ?? "",
  authDomain: process.env.NEXT_PUBLIC_FIREBASE_AUTH_DOMAIN ?? "",
  projectId: process.env.NEXT_PUBLIC_FIREBASE_PROJECT_ID ?? "",
  appId: process.env.NEXT_PUBLIC_FIREBASE_APP_ID ?? "",
};
