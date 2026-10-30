import type { components, paths } from "@spotfinder/shared-types";
import createClient from "openapi-fetch";
import { API_URL } from "@/lib/env";

export type SpotSummary = components["schemas"]["SpotSummary"];
export type SpotDetail = components["schemas"]["SpotDetail"];
export type ModerationItem = components["schemas"]["ModerationItem"];
export type Tier = SpotSummary["display_tier"];
export type Category = SpotSummary["category"];

/** Typed client for browser code. Every path, parameter and response comes from the OpenAPI schema. */
export const api = createClient<paths>({ baseUrl: API_URL });

/** Typed client for server components, cached and revalidated by Next.js every `seconds`. */
export function createServerApi(seconds: number) {
  return createClient<paths>({
    baseUrl: API_URL,
    fetch: (request) => fetch(request, { next: { revalidate: seconds } }),
  });
}
