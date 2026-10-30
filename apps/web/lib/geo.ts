import type { SpotSummary } from "@/lib/api";

/** [west, south, east, north] */
export type Bounds = readonly [number, number, number, number];

export const NIGERIA_BOUNDS: Bounds = [2.6, 4.2, 14.7, 13.9];

const round = (n: number) => Math.round(n * 1e5) / 1e5;
const clamp = (n: number, min: number, max: number) => Math.min(max, Math.max(min, n));

/**
 * Format map bounds as the API's bbox parameter (min_lng,min_lat,max_lng,max_lat). Zoomed far
 * out, Mapbox reports longitudes beyond +-180 for repeated world copies; the API rejects those.
 */
export function toBboxParam([west, south, east, north]: Bounds): string {
  const minLng = clamp(west, -180, 180);
  const maxLng = clamp(east, -180, 180);
  const minLat = clamp(south, -90, 90);
  const maxLat = clamp(north, -90, 90);
  // A degenerate box (min equal to max) is rejected by the API, so widen it slightly.
  const w = minLng < maxLng ? minLng : clamp(minLng - 0.001, -180, 180);
  const s = minLat < maxLat ? minLat : clamp(minLat - 0.001, -90, 90);
  return [w, s, maxLng, maxLat].map(round).join(",");
}

export interface SpotProperties {
  slug: string;
  name: string;
  tier: SpotSummary["display_tier"];
  count: number;
}

export function toFeatureCollection(spots: readonly SpotSummary[]) {
  return {
    type: "FeatureCollection" as const,
    features: spots.map((spot) => ({
      type: "Feature" as const,
      // GeoJSON order is [longitude, latitude].
      geometry: { type: "Point" as const, coordinates: [spot.longitude, spot.latitude] },
      properties: {
        slug: spot.slug,
        name: spot.name,
        tier: spot.display_tier,
        count: spot.safety_report_count,
      } satisfies SpotProperties,
    })),
  };
}
