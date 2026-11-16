// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ModerationQueue } from "@/components/admin/ModerationQueue";
import { api } from "@/lib/api";
import { getIdToken, onAuthChange } from "@/lib/auth";

vi.mock("@/lib/auth", () => ({
  onAuthChange: vi.fn(),
  getIdToken: vi.fn(),
  signInWithGoogle: vi.fn(),
  signOutUser: vi.fn(),
}));
vi.mock("@/lib/api", () => ({ api: { GET: vi.fn(), PATCH: vi.fn() } }));

const GET = vi.mocked(api.GET) as unknown as ReturnType<typeof vi.fn>;
const PATCH = vi.mocked(api.PATCH) as unknown as ReturnType<typeof vi.fn>;

const spotItem = (over: Record<string, unknown> = {}) => ({
  kind: "spot",
  id: "spot-1",
  spot_id: "spot-1",
  spot_name: "Pending Spot",
  spot_slug: "pending-spot",
  submitter: "Alice",
  photo_url: null,
  spot: {
    category: "nature",
    state: "Ekiti",
    city: "Ikogosi",
    address: null,
    description: "Warm and cold springs side by side.",
    cost_estimate_text: "N2,000 per person",
    best_time: "Dry season",
    amenities: { parking: true, restrooms: false },
    latitude: 7.58,
    longitude: 4.98,
  },
  created_at: "2026-10-28T10:00:00Z",
  ...over,
});

const photoItem = {
  kind: "photo",
  id: "photo-1",
  spot_id: "spot-9",
  spot_name: "Live Spot",
  spot_slug: "live-spot",
  submitter: "Bob",
  photo_url: "https://res.cloudinary.com/x/y.jpg",
  spot: null,
  created_at: "2026-10-28T11:00:00Z",
};

const queue = (items: unknown[], total = items.length) => ({
  data: { items, total, limit: 20, offset: 0 },
  response: { status: 200, ok: true },
});
const status = (code: number) => ({ response: { status: code, ok: code < 300 } });

function signedInAs(email: string | null) {
  vi.mocked(onAuthChange).mockImplementation(async (callback) => {
    callback(email === null ? null : { email });
    return () => {};
  });
}

beforeEach(() => {
  vi.mocked(getIdToken).mockResolvedValue("id-token-123");
  signedInAs("mod@example.com");
});

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
  GET.mockReset();
  PATCH.mockReset();
});

describe("access", () => {
  it("asks anonymous visitors to sign in and never calls the API", async () => {
    signedInAs(null);
    render(<ModerationQueue />);
    expect(await screen.findByRole("button", { name: "Sign in with Google" })).toBeTruthy();
    expect(GET).not.toHaveBeenCalled();
  });

  it("shows a 403 view, and no queue data, when the API says the account is not a moderator", async () => {
    signedInAs("visitor@example.com");
    GET.mockResolvedValue(status(403));
    render(<ModerationQueue />);
    expect(await screen.findByText("403: no access")).toBeTruthy();
    expect(screen.getByText("visitor@example.com is not a moderator.")).toBeTruthy();
    expect(screen.queryByText("New spot")).toBeNull();
    expect(screen.queryByRole("button", { name: /Approve/ })).toBeNull();
    expect(PATCH).not.toHaveBeenCalled();
  });

  it("sends the Firebase ID token to the API as a bearer token", async () => {
    GET.mockResolvedValue(status(403));
    render(<ModerationQueue />);
    await screen.findByText("403: no access");
    expect(GET).toHaveBeenCalledWith("/api/admin/moderation-queue", {
      params: { query: { limit: 20, offset: 0 } },
      headers: { Authorization: "Bearer id-token-123" },
    });
  });

  it("returns to the sign-in view when the API rejects the token", async () => {
    GET.mockResolvedValue(status(401));
    render(<ModerationQueue />);
    expect(await screen.findByRole("button", { name: "Sign in with Google" })).toBeTruthy();
  });

  it("offers a retry when the API fails", async () => {
    GET.mockResolvedValue(status(503));
    render(<ModerationQueue />);
    expect(await screen.findByText("The queue could not be loaded.")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Try again" }));
    await waitFor(() => expect(GET).toHaveBeenCalledTimes(2));
  });

  it("explains when sign-in is not configured", async () => {
    vi.mocked(onAuthChange).mockRejectedValue(new Error("Sign-in is not configured."));
    render(<ModerationQueue />);
    expect(await screen.findByText("Sign-in is not configured for this site.")).toBeTruthy();
  });
});

describe("queue contents", () => {
  it("shows the submitter, the Lagos-time date, the spot details and the actions", async () => {
    GET.mockResolvedValue(queue([spotItem(), photoItem]));
    render(<ModerationQueue />);
    const card = await screen.findByRole("article", { name: "Pending Spot" });
    expect(within(card).getByText("New spot")).toBeTruthy();
    expect(within(card).getByText(/Submitted by Alice on 28 Oct 2026, 11:00/)).toBeTruthy();
    expect(within(card).getByText("Ikogosi, Ekiti")).toBeTruthy();
    expect(within(card).getByText("N2,000 per person")).toBeTruthy();
    expect(within(card).getByText("Parking")).toBeTruthy();
    expect(within(card).queryByText(/Restrooms/)).toBeNull();
    expect(within(card).getByRole("button", { name: "Approve Pending Spot" })).toBeTruthy();
    expect(within(card).getByRole("button", { name: "Reject Pending Spot" })).toBeTruthy();

    const photo = screen.getByRole("article", { name: "Live Spot" });
    expect(within(photo).getByText("New photo")).toBeTruthy();
    expect(within(photo).getByRole("img").getAttribute("src")).toBe("https://res.cloudinary.com/x/y.jpg");
    expect(within(photo).getByRole("link", { name: "Open the spot page" }).getAttribute("href")).toBe(
      "/spots/live-spot",
    );
    expect(screen.getByText("1 to 2 of 2")).toBeTruthy();
  });

  it("says so when the queue is empty", async () => {
    GET.mockResolvedValue(queue([]));
    render(<ModerationQueue />);
    expect(await screen.findByText("Nothing is waiting for review.")).toBeTruthy();
  });
});

describe("decisions", () => {
  it("approves a spot and removes it from the queue", async () => {
    GET.mockResolvedValue(queue([spotItem(), photoItem]));
    PATCH.mockResolvedValue(status(200));
    render(<ModerationQueue />);
    fireEvent.click(await screen.findByRole("button", { name: "Approve Pending Spot" }));

    expect(await screen.findByText("Approved Pending Spot.")).toBeTruthy();
    expect(PATCH).toHaveBeenCalledWith("/api/spots/{spot_id}", {
      params: { path: { spot_id: "spot-1" } },
      body: { decision: "approve" },
      headers: { Authorization: "Bearer id-token-123" },
    });
    expect(screen.queryByRole("article", { name: "Pending Spot" })).toBeNull();
    expect(screen.getByRole("article", { name: "Live Spot" })).toBeTruthy();
    expect(screen.getByText("1 to 1 of 1")).toBeTruthy();
  });

  it("will not reject without a reason", async () => {
    GET.mockResolvedValue(queue([spotItem()]));
    render(<ModerationQueue />);
    fireEvent.click(await screen.findByRole("button", { name: "Reject Pending Spot" }));

    const confirm = screen.getByRole("button", { name: "Confirm rejection" }) as HTMLButtonElement;
    expect(confirm.disabled).toBe(true);
    fireEvent.change(screen.getByLabelText("Reason for rejecting Pending Spot"), {
      target: { value: "   " },
    });
    expect(confirm.disabled).toBe(true);
    fireEvent.click(confirm);
    expect(PATCH).not.toHaveBeenCalled();
  });

  it("rejects with the reason and removes the item", async () => {
    GET.mockResolvedValue(queue([spotItem()]));
    PATCH.mockResolvedValue(status(200));
    render(<ModerationQueue />);
    fireEvent.click(await screen.findByRole("button", { name: "Reject Pending Spot" }));
    fireEvent.change(screen.getByLabelText("Reason for rejecting Pending Spot"), {
      target: { value: "  Duplicate of Ikogosi Resort  " },
    });
    fireEvent.click(screen.getByRole("button", { name: "Confirm rejection" }));

    expect(await screen.findByText("Rejected Pending Spot.")).toBeTruthy();
    expect(PATCH).toHaveBeenCalledWith("/api/spots/{spot_id}", {
      params: { path: { spot_id: "spot-1" } },
      body: { decision: "reject", reason: "Duplicate of Ikogosi Resort" },
      headers: { Authorization: "Bearer id-token-123" },
    });
    expect(await screen.findByText("Nothing is waiting for review.")).toBeTruthy();
  });

  it("lets a moderator back out of a rejection without calling the API", async () => {
    GET.mockResolvedValue(queue([spotItem()]));
    render(<ModerationQueue />);
    fireEvent.click(await screen.findByRole("button", { name: "Reject Pending Spot" }));
    fireEvent.click(screen.getByRole("button", { name: "Cancel" }));
    expect(screen.getByRole("button", { name: "Approve Pending Spot" })).toBeTruthy();
    expect(PATCH).not.toHaveBeenCalled();
  });

  it("decides on photos through the photo endpoint", async () => {
    GET.mockResolvedValue(queue([photoItem]));
    PATCH.mockResolvedValue(status(200));
    render(<ModerationQueue />);
    fireEvent.click(await screen.findByRole("button", { name: "Approve Live Spot" }));
    expect(await screen.findByText("Approved the photo on Live Spot.")).toBeTruthy();
    expect(PATCH).toHaveBeenCalledWith("/api/photos/{photo_id}", {
      params: { path: { photo_id: "photo-1" } },
      body: { decision: "approve" },
      headers: { Authorization: "Bearer id-token-123" },
    });
  });

  it("treats a 409 as already handled by someone else and removes the item", async () => {
    GET.mockResolvedValue(queue([spotItem()]));
    PATCH.mockResolvedValue(status(409));
    render(<ModerationQueue />);
    fireEvent.click(await screen.findByRole("button", { name: "Approve Pending Spot" }));
    expect(await screen.findByText("Someone else already decided on Pending Spot.")).toBeTruthy();
    expect(screen.queryByRole("article", { name: "Pending Spot" })).toBeNull();
  });

  it("keeps the item and shows an error when saving fails", async () => {
    GET.mockResolvedValue(queue([spotItem()]));
    PATCH.mockResolvedValue(status(500));
    render(<ModerationQueue />);
    fireEvent.click(await screen.findByRole("button", { name: "Approve Pending Spot" }));
    const alert = await screen.findByRole("alert");
    expect(alert.textContent).toContain("could not be saved");
    const approve = screen.getByRole("button", { name: "Approve Pending Spot" }) as HTMLButtonElement;
    expect(approve.disabled).toBe(false);
  });

  it("shows the no-access view if access is revoked mid-session", async () => {
    GET.mockResolvedValueOnce(queue([spotItem()])).mockResolvedValue(status(403));
    PATCH.mockResolvedValue(status(403));
    render(<ModerationQueue />);
    fireEvent.click(await screen.findByRole("button", { name: "Approve Pending Spot" }));
    expect(await screen.findByText("403: no access")).toBeTruthy();
    expect(screen.queryByRole("article", { name: "Pending Spot" })).toBeNull();
  });
});
