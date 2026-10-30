import { NIGERIA_BOUNDS } from "@/lib/geo";

/** Static image of the whole country: one image request, no JavaScript. */
export function nigeriaStaticMapUrl(token: string, scale: 1 | 2): string {
  const [west, south, east, north] = NIGERIA_BOUNDS;
  const size = scale === 2 ? "800x600@2x" : "800x600";
  return `https://api.mapbox.com/styles/v1/mapbox/light-v11/static/[${west},${south},${east},${north}]/${size}?access_token=${encodeURIComponent(token)}`;
}
