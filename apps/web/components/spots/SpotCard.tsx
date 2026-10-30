import Link from "next/link";
import type { SpotSummary } from "@/lib/api";
import { CATEGORY_LABELS } from "@/lib/utils";
import { SafetyBadge } from "@/components/spots/SafetyBadge";

export function SpotCard({ spot }: { spot: SpotSummary }) {
  return (
    <Link
      href={`/spots/${spot.slug}`}
      // Spot pages are cached and fast to open. Prefetching every card would spend mobile data and
      // CPU on pages most visitors never open.
      prefetch={false}
      className="flex flex-col gap-3 rounded-lg border border-line bg-surface p-4 hover:border-ink"
    >
      <div>
        <h2 className="font-serif text-xl font-semibold">{spot.name}</h2>
        <p className="text-muted">
          {spot.city}, {spot.state}
        </p>
      </div>
      <p>{CATEGORY_LABELS[spot.category]}</p>
      <SafetyBadge tier={spot.display_tier} count={spot.safety_report_count} withBasis />
    </Link>
  );
}
