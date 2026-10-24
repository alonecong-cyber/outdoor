import type { CSSProperties } from "react";

type IconName = "mountain" | "search" | "arrow" | "external" | "grid" | "bell" | "calculator" | "clock" | "check" | "chevron" | "close" | "menu" | "filter";

const paths: Record<IconName, React.ReactNode> = {
  mountain: <><path d="m2 19 7-13 5 8 3-5 5 10H2Z" /><path d="m6 12 3 1 2-3m4 2 2 1 2-1" /></>,
  search: <><circle cx="10.5" cy="10.5" r="6.5" /><path d="m16 16 4.5 4.5" /></>,
  arrow: <><path d="M4 12h16m-6-6 6 6-6 6" /></>,
  external: <><path d="M14 4h6v6m0-6L10 14" /><path d="M10 4H5a1 1 0 0 0-1 1v14a1 1 0 0 0 1 1h14a1 1 0 0 0 1-1v-5" /></>,
  grid: <><rect x="3" y="3" width="7" height="7" rx="1" /><rect x="14" y="3" width="7" height="7" rx="1" /><rect x="3" y="14" width="7" height="7" rx="1" /><rect x="14" y="14" width="7" height="7" rx="1" /></>,
  bell: <><path d="M18 8a6 6 0 0 0-12 0c0 7-3 7-3 9h18c0-2-3-2-3-9ZM10 21h4" /></>,
  calculator: <><rect x="5" y="2" width="14" height="20" rx="2" /><path d="M8 6h8M8 11h1m6 0h1m-8 4h1m6 0h1m-8 4h1m6 0h1" /></>,
  clock: <><circle cx="12" cy="12" r="9" /><path d="M12 7v5l3 2" /></>,
  check: <path d="m5 12 4 4L19 6" />,
  chevron: <path d="m9 5 7 7-7 7" />,
  close: <path d="m6 6 12 12M6 18 18 6" />,
  menu: <path d="M4 7h16M4 12h16M4 17h16" />,
  filter: <><path d="M3 6h18M7 12h10M10 18h4" /></>,
};

export function Icon({ name, className = "", style }: { name: IconName; className?: string; style?: CSSProperties }) {
  return <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" className={`icon ${className}`} style={style} aria-hidden="true">{paths[name]}</svg>;
}
