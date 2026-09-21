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
      <body className="font-sans">
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
