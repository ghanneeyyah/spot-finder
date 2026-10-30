import Link from "next/link";
import { buttonClass, secondaryButtonClass } from "@/components/ui/Field";

export default function NotFound() {
  return (
    <div className="mx-auto flex max-w-xl flex-col items-start gap-4 px-4 py-16">
      <h1 className="font-serif text-4xl font-bold">Page not found</h1>
      <p className="text-lg">This address does not lead anywhere. It may have moved or never existed.</p>
      <div className="flex gap-3">
        <Link href="/" className={buttonClass}>
          Open the map
        </Link>
        <Link href="/spots" className={secondaryButtonClass}>
          Browse spots
        </Link>
      </div>
    </div>
  );
}
