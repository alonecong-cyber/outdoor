"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const items = [
  { href: "/", label: "线报", glyph: "⚡" },
  { href: "/variants", label: "目录", glyph: "▦" },
  { href: "/calculator", label: "计算器", glyph: "∑" },
  { href: "/alerts", label: "提醒", glyph: "◉" },
];

export function BottomNav() {
  const pathname = usePathname();
  return (
    <nav className="fixed inset-x-0 bottom-0 z-40 border-t border-line bg-bg/90 backdrop-blur md:hidden">
      <div className="mx-auto grid max-w-3xl grid-cols-4">
        {items.map((it) => {
          const active =
            it.href === "/" ? pathname === "/" : pathname.startsWith(it.href);
          return (
            <Link
              key={it.href}
              href={it.href}
              className={`flex flex-col items-center gap-0.5 py-2.5 text-[11px] tracking-widest transition-colors ${
                active ? "text-accent" : "text-dim hover:text-ink"
              }`}
            >
              <span className="text-base leading-none">{it.glyph}</span>
              {it.label}
            </Link>
          );
        })}
      </div>
    </nav>
  );
}
