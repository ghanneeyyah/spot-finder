"use client";

export default function GlobalError({ reset }: { error: Error & { digest?: string }; reset: () => void }) {
  return (
    <html lang="en">
      <body style={{ fontFamily: "system-ui, sans-serif", color: "#1d2457", background: "#f6f7fb", margin: 0 }}>
        <div role="alert" style={{ maxWidth: 560, margin: "0 auto", padding: "4rem 1rem" }}>
          <h1 style={{ fontFamily: "Georgia, serif", fontSize: "2.25rem" }}>Something went wrong</h1>
          <p style={{ fontSize: "1.125rem" }}>The page could not load. Try again in a moment.</p>
          <button
            type="button"
            onClick={reset}
            style={{ background: "#1d2457", color: "#fff", border: 0, borderRadius: 6, padding: "0.6rem 1rem", fontSize: "1rem", fontWeight: 600 }}
          >
            Try again
          </button>
        </div>
      </body>
    </html>
  );
}
