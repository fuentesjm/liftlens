"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const LINKS = [
  { href: "/", label: "Today" },
  { href: "/record", label: "Record a set" },
  { href: "/plan", label: "Plan" },
  { href: "/history", label: "History" },
];

export default function Nav() {
  const path = usePathname();
  const isActive = (href) =>
    href === "/" ? path === "/" : path.startsWith(href) || (href === "/history" && path.startsWith("/sessions"));

  return (
    <header className="topbar">
      <Link href="/" className="wordmark">
        LiftLens
      </Link>
      <nav className="nav" aria-label="Main">
        {LINKS.map((l) => (
          <Link key={l.href} href={l.href} aria-current={isActive(l.href) ? "page" : undefined}>
            {l.label}
          </Link>
        ))}
      </nav>
    </header>
  );
}
