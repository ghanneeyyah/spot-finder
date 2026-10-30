"use client";

import mapboxgl from "mapbox-gl";
import "mapbox-gl/dist/mapbox-gl.css";
import { useEffect, useRef, useState } from "react";
import type { SpotSummary } from "@/lib/api";
import { NIGERIA_BOUNDS, toBboxParam, toFeatureCollection, type SpotProperties } from "@/lib/geo";
import { TIER_COLORS, safetySummary } from "@/lib/safety";

const SOURCE = "spots";
const MOVE_DEBOUNCE_MS = 250;

interface Props {
  token: string;
  spots: readonly SpotSummary[];
  onViewportChange: (bbox: string) => void;
}

/** Popup content is built with DOM nodes and textContent, so spot names can never inject markup. */
function popupContent({ slug, name, tier, count }: SpotProperties): HTMLElement {
  const root = document.createElement("div");
  root.style.cssText = "font-family:inherit;color:#1d2457;padding:2px 0";
  const link = document.createElement("a");
  link.href = `/spots/${encodeURIComponent(slug)}`;
  link.textContent = name;
  link.style.cssText = "font-weight:700;font-size:15px;text-decoration:underline;color:#1d2457";
  const { headline, basis } = safetySummary(tier, count);
  const line = document.createElement("p");
  line.style.cssText = "margin:4px 0 0;font-size:13px";
  line.textContent = basis ? `${headline}. ${basis}.` : headline;
  root.append(link, line);
  return root;
}

export default function MapView({ token, spots, onViewportChange }: Props) {
  const container = useRef<HTMLDivElement>(null);
  const mapRef = useRef<mapboxgl.Map | null>(null);
  const viewportCallback = useRef(onViewportChange);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    viewportCallback.current = onViewportChange;
  }, [onViewportChange]);

  useEffect(() => {
    if (!container.current) return;
    mapboxgl.accessToken = token;
    const map = new mapboxgl.Map({
      container: container.current,
      style: "mapbox://styles/mapbox/light-v11",
      bounds: [
        [NIGERIA_BOUNDS[0], NIGERIA_BOUNDS[1]],
        [NIGERIA_BOUNDS[2], NIGERIA_BOUNDS[3]],
      ],
      fitBoundsOptions: { padding: 16 },
    });
    mapRef.current = map;
    map.addControl(new mapboxgl.NavigationControl({ showCompass: false }), "top-right");

    let timer: ReturnType<typeof setTimeout> | undefined;
    const emitViewport = () => {
      const bounds = map.getBounds();
      if (!bounds) return;
      viewportCallback.current(
        toBboxParam([bounds.getWest(), bounds.getSouth(), bounds.getEast(), bounds.getNorth()]),
      );
    };

    map.on("load", () => {
      // The API returns at most 100 spots per viewport; clustering keeps them legible at any zoom.
      map.addSource(SOURCE, {
        type: "geojson",
        data: toFeatureCollection([]),
        cluster: true,
        clusterMaxZoom: 12,
        clusterRadius: 50,
      });
      map.addLayer({
        id: "clusters",
        type: "circle",
        source: SOURCE,
        filter: ["has", "point_count"],
        paint: {
          "circle-color": "#1d2457",
          "circle-radius": ["step", ["get", "point_count"], 16, 10, 20, 30, 26],
          "circle-stroke-width": 2,
          "circle-stroke-color": "#ffffff",
        },
      });
      map.addLayer({
        id: "cluster-count",
        type: "symbol",
        source: SOURCE,
        filter: ["has", "point_count"],
        layout: {
          "text-field": ["get", "point_count_abbreviated"],
          "text-size": 13,
          "text-font": ["DIN Pro Medium", "Arial Unicode MS Bold"],
        },
        paint: { "text-color": "#ffffff" },
      });
      map.addLayer({
        id: "spot-points",
        type: "circle",
        source: SOURCE,
        filter: ["!", ["has", "point_count"]],
        paint: {
          "circle-color": [
            "match",
            ["get", "tier"],
            "green", TIER_COLORS.green,
            "yellow", TIER_COLORS.yellow,
            "red", TIER_COLORS.red,
            TIER_COLORS.unverified,
          ],
          "circle-radius": 9,
          "circle-stroke-width": 2.5,
          "circle-stroke-color": "#ffffff",
        },
      });

      map.on("click", "clusters", (event) => {
        const feature = map.queryRenderedFeatures(event.point, { layers: ["clusters"] })[0];
        const clusterId = feature?.properties?.cluster_id as number | undefined;
        const source = map.getSource(SOURCE) as mapboxgl.GeoJSONSource | undefined;
        if (clusterId === undefined || !source || feature?.geometry.type !== "Point") return;
        const center = feature.geometry.coordinates as [number, number];
        source.getClusterExpansionZoom(clusterId, (error, zoom) => {
          if (!error && zoom != null) map.easeTo({ center, zoom });
        });
      });

      map.on("click", "spot-points", (event) => {
        const feature = event.features?.[0];
        if (!feature || feature.geometry.type !== "Point") return;
        new mapboxgl.Popup({ maxWidth: "260px" })
          .setLngLat(feature.geometry.coordinates as [number, number])
          .setDOMContent(popupContent(feature.properties as SpotProperties))
          .addTo(map);
      });

      for (const layer of ["clusters", "spot-points"]) {
        map.on("mouseenter", layer, () => (map.getCanvas().style.cursor = "pointer"));
        map.on("mouseleave", layer, () => (map.getCanvas().style.cursor = ""));
      }

      map.on("moveend", () => {
        clearTimeout(timer);
        timer = setTimeout(emitViewport, MOVE_DEBOUNCE_MS);
      });
      setReady(true);
      emitViewport();
    });

    return () => {
      clearTimeout(timer);
      map.remove();
      mapRef.current = null;
      setReady(false);
    };
  }, [token]);

  useEffect(() => {
    if (!ready) return;
    const source = mapRef.current?.getSource(SOURCE) as mapboxgl.GeoJSONSource | undefined;
    source?.setData(toFeatureCollection(spots));
  }, [spots, ready]);

  return <div ref={container} className="h-full w-full" role="application" aria-label="Map of spots" />;
}
