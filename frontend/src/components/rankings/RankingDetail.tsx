"use client";

import Link from "next/link";
import { useEffect, useRef, type ReactNode } from "react";
import type { GearRankingItem } from "@/lib/api";
import { Icon } from "@/components/Icon";
import {
  CnReviewList,
  CompareToggle,
  GearImage,
  PriceSummary,
  ScoreBars,
  TIER_STYLE,
  isCnPick,
  rankLabel,
  shortSource,
} from "@/components/rankings/RankingCard";

/** 打开弹层时锁定背景滚动，Esc 关闭。 */
export function useOverlay(open: boolean, onClose: () => void) {
  const close = useRef(onClose);
  close.current = onClose;
  useEffect(() => {
    if (!open) return undefined;
    const prev = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && close.current();
    window.addEventListener("keydown", onKey);
    return () => {
      document.body.style.overflow = prev;
      window.removeEventListener("keydown", onKey);
    };
  }, [open]);
}

function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="border-t border-line py-4">
      <h3 className="mb-2.5 text-sm font-semibold text-ink">{title}</h3>
      {children}
    </section>
  );
}

function LinkChips({ links, tone = "text-ink" }: { links: { label: string; url: string }[]; tone?: string }) {
  return (
    <div className="flex flex-wrap gap-2">
      {links.map((l, i) => (
        <a
          key={`${l.label}-${i}`}
          href={l.url}
          target="_blank"
          rel="noopener noreferrer"
          className={`inline-flex min-h-9 items-center gap-1 rounded-md border border-line bg-panel px-3 text-[13px] hover:border-forest ${tone}`}
        >
          {l.label}
          <Icon name="external" className="!h-3.5 !w-3.5 text-dim" />
        </a>
      ))}
    </div>
  );
}

/** 单品详情：桌面右侧抽屉，移动端底部全屏面板。 */
export function RankingDetail({
  item,
  selected,
  onToggleSelect,
  onClose,
}: {
  item: GearRankingItem | null;
  selected: boolean;
  onToggleSelect: (id: string) => void;
  onClose: () => void;
}) {
  useOverlay(item != null, onClose);
  if (!item) return null;
  const cnPick = isCnPick(item);
  const pros = item.pros_zh?.length ? item.pros_zh : item.pros;
  const cons = item.cons_zh?.length ? item.cons_zh : item.cons;
  const quotes = item.authorities.filter((a) => a.quote);
  const specRows = Object.entries(item.spec_table ?? {});
  const watchHref = `/watch?name=${encodeURIComponent(item.name_cn)}&keywords=${encodeURIComponent([item.name_cn, item.name].join(","))}`;

  return (
    <div className="fixed inset-0 z-[60] flex justify-end" role="dialog" aria-modal="true" aria-labelledby="rk-detail-title">
      <button type="button" aria-label="关闭详情" className="absolute inset-0 bg-[#10201899] backdrop-blur-[2px]" onClick={onClose} />
      <div className="relative mt-auto flex max-h-[92dvh] w-full flex-col overflow-hidden rounded-t-2xl bg-panel shadow-2xl sm:mt-0 sm:h-full sm:max-h-none sm:max-w-xl sm:rounded-none">
        <header className="flex items-center gap-3 border-b border-line px-5 py-3">
          <span className="mx-auto h-1 w-10 rounded-full bg-line sm:hidden" aria-hidden="true" />
          <p className="hidden min-w-0 flex-1 truncate text-xs text-dim sm:block">{item.category_name} · {item.brand_name}</p>
          <button type="button" onClick={onClose} className="absolute right-3 top-2 grid h-10 w-10 place-items-center rounded-full hover:bg-panel-2 sm:static" aria-label="关闭">
            <Icon name="close" />
          </button>
        </header>

        <div className="flex-1 overflow-y-auto overscroll-contain px-5 pb-6">
          <div className="relative -mx-5 aspect-[16/10] bg-white">
            <GearImage item={item} className="absolute inset-0 h-full w-full object-contain p-5" />
          </div>
          <div className="pt-4">
            <div className="mb-2 flex flex-wrap gap-1.5">
              <span className={`rounded border px-1.5 py-0.5 text-xs font-semibold ${TIER_STYLE[item.price_tier] ?? TIER_STYLE.budget}`}>{item.price_tier_name}</span>
              {item.is_cn_brand && <span className="rounded bg-accent px-1.5 py-0.5 text-xs font-semibold text-white">国货</span>}
              {item.gender_name && <span className="rounded border border-line px-1.5 py-0.5 text-xs text-dim">{item.gender_name}</span>}
              {item.rating_score ? (
                <span className="rounded bg-forest px-1.5 py-0.5 font-mono text-xs font-semibold text-white" title={item.score_basis}>实测 {item.rating_score} 分</span>
              ) : null}
            </div>
            <h2 id="rk-detail-title" className="text-xl font-semibold leading-snug text-ink">{item.name_cn}</h2>
            <p className="font-mono text-[13px] text-dim">{item.name}{item.brand_country ? ` · ${item.brand_country}` : ""}</p>
          </div>

          <div className="my-4 rounded-lg bg-bg p-4">
            <PriceSummary item={item} />
            {item.price_guide.promo_tips && <p className="mt-2 text-xs leading-relaxed text-dim">{item.price_guide.promo_tips}</p>}
          </div>

          <p className="mb-4 rounded-md border-l-[3px] border-forest bg-[#edf1e8] px-3 py-2.5 text-[13px] leading-relaxed text-[#36493b]">{item.bottom_line}</p>

          {item.authorities.length > 0 && (
            <Section title="榜单与奖项">
              <ul className="space-y-2">
                {item.authorities.map((a, i) => (
                  <li key={i}>
                    <a href={a.url || undefined} target="_blank" rel="noopener noreferrer" className="flex items-center gap-2 text-[13px] hover:underline">
                      <Icon name="award" className="!h-4 !w-4 shrink-0 text-forest" />
                      <strong className="shrink-0">{shortSource(a.source)} {rankLabel(a)}</strong>
                      <span className="truncate" title={a.badge}>{a.badge_zh || a.badge}</span>
                    </a>
                  </li>
                ))}
              </ul>
            </Section>
          )}

          {Object.keys(item.sub_scores ?? {}).length > 0 && (
            <Section title="分项评分（满分 10）">
              <ScoreBars item={item} />
            </Section>
          )}

          <Section title={cnPick ? "优缺点" : "优缺点（测评译文，长按/悬停看原文）"}>
            <div className="grid gap-3 sm:grid-cols-2">
              <ul className="space-y-1.5 text-[13px] leading-relaxed">
                {pros.map((p, i) => (
                  <li key={`${p}-${i}`} title={item.pros[i]} className="flex gap-2"><span className="text-moss">＋</span>{p}</li>
                ))}
              </ul>
              <ul className="space-y-1.5 text-[13px] leading-relaxed">
                {cons.map((p, i) => (
                  <li key={`${p}-${i}`} title={item.cons[i]} className="flex gap-2"><span className="text-accent">－</span>{p}</li>
                ))}
              </ul>
            </div>
          </Section>

          {!cnPick && quotes.length > 0 && (
            <Section title="测评结论">
              <div className="space-y-2">
                {quotes.map((a, i) => (
                  <blockquote key={i} title={a.quote} className="text-[13px] leading-relaxed text-ink/85">
                    “{a.quote_zh || a.quote}” <cite className="not-italic text-xs text-dim">— {a.source}</cite>
                  </blockquote>
                ))}
              </div>
            </Section>
          )}

          <Section title="差价分析">
            <p className="text-[13px] leading-relaxed text-ink/85">{item.gap_analysis}</p>
          </Section>

          {(item.cn_reviews?.length ?? 0) > 0 && (
            <Section title="国内口碑（什么值得买 / B站 / 小红书）">
              <CnReviewList item={item} limit={9} />
            </Section>
          )}

          {specRows.length > 0 && (
            <Section title="规格参数">
              <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-1.5 text-[13px]">
                {specRows.map(([k, v]) => (
                  <div key={k} className="contents"><dt className="text-dim">{k}</dt><dd className="text-ink">{v}</dd></div>
                ))}
              </dl>
            </Section>
          )}

          {(item.cn_links?.length ?? 0) > 0 && (
            <Section title="去国内平台看看">
              <LinkChips links={item.cn_links ?? []} />
            </Section>
          )}
          {(item.buy_links?.length ?? 0) > 0 && (
            <Section title="评测原文 / 海外购买">
              <LinkChips links={item.buy_links ?? []} tone="text-[#2b4c68]" />
            </Section>
          )}
        </div>

        <footer className="flex gap-2 border-t border-line bg-panel px-5 py-3 pb-[calc(12px+env(safe-area-inset-bottom,0px))]">
          <CompareToggle selected={selected} onClick={() => onToggleSelect(item.id)} className="min-h-11 flex-1" />
          <Link href={watchHref} className="inline-flex min-h-11 flex-1 items-center justify-center gap-1.5 rounded-md bg-forest px-3 text-[13px] font-semibold text-white hover:bg-forest-2">
            <Icon name="bell" className="!h-4 !w-4" />关注降价
          </Link>
        </footer>
      </div>
    </div>
  );
}
