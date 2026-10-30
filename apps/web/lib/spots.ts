import { cache } from "react";
import { createServerApi } from "@/lib/api";

/** How long a spot page is cached. Must match `revalidate` in the spot page and its image route. */
export const SPOT_REVALIDATE_SECONDS = 300;

/** One API call per render, shared by the page, its metadata and its preview image. */
export const loadSpot = cache(async (slug: string) => {
  const { data, response } = await createServerApi(SPOT_REVALIDATE_SECONDS).GET("/api/spots/{slug}", {
    params: { path: { slug } },
  });
  if (response.status === 404 || response.status === 422) return null;
  if (!data) throw new Error(`Could not load spot (status ${response.status})`);
  return data;
});
