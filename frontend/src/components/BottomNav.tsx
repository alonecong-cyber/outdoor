"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Icon } from "@/components/Icon";

const items = [
  { href: "/", label: "发现", icon: "mountain" as const },
  { href: "/variants", label: "目录", icon: "grid" as const },
  { href: "/calculator", label: "计算器", icon: "calculator" as const },
  { href: "/alerts", label: "提醒", icon: "bell" as const },
];

export function BottomNav() {
  const pathname = usePathname();
  // 详情使用专门的价格与操作栏；顶部菜单保留完整导航。
  if (/^\/(deals|variants)\/[^/]+/.test(pathname)) return null;
  return <nav className="bottom-nav" aria-label="移动底部导航"><div>{items.map((item) => {
    const active = item.href === "/" ? pathname === "/" : pathname.startsWith(item.href);
    return <Link key={item.href} href={item.href} className={active ? "is-active" : ""} aria-current={active ? "page" : undefined}><Icon name={item.icon} /><span>{item.label}</span></Link>;
  })}</div></nav>;
}
