"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { HeaderSearch } from "@/components/HeaderSearch";
import { Icon } from "@/components/Icon";

const NAV = [
  { href: "/", label: "发现优惠", short: "发现" },
  { href: "/variants", label: "装备目录", short: "目录" },
  { href: "/calculator", label: "到手价计算器", short: "计算器" },
  { href: "/alerts", label: "降价提醒", short: "提醒" },
];

export function SiteHeader({ kicker }: { kicker?: string }) {
  const pathname = usePathname();
  const active = (href: string) => href === "/" ? pathname === "/" || pathname.startsWith("/deals/") : pathname.startsWith(href);
  return (
    <header className="site-header">
      <Link href="/" className="wordmark" aria-label="OutdoorDeal 首页">
        <span className="brand-symbol"><Icon name="mountain" /></span>
        <span><span className="wordmark-name">OUTDOOR<span>DEAL</span><span className="brand-period">.</span></span><span className="wordmark-caption">户外装备 · 价格手册</span></span>
      </Link>
      <nav className="desktop-nav" aria-label="主导航">
        {NAV.map((item) => <Link key={item.href} href={item.href} className={active(item.href) ? "is-active" : ""} aria-current={active(item.href) ? "page" : undefined}>{item.label}</Link>)}
      </nav>
      <div className="header-end"><HeaderSearch /><span className="header-edition">FIELD NOTES <span>/ {kicker || "OUTDOOR"}</span></span>
        <details className="mobile-menu"><summary aria-label="打开导航菜单"><Icon name="menu" /></summary><nav aria-label="移动主导航">{NAV.map((item) => <Link key={item.href} href={item.href} aria-current={active(item.href) ? "page" : undefined}>{item.label}<Icon name="chevron" /></Link>)}</nav></details>
      </div>
    </header>
  );
}
