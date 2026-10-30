import Link from "next/link";
import type { Category, Tier } from "@/lib/api";
import { CATEGORY_OPTIONS, STATE_OPTIONS, TIER_OPTIONS } from "@/lib/utils";
import { Field, buttonClass, controlClass } from "@/components/ui/Field";

interface Props {
  q?: string | undefined;
  state?: string | undefined;
  category?: Category | undefined;
  tier?: Tier | undefined;
}

/** A plain GET form: it works without JavaScript, which matters on slow phones. */
export function SpotFilters({ q, state, category, tier }: Props) {
  const active = Boolean(q || state || category || tier);
  return (
    <form action="/spots" method="get" className="grid gap-3 sm:grid-cols-2 lg:grid-cols-[2fr_1fr_1fr_1fr_auto] lg:items-end">
      <Field label="Search" htmlFor="q">
        <input id="q" name="q" type="search" defaultValue={q} maxLength={80} className={controlClass} />
      </Field>
      <Field label="State" htmlFor="state">
        <select id="state" name="state" defaultValue={state ?? ""} className={controlClass}>
          <option value="">All states</option>
          {STATE_OPTIONS.map((o) => (
            <option key={o.value} value={o.value}>
              {o.label}
            </option>
          ))}
        </select>
      </Field>
      <Field label="Category" htmlFor="category">
        <select id="category" name="category" defaultValue={category ?? ""} className={controlClass}>
          <option value="">All categories</option>
          {CATEGORY_OPTIONS.map((o) => (
            <option key={o.value} value={o.value}>
              {o.label}
            </option>
          ))}
        </select>
      </Field>
      <Field label="Safety reports" htmlFor="safety_tier">
        <select id="safety_tier" name="safety_tier" defaultValue={tier ?? ""} className={controlClass}>
          <option value="">Any</option>
          {TIER_OPTIONS.map((o) => (
            <option key={o.value} value={o.value}>
              {o.label}
            </option>
          ))}
        </select>
      </Field>
      <div className="flex items-center gap-4">
        <button type="submit" className={buttonClass}>
          Apply
        </button>
        {active && (
          <Link href="/spots" className="underline">
            Clear
          </Link>
        )}
      </div>
    </form>
  );
}
