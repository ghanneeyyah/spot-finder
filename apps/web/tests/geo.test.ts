import { describe, expect, it } from "vitest";
import type { SpotSummary } from "@/lib/api";
import { NIGERIA_BOUNDS, toBboxParam, toFeatureCollection } from "@/lib/geo";

describe("toBboxParam", () => {
  it("orders values as min_lng,min_lat,max_lng,max_lat", () => {
    expect(toBboxParam([3.1, 6.2, 4.9, 7.4])).toBe("3.1,6.2,4.9,7.4");
  });

  it("clamps the world copies Mapbox reports when zoomed far out", () => {
    expect(toBboxParam([-250, -95, 400, 91])).toBe("-180,-90,180,90");
  });

  it("rounds to five decimals so the URL stays short and stable", () => {
    expect(toBboxParam([3.123456789, 6.987654321, 4.5, 7.5])).toBe("3.12346,6.98765,4.5,7.5");
  });

  it("widens a degenerate box instead of sending one the API rejects", () => {
    const [west, , east] = toBboxParam([3, 6, 3, 7]).split(",").map(Number);
    expect(west).toBeLessThan(east as number);
  });

  it("covers the whole country for the initial view", () => {
    expect(toBboxParam(NIGERIA_BOUNDS)).toBe("2.6,4.2,14.7,13.9");
  });
});

describe("toFeatureCollection", () => {
  const spot = {
    id: "1", slug: "olumo-rock", name: "Olumo Rock", category: "historical", state: "Ogun",
    city: "Abeokuta", latitude: 7.1517, longitude: 3.3405, display_tier: "green",
    safety_report_count: 4,
  } satisfies SpotSummary;

  it("puts longitude before latitude, as GeoJSON requires", () => {
    const [feature] = toFeatureCollection([spot]).features;
    expect(feature?.geometry.coordinates).toEqual([3.3405, 7.1517]);
  });

  it("carries only what the map needs", () => {
    const [feature] = toFeatureCollection([spot]).features;
    expect(feature?.properties).toEqual({ slug: "olumo-rock", name: "Olumo Rock", tier: "green", count: 4 });
  });
});
