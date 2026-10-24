"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { Icon } from "@/components/Icon";

export function HeaderSearch() {
  const router = useRouter();
  const [value, setValue] = useState("");
  const submit = (event: React.FormEvent) => {
    event.preventDefault();
    const q = value.trim();
    router.push(q ? `/variants?q=${encodeURIComponent(q)}` : "/variants");
  };
  return (
    <form className="header-search" role="search" onSubmit={submit} aria-label="站内搜索装备">
      <div className="search-field">
        <Icon name="search" />
        <input
          type="search"
          className="field"
          aria-label="搜索衣服、鞋、型号"
          placeholder="搜一件衣服、鞋或款号…"
          value={value}
          onChange={(event) => setValue(event.target.value)}
        />
      </div>
    </form>
  );
}
