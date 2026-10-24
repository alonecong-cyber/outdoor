"use client";

import { fen } from "@/lib/format";

/**
 * 价格走势迷你图：90 天快照折线，最低点标橙。
 * 纯 SVG，无依赖；points 为按时间升序的 {ts, price_cents}。
 */
export function Sparkline({
  points,
  width = 120,
  height = 36,
}: {
  points: { ts: string; price_cents: number }[];
  width?: number;
  height?: number;
}) {
  if (points.length < 2) {
    return (
      <svg width={width} height={height} aria-label="历史不足" role="img">
        <line
          x1={0}
          y1={height / 2}
          x2={width}
          y2={height / 2}
          stroke="var(--color-line)"
          strokeDasharray="3 4"
        />
      </svg>
    );
  }
  const prices = points.map((p) => p.price_cents);
  const min = Math.min(...prices);
  const max = Math.max(...prices);
  const span = max - min || 1;
  const stepX = width / (points.length - 1);
  const y = (p: number) => 3 + (height - 6) * (1 - (p - min) / span);
  const coords = points.map((p, i) => `${(i * stepX).toFixed(1)},${y(p.price_cents).toFixed(1)}`);
  const minIdx = prices.indexOf(min);

  return (
    <svg width={width} height={height} viewBox={`0 0 ${width} ${height}`} role="img" aria-label="90 天价格走势">
      <polyline
        points={coords.join(" ")}
        fill="none"
        stroke="var(--color-dim)"
        strokeWidth={1.5}
        strokeLinejoin="round"
      />
      <circle
        cx={minIdx * stepX}
        cy={y(min)}
        r={3}
        fill="var(--color-accent)"
        stroke="var(--color-bg)"
        strokeWidth={1}
      />
      <title>{`最低 ${fen(min)}`}</title>
    </svg>
  );
}
