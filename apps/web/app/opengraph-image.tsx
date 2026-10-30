import { ImageResponse } from "next/og";

export const alt = "Spotfinder: places across Nigeria with community safety reports";
export const size = { width: 1200, height: 630 };
export const contentType = "image/png";

export default function OpenGraphImage() {
  return new ImageResponse(
    (
      <div
        style={{
          width: "100%",
          height: "100%",
          display: "flex",
          flexDirection: "column",
          justifyContent: "center",
          padding: 80,
          background: "#1d2457",
          color: "#ffffff",
        }}
      >
        <div style={{ fontSize: 120, fontWeight: 700 }}>Spotfinder</div>
        <div style={{ fontSize: 44, marginTop: 24, maxWidth: 900 }}>
          Places across Nigeria, with community safety reports and cost estimates
        </div>
        <div style={{ display: "flex", gap: 20, marginTop: 56 }}>
          <div style={{ width: 36, height: 36, borderRadius: 18, background: "#4ade80" }} />
          <div style={{ width: 36, height: 36, background: "#fbbf24", transform: "rotate(45deg)" }} />
          <div style={{ width: 0, height: 0, borderLeft: "20px solid transparent", borderRight: "20px solid transparent", borderBottom: "38px solid #f87171" }} />
        </div>
      </div>
    ),
    size,
  );
}
