import Image from "next/image";
import { MAPBOX_TOKEN } from "@/lib/env";

interface Props {
  name: string;
  latitude: number;
  longitude: number;
}

/**
 * A map image with no JavaScript: it costs one request and keeps the spot page fast on a cheap
 * phone. The interactive map lives on the home page.
 */
export function StaticMap({ name, latitude, longitude }: Props) {
  const center = `${longitude},${latitude}`;
  const directions = `https://www.google.com/maps/search/?api=1&query=${latitude},${longitude}`;
  const src = `https://api.mapbox.com/styles/v1/mapbox/light-v11/static/pin-l+1d2457(${center})/${center},13,0/640x400@2x?access_token=${encodeURIComponent(MAPBOX_TOKEN)}`;
  return (
    <div className="flex flex-col gap-3">
      {MAPBOX_TOKEN && (
        <Image
          src={src}
          alt={`Map showing the location of ${name}`}
          width={640}
          height={400}
          unoptimized
          className="h-auto w-full rounded-lg border border-line"
        />
      )}
      <a href={directions} target="_blank" rel="noopener noreferrer" className="font-semibold underline">
        Get directions
      </a>
    </div>
  );
}
