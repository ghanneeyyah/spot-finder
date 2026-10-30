import type { ReactNode } from "react";

export const controlClass =
  "w-full rounded-md border border-line bg-surface px-3 py-2 text-base text-ink focus-visible:border-ink";

export function Field({ label, htmlFor, children }: { label: string; htmlFor: string; children: ReactNode }) {
  return (
    <div className="flex flex-col gap-1">
      <label htmlFor={htmlFor} className="text-sm font-semibold">
        {label}
      </label>
      {children}
    </div>
  );
}

export const buttonClass =
  "inline-flex items-center justify-center rounded-md bg-ink px-4 py-2 text-base font-semibold text-white hover:bg-[#2b3480]";

export const secondaryButtonClass =
  "inline-flex items-center justify-center rounded-md border border-ink px-4 py-2 text-base font-semibold text-ink hover:bg-ink/5";
