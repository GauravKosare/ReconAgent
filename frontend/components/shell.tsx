"use client";

import { usePathname } from "next/navigation";
import Link from "next/link";
import type { ReactNode } from "react";
import { NavLink } from "./ui";
import {
  IconClock,
  IconGrid,
  IconQueue,
  IconReport,
  IconShield,
  IconUpload,
} from "./icons";

export function Shell({
  children,
  batchId,
  demo,
}: {
  children: ReactNode;
  batchId?: string;
  demo?: boolean;
}) {
  const path = usePathname();
  const b = batchId ? `/batches/${batchId}` : "";

  const nav = [
    { href: "/", label: "Overview", icon: <IconGrid />, on: path === "/" },
    { href: "/upload", label: "New batch", icon: <IconUpload />, on: path === "/upload" },
    ...(batchId
      ? [
          { href: b, label: "Batch dashboard", icon: <IconReport />, on: path === b },
          { href: `${b}/queue`, label: "Approval queue", icon: <IconQueue />, on: path === `${b}/queue` },
          { href: `${b}/audit`, label: "Audit log", icon: <IconClock />, on: path === `${b}/audit` },
        ]
      : []),
  ];

  return (
    <div className="min-h-dvh md:grid md:grid-cols-[248px_1fr]">
      {/* sidebar */}
      <aside className="hidden border-r border-line bg-surface/60 px-4 py-5 md:flex md:flex-col">
        <Link href="/" className="mb-7 flex items-center gap-2.5 px-2">
          <span className="grid h-8 w-8 place-items-center rounded-lg bg-brand text-white">
            <IconShield className="h-[18px] w-[18px]" />
          </span>
          <span>
            <span className="block font-display text-[17px] leading-none text-ink">ReconAgent</span>
            <span className="block text-[11px] text-faint">Finance controller</span>
          </span>
        </Link>

        <nav className="grid gap-1">
          {nav.map((n) => (
            <NavLink key={n.href} href={n.href} active={n.on} icon={n.icon}>
              {n.label}
            </NavLink>
          ))}
        </nav>

        <div className="mt-auto rounded-xl border border-line bg-card p-3 text-[11px] leading-relaxed text-faint">
          {demo ? (
            <>
              <span className="font-medium text-warn">Demo data</span> — API offline, showing a
              bundled sample batch.
            </>
          ) : (
            <>
              Connected to{" "}
              <span className="font-mono text-muted">
                {process.env.NEXT_PUBLIC_API_URL || "localhost:8000"}
              </span>
            </>
          )}
        </div>
      </aside>

      {/* main */}
      <div className="flex min-w-0 flex-col">
        <header className="sticky top-0 z-20 flex items-center gap-3 border-b border-line bg-bg/80 px-5 py-3 backdrop-blur md:px-8">
          <Link href="/" className="flex items-center gap-2 md:hidden">
            <span className="grid h-7 w-7 place-items-center rounded-md bg-brand text-white">
              <IconShield className="h-4 w-4" />
            </span>
            <span className="font-display text-ink">ReconAgent</span>
          </Link>
          <div className="hidden text-sm text-faint md:block">
            {batchId ? (
              <span className="font-mono text-muted">{batchId}</span>
            ) : (
              "Three-way reconciliation"
            )}
          </div>
          {demo && (
            <span className="ml-auto rounded-full bg-[color-mix(in_srgb,var(--warn)_16%,transparent)] px-2.5 py-1 text-xs font-medium text-warn">
              Demo mode
            </span>
          )}
        </header>
        {/* mobile nav */}
        <nav className="flex gap-1 overflow-x-auto border-b border-line bg-surface/50 px-3 py-2 md:hidden">
          {nav.map((n) => (
            <Link
              key={n.href}
              href={n.href}
              className={`flex shrink-0 items-center gap-1.5 rounded-lg px-2.5 py-1.5 text-xs font-medium ${
                n.on ? "bg-brand text-white" : "text-muted"
              }`}
            >
              {n.icon}
              {n.label}
            </Link>
          ))}
        </nav>
        <main className="flex-1 px-5 py-6 md:px-8 md:py-8">{children}</main>
      </div>
    </div>
  );
}
