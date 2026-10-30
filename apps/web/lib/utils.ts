import { CATEGORIES, TIERS } from "@spotfinder/shared-types";
import type { Category, Tier } from "@/lib/api";

export const CATEGORY_LABELS: Record<Category, string> = {
  nature: "Nature",
  food: "Food",
  historical: "Historical",
  hangout: "Hangout",
  beach: "Beach",
  park: "Park",
  other: "Other",
};

export const TIER_FILTER_LABELS: Record<Tier, string> = {
  green: "Reports lean safe",
  yellow: "Reports are mixed",
  red: "Reports raise concerns",
  unverified: "No community reports yet",
};

export function isCategory(value: string | undefined): value is Category {
  return value !== undefined && (CATEGORIES as readonly string[]).includes(value);
}

export function isTier(value: string | undefined): value is Tier {
  return value !== undefined && (TIERS as readonly string[]).includes(value);
}

export function humanize(key: string): string {
  const text = key.replace(/_/g, " ");
  return text.charAt(0).toUpperCase() + text.slice(1);
}

/** Build a query string, leaving out empty values. */
export function queryString(params: Record<string, string | number | undefined>): string {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== "") search.set(key, String(value));
  }
  const text = search.toString();
  return text ? `?${text}` : "";
}

export function pickString(value: string | string[] | undefined): string | undefined {
  const first = Array.isArray(value) ? value[0] : value;
  const trimmed = first?.trim();
  return trimmed ? trimmed.slice(0, 80) : undefined;
}

import { NIGERIAN_STATES } from "@spotfinder/shared-types";

export const STATE_OPTIONS = NIGERIAN_STATES.map((value) => ({ value, label: value }));
export const CATEGORY_OPTIONS = CATEGORIES.map((value) => ({ value, label: CATEGORY_LABELS[value] }));
export const TIER_OPTIONS = TIERS.map((value) => ({ value, label: TIER_FILTER_LABELS[value] }));
