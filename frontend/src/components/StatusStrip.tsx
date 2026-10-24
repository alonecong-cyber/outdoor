"use client";

import { useQuery } from "@tanstack/react-query";
import { Icon } from "@/components/Icon";
import { api } from "@/lib/api";
import { timeAgo } from "@/lib/format";

export function StatusStrip() {
  const status = useQuery({ queryKey: ["site-status"], queryFn: api.status, staleTime: 60_000, retry: 1 });
  if (!status.data) return <div className="status-strip"><span>{status.isPending ? "正在读取更新状态…" : "暂时无法读取更新状态"}</span><span>价格以结算页为准</span></div>;
  const data = status.data;
  return <div className="status-strip"><p><span className="status-dot" />{data.scheduler_enabled ? "后台自动更新已开启" : "后台自动更新未开启"}<span className="desktop-status"> · {data.last_deal_update ? `最近入库 ${timeAgo(data.last_deal_update)}` : "暂无更新时间"}</span></p><details><summary>数据状态<Icon name="chevron" /></summary><div className="source-popover"><p>{data.counts.deals} 条线报 · {data.counts.verified_offers} 个核验报价 · {data.counts.confirmed_variants} 个已确认规格</p>{data.sources.map((source) => <p key={source.source}><strong>{source.name}</strong> · {source.configured ? "已配置" : "未配置"}<br />{source.note}</p>)}<p>{data.last_deal_update ? `最近入库：${timeAgo(data.last_deal_update)}` : "尚无线报入库记录"}。入库时间不代表商家价格已核验。</p></div></details></div>;
}
