import type { Tier } from "@/lib/api";
import { TIER_COLORS, safetySummary } from "@/lib/safety";

// Each tier has its own shape as well as its own color, so the badge never depends on color alone.
function Glyph({ tier }: { tier: Tier }) {
  const color = TIER_COLORS[tier];
  return (
    <svg width="16" height="16" viewBox="0 0 16 16" aria-hidden="true" className="shrink-0">
      {tier === "green" && <circle cx="8" cy="8" r="6.5" fill={color} />}
      {tier === "yellow" && <path d="M8 1 15 8 8 15 1 8Z" fill={color} />}
      {tier === "red" && <path d="M8 1.5 15.5 14.5H.5Z" fill={color} />}
      {tier === "unverified" && (
        <circle cx="8" cy="8" r="5.5" fill="none" stroke={color} strokeWidth="2" strokeDasharray="3 2" />
      )}
    </svg>
  );
}

export function TierMark({ tier, label }: { tier: Tier; label: string }) {
  return (
    <span className="inline-flex items-center gap-2 font-semibold">
      <Glyph tier={tier} />
      {label}
    </span>
  );
}

/** Safety as community sentiment. A tier appears only when reports back it. */
export function SafetyBadge({ tier, count, withBasis = false }: { tier: Tier; count: number; withBasis?: boolean }) {
  const { headline, basis } = safetySummary(tier, count);
  const shown: Tier = count > 0 ? tier : "unverified";
  return (
    <span className="inline-flex flex-col">
      <TierMark tier={shown} label={headline} />
      {withBasis && basis && <span className="pl-6 text-sm text-muted">{basis}</span>}
    </span>
  );
}
