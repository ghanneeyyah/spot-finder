import type { Tier } from "@/lib/api";

export const TIER_COLORS: Record<Tier, string> = {
  green: "#15803d",
  yellow: "#b45309",
  red: "#b91c1c",
  unverified: "#64748b",
};

const HEADLINES: Record<Tier, string> = {
  green: "Reports lean safe",
  yellow: "Reports are mixed",
  red: "Reports raise concerns",
  unverified: "No community reports yet",
};

export function reportCountText(count: number): string {
  return `Based on ${count} community ${count === 1 ? "report" : "reports"}`;
}

/** Safety is always community sentiment, and a tier is only shown once reports back it. */
export function safetySummary(tier: Tier, count: number): { headline: string; basis: string | null } {
  if (count <= 0 || tier === "unverified") {
    return { headline: HEADLINES.unverified, basis: null };
  }
  return { headline: HEADLINES[tier], basis: reportCountText(count) };
}

export function effectiveTier(tier: Tier, count: number): Tier {
  return count > 0 ? tier : "unverified";
}
