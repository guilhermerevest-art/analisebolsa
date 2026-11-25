import type { MetadataRoute } from "next";

import { lerTodosTickers } from "@/lib/dados";
import { urlSite } from "@/lib/site";

export const revalidate = 86400;

export default async function sitemap(): Promise<MetadataRoute.Sitemap> {
  const base = urlSite();
  const fixas: MetadataRoute.Sitemap = [{ url: `${base}/`, changeFrequency: "daily", priority: 1 }];
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
