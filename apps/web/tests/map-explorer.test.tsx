// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { Suspense, lazy, type ComponentType } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { MapExplorer } from "@/components/map/MapExplorer";
import { api } from "@/lib/api";

vi.mock("@/lib/env", () => ({ MAPBOX_TOKEN: "pk.test", API_URL: "http://api", SITE_URL: "http://site", FIREBASE_CONFIG: {} }));
vi.mock("@/lib/api", () => ({ api: { GET: vi.fn() } }));
// The real map needs WebGL. A stand-in lets the test observe when the module is requested.
const mapLoaded = vi.fn();
vi.mock("@/components/map/MapView", () => {
  mapLoaded();
  return {
    default: ({ onViewportChange }: { onViewportChange: (bbox: string) => void }) => (
      <button type="button" data-testid="map" onClick={() => onViewportChange("3,6,4,7")}>
        map
      </button>
    ),
  };
});
vi.mock("next/dynamic", () => ({
  default: (loader: () => Promise<{ default: ComponentType<Record<string, unknown>> }>) => {
    const Lazy = lazy(loader);
    return (props: Record<string, unknown>) => (
      <Suspense fallback={null}>
        <Lazy {...props} />
      </Suspense>
    );
  },
}));

const GET = vi.mocked(api.GET) as unknown as ReturnType<typeof vi.fn>;

beforeEach(() => {
  sessionStorage.clear();
  GET.mockResolvedValue({ data: { items: [], total: 0, limit: 100, offset: 0 } });
});
afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe("home page map", () => {
  it("paints a static map and does not start the interactive map or any API call", () => {
    render(<MapExplorer />);
    expect(screen.getByRole("button", { name: "Explore the map" })).toBeTruthy();
    expect(screen.queryByTestId("map")).toBeNull();
    expect(GET).not.toHaveBeenCalled();
    const image = document.querySelector("img");
    expect(image?.getAttribute("src")).toContain("api.mapbox.com/styles/v1/mapbox/light-v11/static/");
    expect(image?.getAttribute("width")).toBe("800");
  });

  it("loads the interactive map when asked, then fetches spots for the viewport", async () => {
    render(<MapExplorer />);
    fireEvent.click(screen.getByRole("button", { name: "Explore the map" }));
    fireEvent.click(await screen.findByTestId("map"));
    await waitFor(() => expect(GET).toHaveBeenCalled());
    expect(GET).toHaveBeenCalledWith("/api/spots", expect.objectContaining({ params: { query: { bbox: "3,6,4,7", limit: 100 } } }));
    expect(sessionStorage.getItem("spotfinder:map-loaded")).toBe("1");
    expect(await screen.findByText("0 spots in view")).toBeTruthy();
  });

  it("has exactly one filter panel, so no element id appears twice", () => {
    render(<MapExplorer />);
    const ids = [...document.querySelectorAll("[id]")].map((el) => el.id);
    expect(new Set(ids).size).toBe(ids.length);
    const toggle = screen.getByRole("button", { name: "Filters and key" });
    expect(toggle.getAttribute("aria-expanded")).toBe("false");
    fireEvent.click(toggle);
    expect(toggle.getAttribute("aria-expanded")).toBe("true");
  });

  it("opens the map straight away when it was opened earlier in the session", async () => {
    sessionStorage.setItem("spotfinder:map-loaded", "1");
    render(<MapExplorer />);
    expect(await screen.findByTestId("map")).toBeTruthy();
    expect(screen.queryByRole("button", { name: "Explore the map" })).toBeNull();
  });

  it("sends the chosen filters with the viewport request", async () => {
    sessionStorage.setItem("spotfinder:map-loaded", "1");
    render(<MapExplorer />);
    fireEvent.click(await screen.findByTestId("map"));
    await waitFor(() => expect(GET).toHaveBeenCalledTimes(1));
    fireEvent.change(screen.getByLabelText("Category"), { target: { value: "beach" } });
    await waitFor(() => expect(GET).toHaveBeenCalledTimes(2));
    expect(GET).toHaveBeenLastCalledWith("/api/spots", expect.objectContaining({ params: { query: { bbox: "3,6,4,7", limit: 100, category: "beach" } } }));
  });

  it("offers a retry when spots cannot be loaded", async () => {
    sessionStorage.setItem("spotfinder:map-loaded", "1");
    GET.mockRejectedValue(new Error("network"));
    render(<MapExplorer />);
    fireEvent.click(await screen.findByTestId("map"));
    expect(await screen.findByText("Could not load spots")).toBeTruthy();
    GET.mockResolvedValue({ data: { items: [], total: 0, limit: 100, offset: 0 } });
    fireEvent.click(screen.getByRole("button", { name: "Try again" }));
    expect(await screen.findByText("0 spots in view")).toBeTruthy();
  });
});
