/** URL pública do site, usada no sitemap e em links absolutos. */
export function urlSite(): string {
  return (process.env.SITE_URL ?? process.env.AUTH_URL ?? "http://localhost:3000").replace(/\/$/, "");
}
