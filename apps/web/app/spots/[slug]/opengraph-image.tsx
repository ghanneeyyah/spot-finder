import { ImageResponse } from "next/og";
import { loadSpot } from "@/lib/spots";
import { TIER_COLORS, safetySummary } from "@/lib/safety";
import { CATEGORY_LABELS } from "@/lib/utils";

export const alt = "Spot preview";
export const size = { width: 1200, height: 630 };
export const contentType = "image/png";
export const revalidate = 300; // keep equal to SPOT_REVALIDATE_SECONDS in lib/spots.ts

// Only properties the image renderer supports: it rejects values such as `border: none`.
function markStyle(tier: string, color: string): Record<string, string | number> {
  const base = { width: 40, height: 40 };
  if (tier === "green") return { ...base, borderRadius: 20, background: color };
  if (tier === "yellow") return { ...base, background: color, transform: "rotate(45deg) scale(0.85)" };
  if (tier === "red") return { ...base, background: color, borderRadius: 4 };
  return { ...base, borderRadius: 20, borderWidth: 6, borderStyle: "dashed", borderColor: color };
}

function clip(text: string, max: number): string {
  return text.length <= max ? text : `${text.slice(0, max - 1).trimEnd()}…`;
}

export default async function SpotImage({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  // A preview must never fail: if the API is unreachable it falls back to the plain brand card.
  const spot = await loadSpot(slug).catch(() => null);
  const tier = spot && spot.safety_report_count > 0 ? spot.display_tier : "unverified";
  const { headline, basis } = spot ? safetySummary(spot.display_tier, spot.safety_report_count) : { headline: "", basis: null };
  const color = TIER_COLORS[tier];

  return new ImageResponse(
    (
      <div
        style={{
          width: "100%",
          height: "100%",
          display: "flex",
          flexDirection: "column",
          justifyContent: "space-between",
          padding: 72,
          background: "#1d2457",
          color: "#ffffff",
        }}
      >
        <div style={{ fontSize: 40, fontWeight: 700 }}>Spotfinder</div>
        <div style={{ display: "flex", flexDirection: "column" }}>
          <div style={{ fontSize: spot && spot.name.length > 28 ? 72 : 96, fontWeight: 700, lineHeight: 1.1 }}>
            {spot ? clip(spot.name, 60) : "Spot not found"}
          </div>
          {spot && (
            <div style={{ fontSize: 40, marginTop: 20, opacity: 0.9 }}>
              {`${spot.city}, ${spot.state}. ${CATEGORY_LABELS[spot.category]}`}
            </div>
          )}
        </div>
        {spot && (
          <div style={{ display: "flex", alignItems: "center", background: "#ffffff", color: "#1d2457", borderRadius: 16, padding: "24px 32px" }}>
            <div style={markStyle(tier, color)} />
            <div style={{ display: "flex", flexDirection: "column", marginLeft: 28 }}>
              <div style={{ fontSize: 40, fontWeight: 700 }}>{headline}</div>
              {basis && <div style={{ fontSize: 28, opacity: 0.8 }}>{basis}</div>}
            </div>
          </div>
        )}
      </div>
    ),
    size,
  );
}
