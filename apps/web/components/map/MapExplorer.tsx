"use client";

import dynamic from "next/dynamic";
import Link from "next/link";
import { useCallback, useEffect, useState, useSyncExternalStore } from "react";
import { TierMark } from "@/components/spots/SafetyBadge";
import { Field, controlClass, secondaryButtonClass } from "@/components/ui/Field";
import { api, type SpotSummary, type Tier } from "@/lib/api";
import { MAPBOX_TOKEN } from "@/lib/env";
import { nigeriaStaticMapUrl } from "@/lib/mapbox";
import { TIER_FILTER_LABELS, CATEGORY_OPTIONS, STATE_OPTIONS, TIER_OPTIONS } from "@/lib/utils";
import { TIERS } from "@spotfinder/shared-types";

// The map library is large, so it loads after the page is interactive and never on the server.
const MapView = dynamic(() => import("@/components/map/MapView"), {
  ssr: false,
  loading: () => <div className="h-full w-full bg-line/40" aria-hidden="true" />,
});

const VIEWPORT_LIMIT = 100;
const LOADED_KEY = "spotfinder:map-loaded";

const subscribeNever = () => () => {};
function wasMapLoaded(): boolean {
  try {
    return sessionStorage.getItem(LOADED_KEY) === "1";
  } catch {
    return false;
  }
}

/**
 * The interactive map is about 500 KB of JavaScript, which is the single biggest cost on a slow
 * phone. Until someone asks for it the page shows a static image, so it paints and responds at
 * once. Within a browsing session the map then loads straight away on later visits.
 */
function MapFacade({ token, onOpen }: { token: string; onOpen: () => void }) {
  return (
    <button type="button" onClick={onOpen} className="group absolute inset-0 block h-full w-full cursor-pointer">
      {/* A remote map image with fixed dimensions; the image optimizer adds nothing here. */}
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img
        src={nigeriaStaticMapUrl(token, 1)}
        srcSet={`${nigeriaStaticMapUrl(token, 1)} 1x, ${nigeriaStaticMapUrl(token, 2)} 2x`}
        width={800}
        height={600}
        alt=""
        fetchPriority="high"
        className="h-full w-full object-cover"
      />
      <span className="absolute bottom-6 left-1/2 -translate-x-1/2 rounded-md bg-ink px-5 py-3 text-base font-semibold text-white group-hover:bg-[#2b3480]">
        Explore the map
      </span>
    </button>
  );
}

interface Filters {
  state: string;
  category: string;
  tier: string;
}

type Status = "loading" | "ready" | "error";

interface Outcome {
  key: string;
  spots: readonly SpotSummary[];
  total: number;
  ok: boolean;
}

export function MapExplorer() {
  const [filters, setFilters] = useState<Filters>({ state: "", category: "", tier: "" });
  const [bbox, setBbox] = useState<string | null>(null);
  const [outcome, setOutcome] = useState<Outcome | null>(null);
  const [attempt, setAttempt] = useState(0);
  const [shown, setShown] = useState<{ spots: readonly SpotSummary[]; total: number }>({ spots: [], total: 0 });

  const [opened, setOpened] = useState(false);
  const [panelOpen, setPanelOpen] = useState(false);
  const remembered = useSyncExternalStore(subscribeNever, wasMapLoaded, () => false);
  const mapActive = opened || remembered;

  const openMap = useCallback(() => {
    setOpened(true);
    try {
      sessionStorage.setItem(LOADED_KEY, "1");
    } catch {
      // Storage can be unavailable (private mode); the map still opens.
    }
  }, []);

  const onViewportChange = useCallback((next: string) => setBbox(next), []);

  // One key identifies a request. Status is derived from whether the latest request has finished,
  // so a slow earlier response can never be mistaken for the current one.
  const requestKey = bbox === null ? null : `${bbox}|${filters.state}|${filters.category}|${filters.tier}|${attempt}`;
  const status: Status = outcome === null || outcome.key !== requestKey ? "loading" : outcome.ok ? "ready" : "error";
  const spots = shown.spots;
  const total = shown.total;

  useEffect(() => {
    if (bbox === null || requestKey === null) return;
    const controller = new AbortController();
    const query: Record<string, string | number> = { bbox, limit: VIEWPORT_LIMIT };
    if (filters.state) query.state = filters.state;
    if (filters.category) query.category = filters.category;
    if (filters.tier) query.safety_tier = filters.tier;

    api
      .GET("/api/spots", { params: { query }, signal: controller.signal })
      .then(({ data }) => {
        if (controller.signal.aborted) return;
        if (data) {
          setShown({ spots: data.items, total: data.total });
          setOutcome({ key: requestKey, spots: data.items, total: data.total, ok: true });
        } else {
          setOutcome({ key: requestKey, spots: [], total: 0, ok: false });
        }
      })
      .catch(() => {
        if (!controller.signal.aborted) setOutcome({ key: requestKey, spots: [], total: 0, ok: false });
      });
    // A newer viewport or filter change cancels the request still in flight.
    return () => controller.abort();
  }, [bbox, filters, requestKey]);

  const update = (key: keyof Filters) => (event: React.ChangeEvent<HTMLSelectElement>) =>
    setFilters((current) => ({ ...current, [key]: event.target.value }));

  const filterPanel = (
    <div className="flex flex-col gap-4">
      <Field label="State" htmlFor="map-state">
        <select id="map-state" value={filters.state} onChange={update("state")} className={controlClass}>
          <option value="">All states</option>
          {STATE_OPTIONS.map((o) => (
            <option key={o.value} value={o.value}>
              {o.label}
            </option>
          ))}
        </select>
      </Field>
      <Field label="Category" htmlFor="map-category">
        <select id="map-category" value={filters.category} onChange={update("category")} className={controlClass}>
          <option value="">All categories</option>
          {CATEGORY_OPTIONS.map((o) => (
            <option key={o.value} value={o.value}>
              {o.label}
            </option>
          ))}
        </select>
      </Field>
      <Field label="Safety reports" htmlFor="map-tier">
        <select id="map-tier" value={filters.tier} onChange={update("tier")} className={controlClass}>
          <option value="">Any</option>
          {TIER_OPTIONS.map((o) => (
            <option key={o.value} value={o.value}>
              {o.label}
            </option>
          ))}
        </select>
      </Field>
    </div>
  );

  const legend = (
    <ul className="flex flex-col gap-2" aria-label="Marker key">
      {TIERS.map((tier: Tier) => (
        <li key={tier}>
          <TierMark tier={tier} label={TIER_FILTER_LABELS[tier]} />
        </li>
      ))}
    </ul>
  );

  return (
    <div className="flex flex-col lg:flex-row" style={{ height: "calc(100dvh - var(--header-h))" }}>
      <aside className="border-b border-line bg-surface p-4 lg:w-72 lg:shrink-0 lg:overflow-y-auto lg:border-b-0 lg:border-r">
        <button
          type="button"
          aria-expanded={panelOpen}
          aria-controls="map-filters"
          onClick={() => setPanelOpen((open) => !open)}
          className="font-semibold underline lg:hidden"
        >
          Filters and key
        </button>
        {/* One panel for every screen size: always shown on large screens, toggled on small ones. */}
        <div id="map-filters" className={`${panelOpen ? "mt-4 flex" : "hidden"} flex-col gap-8 lg:mt-0 lg:flex`}>
          {filterPanel}
          {legend}
        </div>
      </aside>

      <section className="relative min-h-0 flex-1" aria-label="Map">
        {MAPBOX_TOKEN ? (
          mapActive ? (
            <MapView token={MAPBOX_TOKEN} spots={spots} onViewportChange={onViewportChange} />
          ) : (
            <MapFacade token={MAPBOX_TOKEN} onOpen={openMap} />
          )
        ) : (
          <div className="flex h-full flex-col items-center justify-center gap-3 p-6 text-center">
            <p>The map is not configured.</p>
            <Link href="/spots" className={secondaryButtonClass}>
              Browse the list
            </Link>
          </div>
        )}
        {MAPBOX_TOKEN && mapActive && (
          <div
            role="status"
            className="absolute bottom-6 left-3 flex items-center gap-3 rounded-md border border-line bg-surface px-3 py-2 text-sm font-semibold"
          >
            {status === "loading" && <span>Loading spots</span>}
            {status === "ready" && (
              <span>
                {total > spots.length ? `Showing ${spots.length} of ${total} spots` : `${total} ${total === 1 ? "spot" : "spots"} in view`}
              </span>
            )}
            {status === "error" && (
              <>
                <span>Could not load spots</span>
                <button type="button" className="underline" onClick={() => setAttempt((n) => n + 1)}>
                  Try again
                </button>
              </>
            )}
          </div>
        )}
      </section>
    </div>
  );
}
