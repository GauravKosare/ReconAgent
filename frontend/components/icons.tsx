/* Minimal inline icon set (Lucide-style, 1.5px stroke). No emoji, no deps. */
type P = { className?: string };
const base = "h-[18px] w-[18px]";
const s = (className?: string) => ({
  className: `${base} ${className ?? ""}`,
  viewBox: "0 0 24 24",
  fill: "none",
  stroke: "currentColor",
  strokeWidth: 1.6,
  strokeLinecap: "round" as const,
  strokeLinejoin: "round" as const,
});

export const IconGrid = (p: P) => (
  <svg {...s(p.className)}><rect x="3" y="3" width="7" height="7" rx="1.5" /><rect x="14" y="3" width="7" height="7" rx="1.5" /><rect x="14" y="14" width="7" height="7" rx="1.5" /><rect x="3" y="14" width="7" height="7" rx="1.5" /></svg>
);
export const IconQueue = (p: P) => (
  <svg {...s(p.className)}><path d="M4 7h16M4 12h10M4 17h7" /><circle cx="18" cy="15.5" r="3.2" /></svg>
);
export const IconClock = (p: P) => (
  <svg {...s(p.className)}><circle cx="12" cy="12" r="9" /><path d="M12 7v5l3 2" /></svg>
);
export const IconUpload = (p: P) => (
  <svg {...s(p.className)}><path d="M12 15V4M8 8l4-4 4 4" /><path d="M5 15v3a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2v-3" /></svg>
);
export const IconReport = (p: P) => (
  <svg {...s(p.className)}><path d="M6 20V10M12 20V4M18 20v-7" /></svg>
);
export const IconCheck = (p: P) => (
  <svg {...s(p.className)}><path d="M20 6 9 17l-5-5" /></svg>
);
export const IconX = (p: P) => (
  <svg {...s(p.className)}><path d="M18 6 6 18M6 6l12 12" /></svg>
);
export const IconEdit = (p: P) => (
  <svg {...s(p.className)}><path d="M12 20h9" /><path d="M16.5 3.5a2.1 2.1 0 0 1 3 3L7 19l-4 1 1-4Z" /></svg>
);
export const IconChevron = (p: P) => (
  <svg {...s(p.className)}><path d="m9 18 6-6-6-6" /></svg>
);
export const IconSpark = (p: P) => (
  <svg {...s(p.className)}><path d="M12 3v4M12 17v4M3 12h4M17 12h4M6 6l2.5 2.5M15.5 15.5 18 18M18 6l-2.5 2.5M8.5 15.5 6 18" /></svg>
);
export const IconShield = (p: P) => (
  <svg {...s(p.className)}><path d="M12 3 5 6v6c0 4.5 3 7.5 7 9 4-1.5 7-4.5 7-9V6Z" /><path d="m9 12 2 2 4-4" /></svg>
);
export const IconArrow = (p: P) => (
  <svg {...s(p.className)}><path d="M5 12h14M13 6l6 6-6 6" /></svg>
);
