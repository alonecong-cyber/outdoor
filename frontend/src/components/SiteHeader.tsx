import Link from "next/link";

/** 顶部品牌条：logo + 站名 + 副标题，各页复用。 */
export function SiteHeader({ kicker }: { kicker?: string }) {
  return (
    <header className="rise mb-6">
      <div className="flex items-end justify-between border-b border-line pb-4">
        <Link href="/" className="group flex items-baseline gap-2">
          <span className="font-display text-xl font-black tracking-tight text-ink group-hover:text-accent">
            OUTDOOR<span className="text-accent">DEAL</span>
          </span>
          <span className="micro-label hidden sm:inline">比价 · 到手价 · 提醒</span>
        </Link>
        {kicker ? <span className="micro-label">{kicker}</span> : null}
      </div>
      <p className="micro-label mt-3">
        ELEV. 最低到手价 / 同款同色同码跨渠道 / 优惠叠加逐项透明
      </p>
    </header>
  );
}
