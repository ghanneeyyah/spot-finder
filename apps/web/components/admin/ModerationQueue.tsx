"use client";

import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";
import { ModerationItemCard, type Decision } from "@/components/admin/ModerationItemCard";
import { buttonClass, secondaryButtonClass } from "@/components/ui/Field";
import { api, type ModerationItem } from "@/lib/api";
import { getIdToken, onAuthChange, signInWithGoogle, signOutUser, type SignedInUser } from "@/lib/auth";

const PAGE_SIZE = 20;

type Fetched =
  | { key: string; name: "queue"; items: ModerationItem[]; total: number }
  | { key: string; name: "forbidden" | "signed-out" | "error" };

type View =
  | { name: "loading" | "unconfigured" | "signed-out" | "error" }
  | { name: "forbidden"; email: string | null }
  | { name: "queue"; items: ModerationItem[]; total: number };

/**
 * The page never decides who is a moderator. It asks the API, which checks the Firebase token and
 * the role stored in the database: a 403 from the API is what produces the "no access" view, and
 * a 403 on any decision sends the page back through the same check.
 */
export function ModerationQueue() {
  const [user, setUser] = useState<SignedInUser | null | undefined>(undefined);
  const [unconfigured, setUnconfigured] = useState(false);
  const [fetched, setFetched] = useState<Fetched | null>(null);
  const [offset, setOffset] = useState(0);
  const [attempt, setAttempt] = useState(0);
  const [actionError, setActionError] = useState<string | null>(null);
  const [removed, setRemoved] = useState<{ key: string; ids: string[] }>({ key: "", ids: [] });
  const [announcement, setAnnouncement] = useState("");
  const statusRef = useRef<HTMLParagraphElement>(null);

  // Keyboard users lose their place when the card they were on disappears, so focus moves to the
  // status message, which also announces the outcome to screen readers.
  useEffect(() => {
    if (announcement) statusRef.current?.focus();
  }, [announcement]);

  useEffect(() => {
    let unsubscribe: (() => void) | undefined;
    let cancelled = false;
    onAuthChange((next) => {
      if (!cancelled) setUser(next);
    })
      .then((stop) => {
        if (cancelled) stop();
        else unsubscribe = stop;
      })
      .catch(() => {
        if (!cancelled) setUnconfigured(true);
      });
    return () => {
      cancelled = true;
      unsubscribe?.();
    };
  }, []);

  const requestKey = user ? `${user.email ?? ""}|${offset}|${attempt}` : null;

  useEffect(() => {
    if (requestKey === null) return;
    let cancelled = false;
    const finish = (result: Fetched) => {
      if (!cancelled) setFetched(result);
    };
    (async () => {
      try {
        const token = await getIdToken();
        if (!token) return finish({ key: requestKey, name: "signed-out" });
        const { data, response } = await api.GET("/api/admin/moderation-queue", {
          params: { query: { limit: PAGE_SIZE, offset } },
          headers: { Authorization: `Bearer ${token}` },
        });
        if (data) finish({ key: requestKey, name: "queue", items: data.items, total: data.total });
        else if (response.status === 403) finish({ key: requestKey, name: "forbidden" });
        else if (response.status === 401) finish({ key: requestKey, name: "signed-out" });
        else finish({ key: requestKey, name: "error" });
      } catch {
        finish({ key: requestKey, name: "error" });
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [requestKey, offset]);

  const decide = useCallback(
    async (item: ModerationItem, decision: Decision): Promise<string | null> => {
      const label = item.kind === "spot" ? item.spot_name : `the photo on ${item.spot_name}`;
      try {
        const token = await getIdToken();
        if (!token) {
          setAttempt((n) => n + 1);
          return "You were signed out. Sign in again.";
        }
        const headers = { Authorization: `Bearer ${token}` };
        const body = decision.decision === "reject" ? decision : { decision: "approve" as const };
        const { response } =
          item.kind === "spot"
            ? await api.PATCH("/api/spots/{spot_id}", {
                params: { path: { spot_id: item.id } },
                body,
                headers,
              })
            : await api.PATCH("/api/photos/{photo_id}", {
                params: { path: { photo_id: item.id } },
                body,
                headers,
              });

        if (response.status === 401 || response.status === 403) {
          setAttempt((n) => n + 1); // the queue shows the right "signed out" or "no access" state
          return "Your access has changed.";
        }
        if (response.ok || response.status === 409) {
          setRemoved((current) => ({
            key: requestKey ?? "",
            ids: [...(current.key === requestKey ? current.ids : []), `${item.kind}-${item.id}`],
          }));
          setAnnouncement(
            response.ok
              ? `${decision.decision === "approve" ? "Approved" : "Rejected"} ${label}.`
              : `Someone else already decided on ${label}.`,
          );
          return null;
        }
        return "That could not be saved. Try again.";
      } catch {
        return "That could not be saved. Check your connection and try again.";
      }
    },
    [requestKey],
  );

  const run = async (action: () => Promise<void>) => {
    setActionError(null);
    try {
      await action();
    } catch {
      setActionError("That did not work. Try again.");
    }
  };

  const hidden = new Set(removed.key === requestKey ? removed.ids : []);

  let view: View;
  if (unconfigured) view = { name: "unconfigured" };
  else if (user === undefined) view = { name: "loading" };
  else if (user === null) view = { name: "signed-out" };
  else if (fetched === null || fetched.key !== requestKey) view = { name: "loading" };
  else if (fetched.name === "queue") view = { name: "queue", items: fetched.items, total: fetched.total };
  else if (fetched.name === "forbidden") view = { name: "forbidden", email: user.email };
  else view = { name: fetched.name };

  return (
    <div className="flex flex-col gap-6">
      <h1 className="font-serif text-3xl font-bold">Moderation queue</h1>

      {view.name === "loading" && <p role="status">Loading</p>}

      {view.name === "unconfigured" && <p>Sign-in is not configured for this site.</p>}

      {view.name === "signed-out" && (
        <div className="flex flex-col items-start gap-3">
          <p>Sign in with a moderator account to see pending items.</p>
          <button type="button" className={buttonClass} onClick={() => run(signInWithGoogle)}>
            Sign in with Google
          </button>
        </div>
      )}

      {view.name === "forbidden" && (
        <div className="flex flex-col items-start gap-3" role="alert">
          <h2 className="font-serif text-2xl font-semibold">403: no access</h2>
          <p>{view.email ?? "This account"} is not a moderator.</p>
          <div className="flex gap-3">
            <button type="button" className={secondaryButtonClass} onClick={() => run(signOutUser)}>
              Sign out
            </button>
            <Link href="/" className={secondaryButtonClass}>
              Back to the map
            </Link>
          </div>
        </div>
      )}

      {view.name === "error" && (
        <div className="flex flex-col items-start gap-3" role="alert">
          <p>The queue could not be loaded.</p>
          {user && (
            <button type="button" className={secondaryButtonClass} onClick={() => setAttempt((n) => n + 1)}>
              Try again
            </button>
          )}
        </div>
      )}

      {view.name === "queue" && (
        <QueueView
          items={view.items.filter((item) => !hidden.has(`${item.kind}-${item.id}`))}
          total={view.total - hidden.size}
          offset={offset}
          onDecide={decide}
          onPage={setOffset}
          onRefill={() => setAttempt((n) => n + 1)}
        />
      )}

      {announcement && (
        <p ref={statusRef} tabIndex={-1} role="status" className="font-semibold outline-none">
          {announcement}
        </p>
      )}

      {view.name === "queue" && (
        <div>
          <button type="button" className={secondaryButtonClass} onClick={() => run(signOutUser)}>
            Sign out
          </button>
        </div>
      )}

      {actionError && <p role="alert">{actionError}</p>}
    </div>
  );
}

function QueueView({
  items,
  total,
  offset,
  onDecide,
  onPage,
  onRefill,
}: {
  items: ModerationItem[];
  /** Pending items across all pages, with this session's decisions already subtracted. */
  total: number;
  offset: number;
  onDecide: (item: ModerationItem, decision: Decision) => Promise<string | null>;
  onPage: (offset: number) => void;
  onRefill: () => void;
}) {
  if (items.length === 0) {
    if (total <= 0) return <p>Nothing is waiting for review.</p>;
    // Everything on this page was decided but more is waiting elsewhere.
    return (
      <button type="button" className={buttonClass} onClick={() => (offset > 0 ? onPage(0) : onRefill())}>
        {offset > 0 ? "Back to the start of the queue" : "Load the next items"}
      </button>
    );
  }
  return (
    <>
      <p className="text-muted">
        {offset + 1} to {offset + items.length} of {total}
      </p>
      <ul className="flex flex-col gap-4">
        {items.map((item) => (
          <li key={`${item.kind}-${item.id}`}>
            <ModerationItemCard item={item} onDecide={onDecide} />
          </li>
        ))}
      </ul>
      <div className="flex gap-6">
        {offset > 0 && (
          <button
            type="button"
            className="font-semibold underline"
            onClick={() => onPage(Math.max(offset - PAGE_SIZE, 0))}
          >
            Previous
          </button>
        )}
        {/* Decided items have left the server's list, so the next page starts right after the
            items still shown here, not a full page further on. */}
        {offset + items.length < total && (
          <button type="button" className="font-semibold underline" onClick={() => onPage(offset + items.length)}>
            Next
          </button>
        )}
      </div>
    </>
  );
}
