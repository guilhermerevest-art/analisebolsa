import type { MetadataRoute } from "next";

import { lerTodosTickers } from "@/lib/dados";
import { PRESETS, urlPreset } from "@/lib/screener";
import { urlSite } from "@/lib/site";

export const revalidate = 86400;

export default async function sitemap(): Promise<MetadataRoute.Sitemap> {
  const base = urlSite();
  const fixas: MetadataRoute.Sitemap = [
    { url: `${base}/`, changeFrequency: "daily", priority: 1 },
    { url: `${base}/screener`, changeFrequency: "daily", priority: 0.9 },
    { url: `${base}/simulador`, changeFrequency: "monthly", priority: 0.7 },
    { url: `${base}/backtest`, changeFrequency: "monthly", priority: 0.7 },
    ...PRESETS.map((p) => ({ url: `${base}${urlPreset(p).replaceAll("&", "&amp;")}`, changeFrequency: "daily" as const, priority: 0.7 })),
  ];
  try {
    const tickers = await lerTodosTickers();
    return [
      ...fixas,
      ...tickers.map((t) => ({ url: `${base}/ativo/${t}`, changeFrequency: "daily" as const, priority: 0.8 })),
    ];
  } catch {
    return fixas;
  }
}
