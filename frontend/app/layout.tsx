import Link from "next/link";
import type { ReactNode } from "react";

import "./globals.css";

export const metadata = { title: "DB Agent" };

const steps = [
  ["Sources", "/sources"],
  ["Tables", "/tables"],
  ["Relationships", "/relationships"],
  ["Semantics", "/semantics"],
  ["Deploy", "/deploy"],
  ["Ask", "/ask"],
] as const;

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en">
      {/* suppressHydrationWarning: browser extensions (password managers, Grammarly,
          etc.) commonly inject attributes onto <body> before React hydrates, which
          otherwise reads as a false-positive mismatch. This doesn't hide real
          mismatches elsewhere in the tree. */}
      <body className="font-sans" suppressHydrationWarning>
        <nav className="flex gap-4 border-b border-gray-200 p-4">
          {steps.map(([label, href]) => (
            <Link key={href} href={href}>
              {label}
            </Link>
          ))}
        </nav>
        <main className="p-6">{children}</main>
      </body>
    </html>
  );
}
