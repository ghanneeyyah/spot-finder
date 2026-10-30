import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "About",
  description: "How Spotfinder works and how to read its safety reports.",
  alternates: { canonical: "/about" },
};

export default function AboutPage() {
  return (
    <div className="mx-auto flex max-w-prose flex-col gap-8 px-4 py-10 text-lg">
      <h1 className="font-serif text-4xl font-bold">About Spotfinder</h1>

      <section className="flex flex-col gap-3">
        <h2 className="font-serif text-2xl font-semibold">What it is</h2>
        <p>
          Spotfinder lists places worth visiting across Nigeria, with a cost estimate for each and
          safety reports from the people who have been there.
        </p>
      </section>

      <section className="flex flex-col gap-3">
        <h2 className="font-serif text-2xl font-semibold">How safety reports work</h2>
        <p>
          Every safety rating is the opinion of visitors. It is not a fact about the place, and it
          is not a guarantee.
        </p>
        <p>
          A spot shows a rating only after someone has reported on it. Until then it reads “No
          community reports yet”. Each person can report once per spot. The rating follows what
          most reporters chose, and when reports are split evenly it shows the more cautious one.
        </p>
        <ul className="flex flex-col gap-1 pl-5">
          <li className="list-disc">Reports lean safe: most reporters felt safe.</li>
          <li className="list-disc">Reports are mixed: experiences differ.</li>
          <li className="list-disc">Reports raise concerns: most reporters had a bad experience.</li>
        </ul>
      </section>

      <section className="flex flex-col gap-3">
        <h2 className="font-serif text-2xl font-semibold">Cost estimates</h2>
        <p>Prices are rough ranges and change often. Check before you go.</p>
      </section>

      <section className="flex flex-col gap-3">
        <h2 className="font-serif text-2xl font-semibold">Your call</h2>
        <p>
          Conditions change by the day and by the hour. Use local knowledge, check current advice
          for the area, and trust your own judgment over any rating here.
        </p>
      </section>
    </div>
  );
}
