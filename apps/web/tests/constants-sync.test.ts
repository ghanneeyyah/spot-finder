import { readFileSync } from "node:fs";
import path from "node:path";
import { CATEGORIES, NIGERIAN_STATES, TIERS } from "@spotfinder/shared-types";
import { describe, expect, it } from "vitest";

const root = path.join(import.meta.dirname, "../../..");

describe("constants stay in sync with the API", () => {
  it("states match NIGERIAN_STATES in the Python schema", () => {
    const source = readFileSync(path.join(root, "apps/api/app/schemas/spot.py"), "utf8");
    const block = /NIGERIAN_STATES = \(([\s\S]*?)\)\s*#/.exec(source)?.[1] ?? "";
    const python = [...block.matchAll(/"([^"]+)"/g)].map((m) => m[1]);
    expect(python.length).toBe(37);
    expect([...NIGERIAN_STATES]).toEqual(python);
  });

  it("categories and tiers match the OpenAPI enums", () => {
    const schema = JSON.parse(readFileSync(path.join(root, "packages/shared-types/openapi.json"), "utf8"));
    const summary = schema.components.schemas.SpotSummary.properties;
    expect([...CATEGORIES].sort()).toEqual([...summary.category.enum].sort());
    expect([...TIERS].sort()).toEqual([...summary.display_tier.enum].sort());
  });
});

describe("cache lifetimes agree", () => {
  it("the spot page and its image use SPOT_REVALIDATE_SECONDS", () => {
    const lib = readFileSync(path.join(root, "apps/web/lib/spots.ts"), "utf8");
    const seconds = /SPOT_REVALIDATE_SECONDS = (\d+)/.exec(lib)?.[1];
    for (const file of ["page.tsx", "opengraph-image.tsx"]) {
      const source = readFileSync(path.join(root, "apps/web/app/spots/[slug]", file), "utf8");
      expect(/export const revalidate = (\d+)/.exec(source)?.[1], file).toBe(seconds);
    }
  });
});
