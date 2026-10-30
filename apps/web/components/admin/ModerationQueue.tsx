"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
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
 * the role stored in the database: a 403 from the API is what produces the "no access" view.
 */
export function ModerationQueue() {
  const [user, setUser] = useState<SignedInUser | null | undefined>(undefined);
  const [unconfigured, setUnconfigured] = useState(false);
  const [fetched, setFetched] = useState<Fetched | null>(null);
  const [offset, setOffset] = useState(0);
  const [attempt, setAttempt] = useState(0);
  const [actionError, setActionError] = useState<string | null>(null);

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

  let view: View;
  if (unconfigured) view = { name: "unconfigured" };
  else if (user === undefined) view = { name: "loading" };
  else if (user === null) view = { name: "signed-out" };
  else if (fetched === null || fetched.key !== requestKey) view = { name: "loading" };
  else if (fetched.name === "queue") view = { name: "queue", items: fetched.items, total: fetched.total };
  else if (fetched.name === "forbidden") view = { name: "forbidden", email: user.email };
  else view = { name: fetched.name };

  const run = async (action: () => Promise<void>) => {
    setActionError(null);
    try {
      await action();
    } catch {
      setActionError("That did not work. Try again.");
    }
  };

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
        <>
          {view.items.length === 0 ? (
            <p>Nothing is waiting for review.</p>
          ) : (
            <>
              <p className="text-muted" role="status">
                {offset + 1} to {offset + view.items.length} of {view.total}
              </p>
              <ul className="flex flex-col divide-y divide-line rounded-lg border border-line bg-surface">
                {view.items.map((item) => (
                  <li key={`${item.kind}-${item.id}`} className="flex items-center justify-between gap-4 p-4">
                    <div>
                      <p className="font-semibold">{item.kind === "spot" ? "New spot" : "New photo"}</p>
                      <p>{item.spot_name}</p>
                    </div>
                    {item.photo_url && (
                      <a href={item.photo_url} target="_blank" rel="noopener noreferrer" className="underline">
                        View photo
                      </a>
                    )}
                  </li>
                ))}
              </ul>
              <div className="flex gap-6">
                {offset > 0 && (
                  <button type="button" className="font-semibold underline" onClick={() => setOffset(Math.max(offset - PAGE_SIZE, 0))}>
                    Previous
                  </button>
                )}
                {offset + view.items.length < view.total && (
                  <button type="button" className="font-semibold underline" onClick={() => setOffset(offset + PAGE_SIZE)}>
                    Next
                  </button>
                )}
              </div>
            </>
          )}
          <div>
            <button type="button" className={secondaryButtonClass} onClick={() => run(signOutUser)}>
              Sign out
            </button>
          </div>
        </>
      )}

      {actionError && <p role="alert">{actionError}</p>}
    </div>
  );
}
