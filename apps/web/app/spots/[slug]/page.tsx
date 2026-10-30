import type { Metadata } from "next";
import Image from "next/image";
import { notFound } from "next/navigation";
import { StaticMap } from "@/components/map/StaticMap";
import { SafetyBadge } from "@/components/spots/SafetyBadge";
import { loadSpot } from "@/lib/spots";
import { CATEGORY_LABELS, humanize } from "@/lib/utils";

// Statically generated on first request, then served from cache and refreshed in the background
// every five minutes, so a new safety report shows up quickly. Nothing is built ahead of time, so 5 spots and 50,000 behave the same and the
// build never needs the API.
export const revalidate = 300; // keep equal to SPOT_REVALIDATE_SECONDS in lib/spots.ts
export const dynamicParams = true;
export function generateStaticParams(): { slug: string }[] {
  return [];
}

type Props = { params: Promise<{ slug: string }> };

function excerpt(text: string, max: number): string {
  return text.length <= max ? text : `${text.slice(0, max - 1).trimEnd()}…`;
}

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { slug } = await params;
  const spot = await loadSpot(slug);
  if (!spot) return { title: "Spot not found", robots: { index: false } };
  const description = spot.description
    ? excerpt(spot.description, 155)
    : `${spot.name} in ${spot.city}, ${spot.state}.`;
  return {
    title: spot.name,
    description,
    alternates: { canonical: `/spots/${spot.slug}` },
    openGraph: { title: spot.name, description, url: `/spots/${spot.slug}`, type: "website" },
    twitter: { card: "summary_large_image", title: spot.name, description },
  };
}

export default async function SpotPage({ params }: Props) {
  const { slug } = await params;
  const spot = await loadSpot(slug);
  if (!spot) notFound();

  const amenities = Object.entries(spot.amenities)
    .filter(([, available]) => available === true)
    .map(([key]) => humanize(key));

  return (
    <article className="mx-auto grid max-w-6xl gap-8 px-4 py-8 lg:grid-cols-[3fr_2fr]">
      <div className="flex flex-col gap-8">
        <header className="flex flex-col gap-2">
          <h1 className="font-serif text-4xl font-bold">{spot.name}</h1>
          <p className="text-lg text-muted">
            {spot.address ? `${spot.address}, ` : ""}
            {spot.city}, {spot.state}
          </p>
          <p>{CATEGORY_LABELS[spot.category]}</p>
        </header>

        <section aria-labelledby="safety" className="flex flex-col gap-2 rounded-lg border border-line bg-surface p-4">
          <h2 id="safety" className="font-serif text-xl font-semibold">
            Safety
          </h2>
          <SafetyBadge tier={spot.display_tier} count={spot.safety_report_count} withBasis />
          <p className="text-muted">Community opinion, not verified fact.</p>
        </section>

        {(spot.cost_estimate_text || spot.best_time) && (
          <section aria-labelledby="visit" className="flex flex-col gap-3">
            <h2 id="visit" className="font-serif text-xl font-semibold">
              Planning a visit
            </h2>
            <dl className="grid gap-3 sm:grid-cols-2">
              {spot.cost_estimate_text && (
                <div>
                  <dt className="font-semibold">Cost estimate</dt>
                  <dd>{spot.cost_estimate_text}</dd>
                </div>
              )}
              {spot.best_time && (
                <div>
                  <dt className="font-semibold">Best time to go</dt>
                  <dd>{spot.best_time}</dd>
                </div>
              )}
            </dl>
          </section>
        )}

        {spot.description && <p className="max-w-prose text-lg">{spot.description}</p>}

        {amenities.length > 0 && (
          <section aria-labelledby="amenities" className="flex flex-col gap-2">
            <h2 id="amenities" className="font-serif text-xl font-semibold">
              On site
            </h2>
            <ul className="flex flex-wrap gap-2">
              {amenities.map((label) => (
                <li key={label} className="rounded-md border border-line bg-surface px-3 py-1">
                  {label}
                </li>
              ))}
            </ul>
          </section>
        )}

        {spot.photos.length > 0 && (
          <section aria-labelledby="photos" className="flex flex-col gap-3">
            <h2 id="photos" className="font-serif text-xl font-semibold">
              Photos
            </h2>
            <ul className="grid grid-cols-2 gap-3 sm:grid-cols-3">
              {spot.photos.map((photo) => (
                <li key={photo.id}>
                  <Image
                    src={photo.url}
                    alt={`${spot.name}, shared by a visitor`}
                    width={480}
                    height={360}
                    unoptimized
                    loading="lazy"
                    className="aspect-[4/3] w-full rounded-md object-cover"
                  />
                </li>
              ))}
            </ul>
          </section>
        )}
      </div>

      <aside>
        <StaticMap name={spot.name} latitude={spot.latitude} longitude={spot.longitude} />
      </aside>
    </article>
  );
}
