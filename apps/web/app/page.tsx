import type { Metadata } from "next";
import { MapExplorer } from "@/components/map/MapExplorer";

export const metadata: Metadata = {
  title: { absolute: "Spotfinder: places across Nigeria" },
  alternates: { canonical: "/" },
};

export default function HomePage() {
  return (
    <>
      <h1 className="sr-only">Map of places across Nigeria</h1>
      <MapExplorer />
    </>
  );
}
