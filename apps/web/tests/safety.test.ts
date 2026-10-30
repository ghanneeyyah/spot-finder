import { describe, expect, it } from "vitest";
import { effectiveTier, reportCountText, safetySummary } from "@/lib/safety";

describe("safetySummary", () => {
  it("shows no tier and no basis when there are no reports, whatever the stored tier says", () => {
    expect(safetySummary("green", 0)).toEqual({ headline: "No community reports yet", basis: null });
    expect(safetySummary("red", 0).basis).toBeNull();
    expect(effectiveTier("green", 0)).toBe("unverified");
  });

  it("states safety as community sentiment with the report count", () => {
    expect(safetySummary("green", 12)).toEqual({
      headline: "Reports lean safe",
      basis: "Based on 12 community reports",
    });
    expect(safetySummary("yellow", 3).headline).toBe("Reports are mixed");
    expect(safetySummary("red", 2).headline).toBe("Reports raise concerns");
  });

  it("never phrases a tier as a fact about the place", () => {
    for (const tier of ["green", "yellow", "red"] as const) {
      expect(safetySummary(tier, 5).headline).toMatch(/^Reports /);
    }
  });

  it("uses the singular for one report", () => {
    expect(reportCountText(1)).toBe("Based on 1 community report");
  });
});
