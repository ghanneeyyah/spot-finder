import Link from "next/link";

export function Footer() {
  return (
    <footer className="border-t border-line bg-surface">
      <div className="mx-auto flex max-w-6xl items-center justify-between px-4 py-4 text-muted">
        <span>Spotfinder</span>
        <Link href="/about" className="underline">
          How safety reports work
        </Link>
      </div>
    </footer>
  );
}
