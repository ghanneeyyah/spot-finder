// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
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
vi.mock("@/lib/api", () => ({ api: { GET: vi.fn() } }));

const GET = vi.mocked(api.GET) as unknown as ReturnType<typeof vi.fn>;

function signedInAs(email: string | null) {
  vi.mocked(onAuthChange).mockImplementation(async (callback) => {
    callback(email === null ? null : { email });
    return () => {};
  });
}

const respond = (status: number, data?: unknown) => GET.mockResolvedValue({ data, response: { status } });

beforeEach(() => {
  vi.mocked(getIdToken).mockResolvedValue("id-token-123");
});

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe("/admin moderation queue", () => {
  it("asks anonymous visitors to sign in and never calls the API", async () => {
    signedInAs(null);
    render(<ModerationQueue />);
    expect(await screen.findByRole("button", { name: "Sign in with Google" })).toBeTruthy();
    expect(GET).not.toHaveBeenCalled();
  });

  it("shows a 403 view, and no queue data, when the API says the account is not a moderator", async () => {
    signedInAs("visitor@example.com");
    respond(403);
    render(<ModerationQueue />);
    expect(await screen.findByText("403: no access")).toBeTruthy();
    expect(screen.getByText("visitor@example.com is not a moderator.")).toBeTruthy();
    expect(screen.queryByText("New spot")).toBeNull();
    expect(screen.getByRole("button", { name: "Sign out" })).toBeTruthy();
  });

  it("sends the Firebase ID token to the API as a bearer token", async () => {
    signedInAs("mod@example.com");
    respond(403);
    render(<ModerationQueue />);
    await screen.findByText("403: no access");
    expect(GET).toHaveBeenCalledWith("/api/admin/moderation-queue", {
      params: { query: { limit: 20, offset: 0 } },
      headers: { Authorization: "Bearer id-token-123" },
    });
  });

  it("lists pending items for a moderator", async () => {
    signedInAs("mod@example.com");
    respond(200, {
      items: [
        { kind: "spot", id: "a", spot_id: "a", spot_name: "Pending Spot", photo_url: null, created_at: "2026-10-28T10:00:00Z" },
        { kind: "photo", id: "b", spot_id: "c", spot_name: "Live Spot", photo_url: "https://res.cloudinary.com/x/y.jpg", created_at: "2026-10-28T11:00:00Z" },
      ],
      total: 2,
      limit: 20,
      offset: 0,
    });
    render(<ModerationQueue />);
    expect(await screen.findByText("Pending Spot")).toBeTruthy();
    expect(screen.getByText("New spot")).toBeTruthy();
    expect(screen.getByText("New photo")).toBeTruthy();
    expect(screen.getByText("1 to 2 of 2")).toBeTruthy();
    expect(screen.getByRole("link", { name: "View photo" }).getAttribute("href")).toBe("https://res.cloudinary.com/x/y.jpg");
    expect(screen.queryByText("403: no access")).toBeNull();
  });

  it("says so when the queue is empty", async () => {
    signedInAs("mod@example.com");
    respond(200, { items: [], total: 0, limit: 20, offset: 0 });
    render(<ModerationQueue />);
    expect(await screen.findByText("Nothing is waiting for review.")).toBeTruthy();
  });

  it("returns to the sign-in view when the API rejects the token", async () => {
    signedInAs("mod@example.com");
    respond(401);
    render(<ModerationQueue />);
    expect(await screen.findByRole("button", { name: "Sign in with Google" })).toBeTruthy();
  });

  it("offers a retry when the API fails", async () => {
    signedInAs("mod@example.com");
    respond(503);
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
