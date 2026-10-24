"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const NAV = [
  { href: "/", label: "线报" },
  { href: "/variants", label: "目录" },
  { href: "/calculator", label: "计算器" },
  { href: "/alerts", label: "提醒" },
];

/** 顶部品牌条：logo + 站名 + 桌面导航（移动端用底部 BottomNav）。 */
export function SiteHeader({ kicker }: { kicker?: string }) {
  const pathname = usePathname();
  return (
    <header className="rise mb-6">
      <div className="flex items-end justify-between border-b border-line pb-4">
        <Link href="/" className="group flex items-baseline gap-2">
          <span className="font-display text-xl font-black tracking-tight text-ink group-hover:text-accent">
            OUTDOOR<span className="text-accent">DEAL</span>
          </span>
          <span className="micro-label hidden sm:inline">比价 · 到手价 · 提醒</span>
        </Link>
        <nav className="hidden items-center gap-1 md:flex">
          {NAV.map((n) => {
            const active = n.href === "/" ? pathname === "/" : pathname.startsWith(n.href);
            return (
              <Link
                key={n.href}
                href={n.href}
                className={`btn rounded-full px-3.5 py-1.5 text-xs ${
                  active
                    ? "bg-accent text-[#140b06]"
                    : "border border-line text-dim hover:text-ink"
                }`}
              >
                {n.label}
              </Link>
            );
          })}
        </nav>
        {kicker ? <span className="micro-label md:hidden">{kicker}</span> : null}
      </div>
      <p className="micro-label mt-3">
        ELEV. 最低到手价 / 同款同色同码跨渠道 / 优惠叠加逐项透明
      </p>
    </header>
  );
}
