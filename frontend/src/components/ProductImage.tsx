"use client";

import { useState } from "react";

/** 商品完整入框；缺图时使用本地占位，加载失败不影响阅读。 */
export function ProductImage({ src, alt, className, priority = false }: { src?: string | null; alt: string; className?: string; priority?: boolean }) {
  const [failedSource, setFailedSource] = useState<string | null>(null);
  const url = src && src !== failedSource ? src : "/products/placeholder.svg";
  return (
    // eslint-disable-next-line @next/next/no-img-element
    <img src={url} alt={alt} loading={priority ? "eager" : "lazy"} fetchPriority={priority ? "high" : "auto"} className={className} onError={() => setFailedSource(src ?? null)} />
  );
}
