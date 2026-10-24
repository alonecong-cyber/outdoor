"use client";

import { useState } from "react";

/**
 * 商品图：缺图/加载失败时退回占位 SVG。
 * image 可能是站内路径（/products/…）或外链（https://…），都直接交给 <img>。
 */
export function ProductImage({
  src,
  alt,
  className,
}: {
  src?: string | null;
  alt: string;
  className?: string;
}) {
  const [failed, setFailed] = useState(false);
  const url = src && !failed ? src : "/products/placeholder.svg";
  return (
    // eslint-disable-next-line @next/next/no-img-element
    <img
      src={url}
      alt={alt}
      loading="lazy"
      className={className}
      onError={() => setFailed(true)}
    />
  );
}
