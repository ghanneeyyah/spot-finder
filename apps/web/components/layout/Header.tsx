import Link from "next/link";
import { NavLinks } from "@/components/layout/NavLinks";

export function Header() {
  return (
    <header className="border-b border-line bg-surface" style={{ height: "var(--header-h)" }}>
      <div className="mx-auto flex h-full max-w-6xl items-center justify-between px-4">
        <Link href="/" className="font-serif text-xl font-bold">
          Spotfinder
        </Link>
        <NavLinks />
      </div>
    </header>
  );
}
