"use client";

import Image from "next/image";
import Link from "next/link";
import { useId, useState } from "react";
import { buttonClass, controlClass, secondaryButtonClass } from "@/components/ui/Field";
import type { ModerationItem } from "@/lib/api";
import { CATEGORY_LABELS, formatSubmitted, humanize } from "@/lib/utils";

export type Decision = { decision: "approve" } | { decision: "reject"; reason: string };

/** Resolves to an error message, or null when the decision was saved. */
export type OnDecide = (item: ModerationItem, decision: Decision) => Promise<string | null>;

function Detail({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <dt className="font-semibold">{label}</dt>
      <dd>{children}</dd>
    </div>
  );
}

export function ModerationItemCard({ item, onDecide }: { item: ModerationItem; onDecide: OnDecide }) {
  const [rejecting, setRejecting] = useState(false);
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const reasonId = useId();

  const submit = async (decision: Decision) => {
    setBusy(true);
    setError(null);
    const failure = await onDecide(item, decision);
    // On success the parent removes this card, so only a failure needs the controls back.
    if (failure !== null) {
      setError(failure);
      setBusy(false);
    }
  };

  const spot = item.spot;
  const amenities = spot
    ? Object.entries(spot.amenities)
        .filter(([, on]) => on === true)
        .map(([key]) => humanize(key))
    : [];

  return (
    <article className="flex flex-col gap-4 rounded-lg border border-line bg-surface p-4" aria-label={item.spot_name}>
      <header>
        <p className="font-semibold">{item.kind === "spot" ? "New spot" : "New photo"}</p>
        <h2 className="font-serif text-xl font-semibold">{item.spot_name}</h2>
        <p className="text-muted">
          Submitted by {item.submitter ?? "an unknown account"} on {formatSubmitted(item.created_at)}
        </p>
      </header>

      {spot && (
        <dl className="grid gap-3 sm:grid-cols-2">
          <Detail label="Category">
            {CATEGORY_LABELS[spot.category as keyof typeof CATEGORY_LABELS] ?? spot.category}
          </Detail>
          <Detail label="Location">
            {spot.address ? `${spot.address}, ` : ""}
            {spot.city}, {spot.state}
          </Detail>
          {spot.cost_estimate_text && <Detail label="Cost estimate">{spot.cost_estimate_text}</Detail>}
          {spot.best_time && <Detail label="Best time">{spot.best_time}</Detail>}
          {amenities.length > 0 && <Detail label="On site">{amenities.join(", ")}</Detail>}
          <Detail label="Map">
            <a
              href={`https://www.google.com/maps/search/?api=1&query=${spot.latitude},${spot.longitude}`}
              target="_blank"
              rel="noopener noreferrer"
              className="underline"
            >
              Check the pin
            </a>
          </Detail>
          {spot.description && (
            <div className="sm:col-span-2">
              <dt className="font-semibold">Description</dt>
              <dd className="max-w-prose">{spot.description}</dd>
            </div>
          )}
        </dl>
      )}

      {item.kind === "photo" && (
        <div className="flex flex-col gap-2">
          {item.photo_url && (
            <a href={item.photo_url} target="_blank" rel="noopener noreferrer" className="w-fit">
              <Image
                src={item.photo_url}
                alt={`Submitted photo for ${item.spot_name}`}
                width={320}
                height={240}
                unoptimized
                className="aspect-[4/3] w-80 max-w-full rounded-md border border-line object-cover"
              />
            </a>
          )}
          <Link href={`/spots/${item.spot_slug}`} className="w-fit underline">
            Open the spot page
          </Link>
        </div>
      )}

      {rejecting ? (
        <form
          className="flex flex-col gap-3"
          onSubmit={(event) => {
            event.preventDefault();
            if (reason.trim()) void submit({ decision: "reject", reason: reason.trim() });
          }}
        >
          <label htmlFor={reasonId} className="font-semibold">
            Reason for rejecting {item.spot_name}
          </label>
          <textarea
            id={reasonId}
            value={reason}
            onChange={(event) => setReason(event.target.value)}
            maxLength={500}
            rows={3}
            required
            className={controlClass}
          />
          <div className="flex gap-3">
            <button
              type="submit"
              disabled={busy || reason.trim() === ""}
              className={`${buttonClass} disabled:opacity-50`}
            >
              Confirm rejection
            </button>
            <button type="button" disabled={busy} className={secondaryButtonClass} onClick={() => setRejecting(false)}>
              Cancel
            </button>
          </div>
        </form>
      ) : (
        <div className="flex gap-3">
          <button
            type="button"
            disabled={busy}
            className={`${buttonClass} disabled:opacity-50`}
            aria-label={`Approve ${item.spot_name}`}
            onClick={() => void submit({ decision: "approve" })}
          >
            Approve
          </button>
          <button
            type="button"
            disabled={busy}
            className={secondaryButtonClass}
            aria-label={`Reject ${item.spot_name}`}
            onClick={() => setRejecting(true)}
          >
            Reject
          </button>
        </div>
      )}

      {error && (
        <p role="alert" className="font-semibold">
          {error}
        </p>
      )}
    </article>
  );
}
