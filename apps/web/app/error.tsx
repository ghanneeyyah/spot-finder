"use client";

import Link from "next/link";
import { useEffect } from "react";
import { buttonClass, secondaryButtonClass } from "@/components/ui/Field";

export default function ErrorPage({ error, reset }: { error: Error & { digest?: string }; reset: () => void }) {
  useEffect(() => {
    console.error(error);
  }, [error]);

  return (
    <div className="mx-auto flex max-w-xl flex-col items-start gap-4 px-4 py-16" role="alert">
      <h1 className="font-serif text-4xl font-bold">Something went wrong</h1>
      <p className="text-lg">The page could not load. Your connection may be down, or our side may be having trouble.</p>
      <div className="flex gap-3">
        <button type="button" onClick={reset} className={buttonClass}>
          Try again
        </button>
        <Link href="/" className={secondaryButtonClass}>
          Go to the map
        </Link>
      </div>
    </div>
  );
}
