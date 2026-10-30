import type { Metadata } from "next";
import Link from "next/link";
import { NIGERIAN_STATES } from "@spotfinder/shared-types";
import { SpotCard } from "@/components/spots/SpotCard";
import { SpotFilters } from "@/components/spots/SpotFilters";
import { createServerApi } from "@/lib/api";
import { isCategory, isTier, pickString, queryString } from "@/lib/utils";

export const metadata: Metadata = {
  title: "Spots",
  description: "Search places across Nigeria by state, category and community safety reports.",
  alternates: { canonical: "/spots" },
};

const PAGE_SIZE = 20;
const MAX_OFFSET = 100_000;

type SearchParams = Promise<Record<string, string | string[] | undefined>>;

export default async function SpotsPage({ searchParams }: { searchParams: SearchParams }) {
  const params = await searchParams;
  const q = pickString(params.q);
  const stateParam = pickString(params.state);
  const state = NIGERIAN_STATES.find((s) => s === stateParam);
  const categoryParam = pickString(params.category);
  const category = isCategory(categoryParam) ? categoryParam : undefined;
  const tierParam = pickString(params.safety_tier);
  const tier = isTier(tierParam) ? tierParam : undefined;
  const requested = Number.parseInt(pickString(params.offset) ?? "0", 10);
  const offset = Number.isFinite(requested) ? Math.min(Math.max(requested, 0), MAX_OFFSET) : 0;

  const query: Record<string, string | number> = { limit: PAGE_SIZE, offset };
  if (q) query.q = q;
  if (state) query.state = state;
  if (category) query.category = category;
  if (tier) query.safety_tier = tier;

  const filters = { q, state, category, safety_tier: tier };
  // An unreachable API is an expected failure here. The page is never cached, so it is shown on
  // the server as plain HTML instead of an error boundary that only draws after JavaScript loads.
  const data = await createServerApi(60)
    .GET("/api/spots", { params: { query } })
    .then((result) => result.data)
    .catch(() => undefined);
  if (!data) {
    return (
      <div className="mx-auto flex max-w-6xl flex-col gap-6 px-4 py-8">
        <h1 className="font-serif text-3xl font-bold">Spots</h1>
        <SpotFilters q={q} state={state} category={category} tier={tier} />
        <div className="flex flex-col items-start gap-3 py-8" role="alert">
          <p className="text-lg">The list could not be loaded. Check your connection and try again.</p>
          <Link href={`/spots${queryString({ ...filters, offset: offset || undefined })}`} className="font-semibold underline">
            Try again
          </Link>
        </div>
      </div>
    );
  }

  const previous = offset > 0 ? queryString({ ...filters, offset: Math.max(offset - PAGE_SIZE, 0) || undefined }) : null;
  const next = offset + data.items.length < data.total ? queryString({ ...filters, offset: offset + PAGE_SIZE }) : null;

  return (
    <div className="mx-auto flex max-w-6xl flex-col gap-6 px-4 py-8">
      <h1 className="font-serif text-3xl font-bold">Spots</h1>
      <SpotFilters q={q} state={state} category={category} tier={tier} />

      {data.items.length === 0 ? (
        <div className="flex flex-col items-start gap-3 py-8">
          <p className="text-lg">No spots match these filters.</p>
          <Link href="/spots" className="font-semibold underline">
            Clear filters
          </Link>
        </div>
      ) : (
        <>
          <p className="text-muted" role="status">
            {offset + 1} to {offset + data.items.length} of {data.total}
          </p>
          <ul className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {data.items.map((spot) => (
              <li key={spot.id}>
                <SpotCard spot={spot} />
              </li>
            ))}
          </ul>
          {(previous !== null || next !== null) && (
            <nav aria-label="Pages" className="flex items-center gap-6">
              {previous !== null && (
                <Link href={`/spots${previous}`} rel="prev" className="font-semibold underline">
                  Previous
                </Link>
              )}
              {next !== null && (
                <Link href={`/spots${next}`} rel="next" className="font-semibold underline">
                  Next
                </Link>
              )}
            </nav>
          )}
        </>
      )}
    </div>
  );
}
